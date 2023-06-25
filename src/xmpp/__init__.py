import asyncio
import datetime
import functools
import json
import logging

import aioxmpp
import click
from lndgrpc import AsyncLNDClient
from lndgrpc.aio.async_client import ln

from ..numerology import number_to_numerology

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
    minimum_donation,
    allowed_name,
):
    ctx.ensure_object(dict)

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

                    await send_to_xmpp(muc_client, xmpp_room_jid, xmpp_nick, data, value)

                except aioxmpp.errors.XMPPError as error:
                    logging.exception("error: %s", error)


async def send_to_xmpp(
    muc_client: aioxmpp.muc.MUCClient,
    xmpp_room_jid: str,
    xmpp_nick: str,
    data,
    value
):
    # TODO: Get room jid from RSS feed <podcast:chat> element
    # This is different from IRC because you can join any room on any server
    #   (as long as the given account isn't banned and has access)
    room, join_future = muc_client.join(
        aioxmpp.JID.fromstr(xmpp_room_jid),
        xmpp_nick,
        history=None
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
