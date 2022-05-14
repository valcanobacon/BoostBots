#!/usr/bin/env python3

from setuptools import find_packages, setup

setup(
    name="BoostBots",
    version="0.8.1",
    python_requires=">=3.7",
    description="Boost Bots",
    author_email="boostaccount.w0v3n@aleeas.com",
    packages=find_packages(include=["src", "src.*"]),
    entry_points={
        "console_scripts": [
            "boostirc=src.irc:cli",
            "boostodon=src.mastodon:cli",
            "boostrix=src.matrix:cli",
        ],
    },
    install_requires=[
        "lnd-grpc-client<1,>=0.3.39",
        "click<9,>=8.0.3",
    ],
    extras_require={
        "tests": [
            "pytest<7,>=6.2.5",
            "black<23,>=22.1.0",
            "isort<6,>=5.10.1",
        ],
        "irc": [
            "bottom<3,>=2.2.0",
        ],
        "mastodon": [
            "atoot @ git+https://git@github.com/valcanobacon/atoot@1.0.2#egg=atoot",
        ],
        "matrix": [
            "matrix-nio<1,>=0.19.0",
        ],
    },
)
