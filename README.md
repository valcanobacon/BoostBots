# BoostBots

[![Tests](https://github.com/valcanobacon/BoostBots/actions/workflows/ci.yml/badge.svg)](https://github.com/valcanobacon/BoostBots/actions/workflows/ci.yml)

## BoostIRC

### Quick Start

```sh
git clone https://github.com/valcanobacon/BoostBots.git
cd BoostBots

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -e '.[irc]'

boostirc 
```

## Boostodon (Mastodon Bot)

### Quick Start

```sh
git clone https://github.com/valcanobacon/BoostBots.git
cd BoostBots

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -e '.[mastodon]'

boostodon
```

## Boostrix (Matrix Bot)

### Quick Start

```sh
git clone https://github.com/valcanobacon/BoostBots.git
cd BoostBots

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -e '.[matrix]'

boostrix
```

## Boostr (Nostr Bot)

### Quick Start

```sh
git clone https://github.com/valcanobacon/BoostBots.git
cd BoostBots

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -e '.[nostr]'

boostr
```

## Raspiblitz

```sh
--lnd-tlscert /mnt/hdd/app-data/lnd/tls.cert --lnd-macaroon /mnt/hdd/app-data/lnd/data/chain/bitcoin/mainnet/admin.macaroon
 ```

## BoostBots IRC systemd service:

1. `cd /etc/systemd/system`
2. `sudo nano ./boostbot.service`

    - Include the following in your boostbot.service file:
            
            [Unit]
            Description='BoostBot system service'

            [Service]
            User=admin
            WorkingDirectory=/home/admin/BoostBots/
            ExecStart=/bin/bash -c 'cd /home/admin/BoostBots/ && source venv/bin/activate && boostirc --lnd-tlscert <path to tls cert> --lnd-macaroon <path to admin macaroon> --lnd-host 127.0.0.1 --irc-host <your IRC host> --irc-ssl true --irc-port 6697 --irc-nick <Your bot's IRC nickname> --irc-realname BoostIRC --irc-channel "#YourIRCChannel" --irc-channel-map "#YourIRCChannel" feedId <Podcast Index feed id> --irc-nick-password <password>'

            [Install]
            WantedBy=multi-user.target

3. Reload the service files:
`sudo systemctl daemon-reload`

4. Start the service
`sudo systemctl start boostbot.service`

5. Check the status of the service
`sudo systemctl status boostbot.service`

6. Enable the service on future reboots
`sudo systemctl enable boostbot.service`

- OPTIONAL: if you want to disable the service on future reboots:
`sudo systemctl disable boostbot.service`


# Numerology

| Sats | Emoji | Description |
| - | - | - |
| 10 | 🎳 | Bowler Donation X3 +🦃 |
| 11 | 🎲 | Dice Donation |
| 21 | 🪙 | Bitcoin donation|
| 33 | ✨ | Magic Number Donation|
| 69 | 💋 | Swasslenuff Donation  |
| 73 | 👋 | Greetings Donation  |
| 88 | 🥰 | Love and Kisses Donation  |
| 314 | 🥧 | Pi Donation |
| 321 | 💥 | Countdown Donation |
| 420 | ✌👽💨 | Stoner Donation |
| 666 | 😈 | Devil Donation |
| 777 | 😇 | Angel Donation |
| 1776 | 🇺🇸 | America Fuck Yeah Donation |
| 1867 | 🇨🇦 | Canada Donation |
| 6006 | 🎱🎱 | Boobs Donation |
| 8008 | 🎱🎱 | Boobs Donation |
| 9653 | 🐺 | Wolf Donation |
| 30057 | 🔁 | Boost Donation | 

## Combinations

You can combine numbers, order matters!

| Sats | Emoji | Description |
| - | - | - |
| 6969 | 💋💋 | Double Kiss Donation|
| 3369 | ✨💋 | Magic Kiss Donation |
| 6933 | 💋✨ | Kiss Magic Donation |
| 10420 | ✌👽💨🔥 | Lit Stoner Donation|
| 31415 | 🥧🥧🥧🔥 | Lit Pi Donation|
| 33420 | ✨✌👽💨🔥 | Magic Lit Stoner Donation|
| 22222 | 🦆🦆🦆🦆🦆🔥 | Lit Ducks in a row Donation | 
| 69133 | 💋✨🔥🔥 | Double Lit Magic Kiss Donation |
| 101010 | 🎳🎳🎳🦃🔥🔥🔥 | Turkey Donation |
| 699653 | 💋🐺🔥🔥🔥 | Kiss Wolf Triple Lit Donation|
| 696969 | 💋💋💋🔥🔥🔥 | Triple Kiss Triple Lit Donation|
| 698008 | 💋🎱🎱🔥🔥🔥 | Kiss Boobs Triple Lit Donation|

## Ducks In a Row Donation
If the value is all 2s then you get that many 🦆s

| Sats | Emoji |
| - | - |
| 22 | 🦆🦆 |
| 222 | 🦆🦆🦆 |
| 2222 |🦆🦆🦆🦆 |

## Pi Donation
Any sequence of PI of at least 3 characters gets you 🥧.
4 characters is double pi, 5 characters is triple, ...

| Sats | Emoji |
| - | - |
| 314 | 🥧 |
| 3141 | 🥧🥧 |
| 31415 | 🥧🥧🥧🔥 |

## Countdown Donation
Any Countdown of at least 3 characters gets you 💥.
4 characters is double, 5 characters is triple, ...

| Sats | Emoji |
| - | - |
| 321 | 💥 |
| 4321 | 💥💥 |
| 54321 | 💥💥💥🔥 |

## Lit Donations

| Sats | Emoji |
| - | - |
| >= 10000 | 🔥 |
| >= 50000 | 🔥🔥 |
| >= 100000 | 🔥🔥🔥 |

## Shit Donations

| Sats | Emoji |
| - | - |
| < 9 | 💩 |
| 2 | 🦆💩 |
