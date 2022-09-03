import asyncio
import collections
import datetime
import functools
import json
import logging

import atoot
import click
from lndgrpc import AsyncLNDClient
from lndgrpc.aio.async_client import ln

from ..numerology import number_to_numerology


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
    minimum_donation,
    allowed_name,
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
                    logging.debug("Donation too low, skipping", data)
                    continue

                sender = data.get("sender_name", "Anonymous")

                numerology = number_to_numerology(value)

                message = ""
                if "podcast" in data and data["podcast"]:
                    message += data["podcast"]
                if "episode" in data and data["episode"]:
                    message += f" {data['episode']}"
                if "ts" in data and data["ts"]:
                    message += "@ {}".format(
                        datetime.timedelta(seconds=int(data["ts"]))
                    )
                message += "\n\n"
                message += f"{numerology} {sender} boosted {value} sats"
                message += "\n\n"
                if "message" in data and data["message"]:
                    message += f"\"{data['message']}\""
                    message += "\n\n"
                message += "via {}".format(data.get("app_name", "Unknown"))
                if "url" in data and data["url"] or "feedID" in data and data["feedID"]:
                    message += "\n\n"
                if "url" in data and data["url"]:
                    message += "{}\n".format(data["url"])
                if "feedID" in data and data["feedID"]:
                    message += "https://podcastindex.org/podcast/{}\n".format(
                        data["feedID"]
                    )

                logging.debug(message)
                await mastodon.create_status(status=message)

            except:
                logging.exception("error")


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
