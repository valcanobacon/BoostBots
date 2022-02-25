import asyncio
import functools
import json
import logging
from datetime import timedelta

import click
from lndgrpc import AsyncLNDClient
from nio import AsyncClient as AsyncMatrixClient
from nio import LoginError as MatrixLoginError

from ..numerology import number_to_numerology


def async_cmd(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper


@click.command()
@click.option("--lnd-host", default="127.0.0.1")
@click.option("--lnd-port", type=click.IntRange(0), default=10009)
@click.option(
    "--lnd-macaroon", type=click.Path(exists=True), default="readonly.macaroon"
)
@click.option("--lnd-tlscert", type=click.Path(exists=True), default="tls.cert")
@click.option("--matrix-server", default="https://matrix.example.org")
@click.option("--matrix-user", required=True)
@click.option("--matrix-password", required=True)
@click.option("--matrix-room-id", required=True, multiple=True)
@click.option("--minimum-donation", type=int)
@click.option("-v", "--verbose", is_flag=True, help="Enables verbose mode")
@click.pass_context
@async_cmd
async def cli(
    ctx,
    lnd_host,
    lnd_port,
    lnd_macaroon,
    lnd_tlscert,
    matrix_server,
    matrix_user,
    matrix_password,
    matrix_room_id,
    minimum_donation,
    verbose,
):
    ctx.ensure_object(dict)

    logging.getLogger().setLevel(logging.DEBUG if verbose else logging.INFO)

    matrix = AsyncMatrixClient(
        homeserver=matrix_server,
        user=matrix_user,
    )

    resp = await matrix.login(password=matrix_password)
    if isinstance(resp, MatrixLoginError):
        logging.debug(resp)
        return
    logging.debug(resp)

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

                message = new_message(data, value)
                logging.debug(message)

                # Send the data to each room
                for room_id in matrix_room_id:
                    logging.debug(f"Sending to {room_id}")
                    await matrix.room_send(
                        room_id=room_id,
                        message_type="m.room.message",
                        content={
                            "msgtype": "m.text",
                            "body": message,
                        },
                    )

                await matrix.sync_forever(timeout=30000)  # milliseconds

            except:
                logging.exception("error")


def new_message(data, value):
    def get(data, key, format_found=None, default=None):
        if key in data:
            value = data[key]
            if value:
                if format_found is None:
                    return value
                if callable(format_found):
                    return format_found(key, value)
                return format_found.format(**{key: value})
        return default

    amount = f"{value} sats"

    sender = get(data, "sender_name", default="Anonymous")
    podcast = get(data, "podcast", "[{podcast}]")
    episode = get(data, "episode", "[{episode}]")
    message = get(data, "message", 'saying "{message}"')
    app = get(data, "app_name", "via {app_name}")
    timestamp = get(data, "ts", lambda _, v: "@ {}".format(timedelta(seconds=int(v))))

    numerology = number_to_numerology(value)

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
