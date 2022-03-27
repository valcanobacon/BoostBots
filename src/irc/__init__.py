import asyncio
import codecs
import json
import logging
from datetime import timedelta

import bottom
import click
from lndgrpc import AsyncLNDClient

from ..numerology import number_to_numerology

APP_PUBKEY = ""


@click.command()
@click.option("--lnd-host", default="127.0.0.1")
@click.option("--lnd-port", type=click.IntRange(0), default=10009)
@click.option(
    "--lnd-macaroon", type=click.Path(exists=True), default="readonly.macaroon"
)
@click.option("--lnd-tlscert", type=click.Path(exists=True), default="tls.cert")
@click.option("--irc-host", default="irc.zeronode.net")
@click.option("--irc-port", type=int, default=6697)
@click.option("--irc-ssl", type=bool, default=True)
@click.option("--irc-password")
@click.option("--irc-nick", default="boostirc")
@click.option("--irc-channel", default=["#boostirc"], multiple=True)
@click.option("--irc-realname", default="Boost IRC Bot")
@click.option("--irc-nick-password")
@click.option("--minimum-donation", type=int)
@click.pass_context
def cli(
    ctx,
    lnd_host,
    lnd_port,
    lnd_macaroon,
    lnd_tlscert,
    irc_host,
    irc_port,
    irc_ssl,
    irc_password,
    irc_nick,
    irc_nick_password,
    irc_channel,
    irc_realname,
    minimum_donation,
):
    ctx.ensure_object(dict)

    async_lnd = AsyncLNDClient(
        f"{lnd_host}:{lnd_port}",
        macaroon_filepath=lnd_macaroon,
        cert_filepath=lnd_tlscert,
    )

    bot = bottom.Client(host=irc_host, port=irc_port, ssl=irc_ssl)

    @bot.on("CLIENT_CONNECT")
    async def connect(**kwargs):
        bot.send("NICK", nick=irc_nick)
        bot.send("USER", user=irc_nick, realname=irc_realname)
        if irc_password is not None:
            bot.send("PASS", password=irc_password)

        # Don't try to join channels until the server has
        # sent the MOTD, or signaled that there's no MOTD.
        _, pending = await asyncio.wait(
            [
                bot.wait("RPL_ENDOFMOTD"),
                bot.wait("ERR_NOMOTD"),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel whichever waiter's event didn't come in.
        for future in pending:
            future.cancel()

        if irc_nick_password:
            bot.send(
                "PRIVMSG", target="NickServ", message=f"IDENTIFY {irc_nick_password}"
            )

        for channel in irc_channel:
            bot.send("JOIN", channel=channel)

    @bot.on("PING")
    def keepalive(message, **kwargs):
        bot.send("PONG", message=message)

    async def subscribe_invoices():
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

                    value = int(data.get("value_msat_total", 0)) // 1000
                    if not value:
                        value = invoice.value

                    if minimum_donation is not None and value < minimum_donation:
                        logging.debug("Donation too low, skipping", data)
                        continue

                    message = _new_message(data, value)
                    logging.debug(message)

                    for channel in irc_channel:
                        bot.send("PRIVMSG", target=channel, message=message)

                except Exception as exception:
                    click.echo(exception)

    bot.loop.run_until_complete(bot.connect())

    bot.loop.run_until_complete(subscribe_invoices())

    bot.loop.run_forever()


def _get(data, key, format_found=None, default=None):
    if key in data:
        value = data[key]
        if value:
            value = _sanitize(value)
            if format_found is None:
                return value
            if callable(format_found):
                return format_found(key, value)
            return format_found.format(**{key: value})
    return default


def _sanitize(message):
    # for IRC TODO: check for and replace more than just newlines
    if isinstance(message, str):
        print(repr(message))
        # if "\u" in message:
        #     message = (message.encode('utf-16', 'surrogatepass')
        #                       .decode('utf-16'))
        #     message = r"{}".format(message)
        return message.replace("\n", "")
    return message


def _new_message(data, value, numerology_func=number_to_numerology):

    amount = f"\x02\u200b{value}\x02 sats"
    app = _get(data, "app_name", "via {app_name}")
    sender = _get(data, "sender_name", default="Anonymous")
    podcast = _get(data, "podcast", "\x02[{podcast}]\x02")
    episode = _get(data, "episode", "\x02[{episode}]\x02")
    message = _get(data, "message", 'saying "\x02{message}\x02"')
    timestamp = _get(data, "ts", lambda _, v: "@{}".format(timedelta(seconds=int(v))))
    numerology = numerology_func(value)

    # Build the data to send to Matrix
    data = ""
    if numerology:
        data += numerology + " "
    if podcast:
        data += podcast + " "
    if episode:
        data += episode + " "
    if sender:
        data += sender + " "
    data += f"boosted {amount}"
    if message:
        data += " " + message
    if timestamp:
        data += " " + timestamp
    if app:
        data += " " + app

    return data
