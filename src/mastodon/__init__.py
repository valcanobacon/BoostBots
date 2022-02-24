import asyncio
import datetime
import json

import click
from lndgrpc import AsyncLNDClient

from ..numerology import number_to_numerology


@click.command()
@click.option("--lnd-host", default="127.0.0.1")
@click.option("--lnd-port", type=click.IntRange(0), default=10009)
@click.option(
    "--lnd-macaroon", type=click.Path(exists=True), default="readonly.macaroon"
)
@click.option("--lnd-tlscert", type=click.Path(exists=True), default="tls.cert")
@click.pass_context
def cli(
    ctx,
    lnd_host,
    lnd_port,
    lnd_macaroon,
    lnd_tlscert,
):
    ctx.ensure_object(dict)

    async_lnd = AsyncLNDClient(
        f"{lnd_host}:{lnd_port}",
        macaroon_filepath=lnd_macaroon,
        cert_filepath=lnd_tlscert,
    )

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

                except Exception as exception:
                    click.echo(exception)

    loop = asyncio.new_event_loop()

    loop.run_until_complete(subscribe_invoices())

    loop.run_forever()
