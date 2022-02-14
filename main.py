import asyncio
import json
import bottom

import click

from lndgrpc import AsyncLNDClient


@click.command()
@click.option("--lnd-host", default="127.0.0.1")
@click.option("--lnd-port", type=click.IntRange(0), default=10009)
@click.option("--lnd-macaroon", type=click.Path(exists=True), default="readonly.macaroon")
@click.option("--lnd-tlscert", type=click.Path(exists=True), default="tls.cert")
@click.option("--irc-host", default="irc.zeronode.net")
@click.option("--irc-port", type=int, default=6697)
@click.option("--irc-ssl", type=bool, default=True)
@click.option("--irc-nick", default="boostirc")
@click.option("--irc-channel", default="#boostirc")
@click.option("--irc-realname", default="Boost IRC Bot")
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

        bot.send("JOIN", channel=irc_channel)

    @bot.on("PING")
    def keepalive(message, **kwargs):
        bot.send("PONG", message=message)

    async def subscribe_invoices():
        invoices = async_lnd.subscribe_invoices()
        async for invoice in invoices:
            for tlv in invoice.htlcs:

                data = tlv.custom_records.get(7629169)
                if data is None:
                    continue

                try:
                    data = json.loads(data)
                except json.decoder.JSONDecodeError:
                    continue

                if "action" not in data or str(data["action"]).lower() != "boost":
                    continue

                app = data.get("app_name", "?")
                sender = data.get("sender_name", "Anonymous")
                message = data.get("message")

                amount = int(data.get("value_msat_total", 0)) // 1000
                if not amount:
                    amount = invoice.value

                message = "{sender} boosted {amount} sats via {app}! {message}".format(
                    sender=sender,
                    amount=amount,
                    app=app,
                    message=message,
                )

                click.echo(message)
                bot.send("PRIVMSG", target=irc_channel, message=message)

    bot.loop.run_until_complete(bot.connect())

    bot.loop.run_until_complete(subscribe_invoices())

    bot.loop.run_forever()


if __name__ == "__main__":
    cli()
