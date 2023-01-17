import asyncio
import collections
import datetime
import functools
import json
import logging
import ssl
import time

import atoot
import click
from lndgrpc import AsyncLNDClient
from lndgrpc.aio.async_client import ln

from nostr.event import Event
from nostr.key import PrivateKey
from nostr.message_type import ClientMessageType
from nostr.relay_manager import RelayManager

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
@click.option("--nostr-private-key")
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
    nostr_private_key,
    minimum_donation,
    allowed_name,
):
    ctx.ensure_object(dict)

    logging.getLogger().setLevel(logging.INFO)

    if nostr_private_key:
        if nostr_private_key.startswith("nsec"):
            keys = PrivateKey.from_nsec(nostr_private_key)
        else:
            keys = PrivateKey(bytes.fromhex(nostr_private_key))
    else:
        nostr_keys = PrivateKey()
        logging.info(
            f"Generated Nostr public/private key pair: {keys.bech32()}/{keys.raw_secret.hex()}"
        )

    logging.info(
        f"Using Nostr public key: ${keys.public_key.bech32()}/{keys.public_key.raw_bytes.hex()}"
    )

    relay_manager = RelayManager()
    relay_manager.add_relay("wss://relay.damus.io")
    relay_manager.add_relay("wss://brb.io")
    relay_manager.add_relay("wss://relay.stoner.com")
    relay_manager.open_connections(
        {"cert_reqs": ssl.CERT_NONE}
    )  # NOTE: This disables ssl certificate verification
    time.sleep(1.25)  # allow the connections to open
    relay_manager.close_connections()

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
                    message += f"\"{data['message'].strip()}\""
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
                relay_manager.open_connections(
                    {"cert_reqs": ssl.CERT_NONE}
                )  # NOTE: This disables ssl certificate verification
                time.sleep(1.25)  # allow the connections to open

                event = Event(keys.public_key.hex(), message)
                event.sign(keys.hex())

                message = json.dumps([ClientMessageType.EVENT, event.to_json_object()])
                relay_manager.publish_message(message)
                time.sleep(1)  # allow the messages to send

                relay_manager.close_connections()

            except:
                logging.exception("error")
