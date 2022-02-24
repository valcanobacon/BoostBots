import asyncio
import datetime
import json

from ..numerology import number_to_numerology

import bottom
import click
from lndgrpc import AsyncLNDClient

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
@click.option("--irc-nick", default="boostirc")
@click.option("--irc-channel", default=["#boostirc"], multiple=True)
@click.option("--irc-realname", default="Boost IRC Bot")
@click.option("--irc-nick-password")
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
    irc_nick,
    irc_nick_password,
    irc_channel,
    irc_realname,
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

                    app = "via {}".format(data.get("app_name", "Unknown"))

                    sender = data.get("sender_name", "Anonymous")

                    podcast = ""
                    if "podcast" in data and data["podcast"]:
                        podcast = f"\x02[{data['podcast']}]\x02 "  # trailing space

                    episode = ""
                    if "episode" in data and data["episode"]:
                        episode = f"\x02[{data['episode']}]\x02 "  # trailing space

                    message = ""
                    if "message" in data and data["message"]:
                        message = (
                            f"saying \"\x02{data['message']}\x02\" "  # trailing space
                        )

                    timestamp = ""
                    if "ts" in data and data["ts"]:
                        timestamp = "@ {} ".format(
                            datetime.timedelta(seconds=int(data["ts"]))
                        )  # trailing space

                    value = int(data.get("value_msat_total", 0)) // 1000
                    if not value:
                        value = invoice.value
                    amount = f"\x02{value}\x02 sats "  # trailing space

                    numerology = number_to_numerology(value)
                    if numerology:
                        numerology += " "

                    message = f"{numerology}{podcast}{episode}{sender} boosted {amount}{message}{timestamp}{app}"

                    click.echo(message)
                    for channel in irc_channel:
                        bot.send("PRIVMSG", target=channel, message=message)

                except Exception as exception:
                    click.echo(exception)

    bot.loop.run_until_complete(bot.connect())

    bot.loop.run_until_complete(subscribe_invoices())

    bot.loop.run_forever()