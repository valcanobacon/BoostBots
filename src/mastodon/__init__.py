import asyncio
import datetime
import functools
import json
import logging

import atoot
import click
from lndgrpc import AsyncLNDClient

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
