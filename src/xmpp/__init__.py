import asyncio
import datetime
import functools
import json
import logging
from typing import Optional

import aioxmpp
import click
import requests
from bs4 import BeautifulSoup
from lndgrpc import AsyncLNDClient

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
@click.option("--xmpp-account-jid")
@click.option("--xmpp-account-password")
@click.option("--xmpp-room-jid")
@click.option("--xmpp-nick", default="BoostBot XMPP")
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
    xmpp_account_jid,
    xmpp_account_password,
    xmpp_room_jid,
    xmpp_nick,
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

    client = aioxmpp.Client(
        aioxmpp.JID.fromstr(xmpp_account_jid),
        aioxmpp.make_security_layer(xmpp_account_password)
    )

    async with client.connected() as stream:
        muc_client = client.summon(aioxmpp.muc.MUCClient)
        logging.info(f"Connected to {xmpp_account_jid}")

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

                    logging.debug(data)

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

                    await send_to_xmpp(muc_client, xmpp_room_jid, xmpp_nick, podcast_index, data, value)

                except aioxmpp.errors.XMPPError as error:
                    logging.exception("error: %s", error)


async def send_to_xmpp(
    muc_client: aioxmpp.muc.MUCClient,
    xmpp_room_jid: str,
    xmpp_nick: str,
    podcast_index: PodcastIndex,
    data,
    value
):
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

    chat = item.find("podcast:chat", protocol="xmpp")
    if not (chat and chat.get("space")):
        return

    logging.debug(chat)

    logging.info(f"Joining room '{chat['space']}'")

    room, join_future = muc_client.join(
        aioxmpp.JID.fromstr(chat["space"]),
        xmpp_nick,
        # Don't bother to fetch room history when joining
        history=aioxmpp.muc.xso.History(maxchars=0, maxstanzas=0, seconds=0)
    )

    message = muc_message(data, value)

    await join_future

    logging.info(f"Posting to XMPP room {room.jid}: {message.body}")

    await room.send_message(message)

    await room.leave()


def muc_message(data, value):
    xmpp_message = aioxmpp.Message(
        type_=aioxmpp.MessageType.GROUPCHAT
    )

    numerology = number_to_numerology(value)

    sender = data.get("sender_name", "Anonymous")

    message = f"{numerology} {sender} boosted {value} sats"

    if "ts" in data and data["ts"]:
        message += " @ {}".format(datetime.timedelta(seconds=int(data["ts"])))

    message += "\n"
    if "message" in data and data["message"]:
        message += f"\"{data['message'].strip()}\""
        message += "\n"
    message += "via {}".format(data.get("app_name", "Unknown"))

    xmpp_message.body[None] = message

    return xmpp_message


def get_feed(feed_url) -> Optional[BeautifulSoup]:
    response = requests.get(feed_url)
    if response.status_code not in [requests.status_codes.codes.ok]:
        return

    return BeautifulSoup(response.text, features="xml")


def get_feed_url_from_podcast_index(podcast_index: PodcastIndex, data) -> Optional[str]:
    feed_id = data.get("feedID")
    if not feed_id:
        return

    try:
        result = podcast_index.podcasts_byfeedid(feed_id)
        return result.data["feed"]["url"]
    except:
        pass
