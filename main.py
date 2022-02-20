import asyncio
import datetime
import json
import re

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
@click.option("--irc-channel", default="#boostirc")
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
            bot.send("PRIVMSG", target="NickServ", message=f"IDENTIFY {irc_nick_password}")

        bot.send("JOIN", channel=irc_channel)

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

                    message = ""
                    if "message" in data and data["message"]:
                        message = (
                            f"saying \"\x02{data['message']}\x02\" "  # trailing space
                        )

                    episode = ""
                    if "episode" in data and data["episode"]:
                        episode = f"on episode \"\x02{data['episode']}\x02\" "  # trailing space

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

                    message = f"{numerology}{podcast}{sender} boosted {amount}{message}{episode}{timestamp}{app}"

                    click.echo(message)
                    bot.send("PRIVMSG", target=irc_channel, message=message)

                except Exception as exception:
                    click.echo(exception)

    bot.loop.run_until_complete(bot.connect())

    bot.loop.run_until_complete(subscribe_invoices())

    bot.loop.run_forever()


def number_to_numerology(number: int) -> str:
    results = []

    regex = r"21|33|69|73|88|420|666|1776|2695|9653|[68]00[68]|^2+$"

    matches = re.findall(regex, str(number))

    for match in matches:

        if match == "21":
            results.append("🪙")

        if match == "33":
            results.append("✨")

        if match == "69":
            results.append("💋")

        if match == "73":
            results.append("👋")

        if match == "88":
            results.append("🥰")

        if match == "420":
            results.append("🌱")

        if match == "666":
            results.append("😈")

        if match == "1776":
            results.append("🇺🇸")

        if match == "2695":
            results.append("🎳")

        if match == "9653":
            results.append("🐺")

        if re.search(r"[68]00[68]", match):
            results.append("🎱")
            results.append("🎱")

        if re.search(r"^2+$", match):
            for _ in range(len(match)):
                results.append("🦆")

    if number >= 100000:
        results.append("🔥")

    if number >= 50000:
        results.append("🔥")

    if number >= 10000:
        results.append("🔥")

    if number < 10:
        results.append("💩")

    if not results:
        return ""

    return "".join(results) + " "


if __name__ == "__main__":
    cli()
