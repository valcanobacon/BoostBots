# BoostIRC

## Quick Start

```sh
git clone https://github.com/valcanobacon/BoostIRC.git
cd BoostIRC

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Install the patched version of lnd-grpc-client
cd ..
git clone https://github.com/valcanobacon/lnd-grpc-client
git checkout fix-subscribe-invoices
poetry install
cd -

boostirc \
    --lnd-host REDACTED.m.voltageapp.io \
    --lnd-macaroon ./admin.macaroon \
    --lnd-tlscert ./tls.cert \
    --irc-host irc.zeronode.net \
    --irc-port 6697 \
    --irc-nick boostirc
```

