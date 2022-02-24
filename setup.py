#!/usr/bin/env python3

from setuptools import setup, find_packages


setup(
    name="BoostIRC",
    version="0.1.0",
    python_requires=">=3.9",
    description="Boost IRC",
    author_email="boostaccount.w0v3n@aleeas.com",
    packages=find_packages(include=["src", "src.*"]),
    entry_points={
        "console_scripts": [
            "boostirc=src.irc:cli",
            "boostodon=src.mastodon:cli",
        ],
    },
    install_requires=[
        "lnd-grpc-client<1,>=0.3.39",
        "click<9,>=8.0.3",
    ],
    extras_require={
        "tests": ["pytest>=6.2.5,<7"],
        "irc": [
            "bottom<3,>=2.2.0",
        ],
        "mastodon": [
              'atoot @ git+https://git@github.com/valcanobacon/atoot@1.0.2#egg=atoot',
        ],
    },
)
