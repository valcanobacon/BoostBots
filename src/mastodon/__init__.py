import asyncio
import collections
import datetime
import functools
import json
import logging
from urllib.parse import urlparse

import atoot
import click
import requests
from bs4 import BeautifulSoup
from lndgrpc import AsyncLNDClient
from lndgrpc.aio.async_client import ln

from ..numerology import number_to_numerology
from ..podcast_index import PodcastIndex

logging.getLogger().setLevel(logging.INFO)


def async_cmd(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper


@click.command()
@click.option("--lnd-host", default="127.0.0.1")
@click.option("--lnd-port", type=click.IntRange(0), default=10009)
@click.option("--lnd-macaroon", type=click.Path(exists=True), default="admin.macaroon")
@click.option("--lnd-tlscert", type=click.Path(exists=True), default="tls.cert")
@click.option("--mastodon-instance")
@click.option("--mastodon-access-token")
@click.option("--podcast-index-api-key")
@click.option("--podcast-index-api-secret")
@click.option("--minimum-donation", type=int)
@click.option("--allowed-name", multiple=True)
@click.pass_context
@async_cmd
async def cli(
    ctx,
    lnd_host,
    lnd_port,
    lnd_macaroon,
    lnd_tlscert,
    mastodon_instance,
    mastodon_access_token,
    podcast_index_api_key,
    podcast_index_api_secret,
    minimum_donation,
    allowed_name,
):
    ctx.ensure_object(dict)

    podcast_index = PodcastIndex(
        user_agent="BoostBots",
        api_key=podcast_index_api_key,
        api_secret=podcast_index_api_secret,
    )

    mastodon = await atoot.MastodonAPI.create(
        mastodon_instance, access_token=mastodon_access_token
    )
    resp = await mastodon.verify_account_credentials()
    logging.debug(resp)
    logging.info(f"Connected to {mastodon_instance}")

    async_lnd = AsyncLNDClient(
        f"{lnd_host}:{lnd_port}",
        macaroon_filepath=lnd_macaroon,
        cert_filepath=lnd_tlscert,
    )

    invoices = async_lnd.subscribe_invoices()
    async for invoice in invoices:
        for tlv in invoice.htlcs:
            try:
                data = tlv.custom_records.get(7629169)
                if data is None:
                    continue

                data = json.loads(data)

                if "action" not in data or str(data["action"]).lower() != "boost":
                    continue

                if allowed_name:
                    name = data.get("name")
                    if not name:
                        continue

                    if name.lower() not in [x.lower() for x in allowed_name]:
                        continue

                value = int(data.get("value_msat_total", 0)) // 1000
                if not value:
                    value = invoice.value

                if minimum_donation is not None and value < minimum_donation:
                    logging.debug("Donation too low, skipping: %s", data)
                    continue

                status = await send_to_social_interact(
                    mastodon, podcast_index, data, value
                )
                if status:
                    logging.info("Boosting: %s", status)
                    await mastodon.status_boost(status)
                else:
                    message = main_message(data, value)
                    logging.info("Creating Status: %s", message)
                    await mastodon.create_status(
                        status=message,
                        in_reply_to_id=None,
                        # bug work around to reset value
                        params={},
                    )

            except atoot.MastodonError as error:
                logging.exception("error: %s", error)


async def send_to_social_interact(mastodon, podcast_index, data, value):
    message = reply_message(data, value)

    feed_url = data.get("url")
    if not feed_url:
        feed_url = get_feed_url_from_podcast_index(podcast_index, data)
        if not feed_url:
            return

    logging.debug(feed_url)

    soup = get_feed(feed_url)
    if not soup:
        return

    items = soup.find_all(["podcast:liveItem", "item"])
    item = next(
        filter(
            lambda x: x.title.get_text() == data.get("episode")
            or x.guid.get_text() == data.get("guid"),
            items,
        ),
        None,
    )
    if not item:
        return

    logging.debug(item)

    social_interact = item.find("podcast:socialinteract", protocol="activitypub")
    if not (social_interact and social_interact.get("uri")):
        return

    logging.debug(social_interact)

    status = await mastodon.search(social_interact["uri"], resolve=True)
    if not (status and status.get("statuses")):
        return

    reply_to_id = status.get("statuses")[0].get("id")
    if not reply_to_id:
        return

    logging.info("Creating Status (reply to %s): %s", reply_to_id, message)
    return await mastodon.create_status(
        status=message,
        in_reply_to_id=reply_to_id,
        # bug work around to reset value
        params={},
    )


def get_feed(feed_url):
    response = requests.get(feed_url)
    if response.status_code not in [requests.status_codes.codes.ok]:
        return

    return BeautifulSoup(response.text, "lxml")


def get_feed_url_from_podcast_index(podcast_index, data):
    feed_id = data.get("feedID")
    if not feed_id:
        return

    try:
        result = podcast_index.podcasts_byfeedid(feed_id)
        return result.data["feed"]["url"]
    except:
        pass


def main_message(data, value):

    numerology = number_to_numerology(value)

    sender = data.get("sender_name", "Anonymous")

    message = ""
    if "podcast" in data and data["podcast"]:
        message += data["podcast"]
    if "episode" in data and data["episode"]:
        message += f" {data['episode']}"
    if "ts" in data and data["ts"]:
        message += " @ {}".format(datetime.timedelta(seconds=int(data["ts"])))
    message += "\n\n"
    message += f"{numerology} {sender} boosted {value} sats"
    message += "\n\n"
    if "message" in data and data["message"]:
        message += f"\"{data['message'].strip()}\""
        message += "\n\n"
    message += "via {}".format(data.get("app_name", "Unknown"))
    if "url" in data and data["url"] or "feedID" in data and data["feedID"]:
        message += "\n\n"
    if "url" in data and data["url"]:
        message += "{}\n".format(data["url"])
    if "feedID" in data and data["feedID"]:
        message += "https://podcastindex.org/podcast/{}\n".format(data["feedID"])

    return message


def reply_message(data, value):
    numerology = number_to_numerology(value)

    sender = data.get("sender_name", "Anonymous")

    message = f"{numerology} {sender} boosted {value} sats"

    if "ts" in data and data["ts"]:
        message += " @ {}".format(datetime.timedelta(seconds=int(data["ts"])))

    message += "\n\n"
    if "message" in data and data["message"]:
        message += f"\"{data['message'].strip()}\""
        message += "\n\n"
    message += "via {}".format(data.get("app_name", "Unknown"))

    return message


@click.command()
@click.option("--lnd-host", default="127.0.0.1")
@click.option("--lnd-port", type=click.IntRange(0), default=10009)
@click.option("--lnd-macaroon", type=click.Path(exists=True), default="admin.macaroon")
@click.option("--lnd-tlscert", type=click.Path(exists=True), default="tls.cert")
@click.option("--mastodon-instance")
@click.option("--mastodon-access-token")
@click.pass_context
@async_cmd
async def leaderboard(
    ctx,
    lnd_host,
    lnd_port,
    lnd_macaroon,
    lnd_tlscert,
    mastodon_instance,
    mastodon_access_token,
):
    ctx.ensure_object(dict)

    mastodon = await atoot.MastodonAPI.create(
        mastodon_instance, access_token=mastodon_access_token
    )
    resp = await mastodon.verify_account_credentials()
    logging.debug(resp)
    logging.info(f"Connected to {mastodon_instance}")

    async_lnd = AsyncLNDClient(
        f"{lnd_host}:{lnd_port}",
        macaroon_filepath=lnd_macaroon,
        cert_filepath=lnd_tlscert,
    )

    now = datetime.datetime.now()
    end = now - datetime.timedelta(weeks=1)
    print(end)

    async def generate_invoices(end: datetime.datetime):
        last_date = None
        index_offset = None
        while True:
            response = await async_lnd._ln_stub.ListInvoices(
                ln.ListInvoiceRequest(
                    index_offset=index_offset,
                    reversed=True,
                    num_max_invoices=100,
                )
            )
            if not response.invoices:
                break
            for index, invoice in enumerate(response.invoices):
                if not invoice.settled:
                    continue
                last_date = datetime.datetime.fromtimestamp(invoice.settle_date)
                if last_date and last_date < end:
                    continue
                yield invoice
            if last_date and last_date < end:
                break

            index_offset = response.first_index_offset

    leaderboard = collections.defaultdict(lambda: collections.defaultdict(float))

    async for invoice in generate_invoices(end):
        for tlv in invoice.htlcs:
            try:
                data = tlv.custom_records.get(7629169)
                if data is None:
                    continue

                data = json.loads(data)

                if "action" not in data or str(data["action"]).lower() != "boost":
                    continue

                name = data.get("name")
                if not name:
                    continue

                if name.lower() != "boostbot":
                    continue

                value = int(data.get("value_msat_total", 0)) // 1000
                if not value:
                    value = invoice.value

                sender = data.get("sender_name")
                if not sender:
                    continue

                app_name = data.get("app_name")
                if not app_name:
                    continue

                podcast = data.get("padcast")

                leaderboard[(app_name, sender)]["count"] += 1.0
                leaderboard[(app_name, sender)]["total"] += value
                if leaderboard[(app_name, sender)]["biggest"] < value:
                    leaderboard[(app_name, sender)]["biggest"] = value

            except:
                logging.exception("error")

    lines = [
        " 🏆🏆🏆 Leaderboard ~ Last 7 days 🏆🏆🏆",
        "",
        "      💰 Most Amount Boosted 💰",
        "",
    ]

    most_amount_boosted = sorted(
        leaderboard.items(), key=lambda i: i[1]["total"], reverse=True
    )
    for index, ((app_name, sender), stats) in enumerate(most_amount_boosted[:10]):
        place = index + 1
        if place == 1:
            place = "🥇"
        if place == 2:
            place = "🥈"
        if place == 3:
            place = "🥉"
        lines.append(f" {place} {sender} from {app_name}: {int(stats['total'])}")

    message = "\n".join(lines)
    try:
        logging.debug(message)
        await mastodon.create_status(status=message)
    except:
        logging.exception("error")

    lines = [
        " 🏆🏆🏆 Leaderboard ~ Last 7 days 🏆🏆🏆",
        "",
        "      🔥 Biggest Amount Boosted 🔥",
        "",
    ]

    biggest_amount_boosted = sorted(
        leaderboard.items(), key=lambda i: i[1]["biggest"], reverse=True
    )
    for index, ((app_name, sender), stats) in enumerate(biggest_amount_boosted[:10]):
        place = index + 1
        if place == 1:
            place = "🥇"
        if place == 2:
            place = "🥈"
        if place == 3:
            place = "🥉"
        lines.append(f" {place} {sender} from {app_name}: {int(stats['biggest'])}")

    message = "\n".join(lines)

    try:
        logging.debug(message)
        await mastodon.create_status(status=message)
    except:
        logging.exception("error")
