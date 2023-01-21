from unittest.mock import sentinel

from src.matrix import _get, _new_message


def test_get():
    data = {"a": sentinel.value}
    assert _get(data, "a") is sentinel.value
    assert _get(data, "a", "={a}=") == f"={sentinel.value}="
    assert _get(data, "a", lambda k, v: f"{k}={v}") == f"a={sentinel.value}"
    assert _get(data, "b") is None
    assert _get(data, "b", "={a}=") is None
    assert _get(data, "b", lambda k, v: f"{k}={v}") is None
    assert _get(data, "b", default=sentinel.default) is sentinel.default
    assert _get(data, "b", "={a}=", default=sentinel.default) is sentinel.default
    assert (
        _get(data, "b", lambda k, v: f"{k}={v}", default=sentinel.default)
        is sentinel.default
    )


def test_new_message_all():
    data = dict(
        sender_name="Ben",
        podcast="Boost Bots",
        episode="#0 Hello World",
        message="That was amazing",
        app_name="BoostCLI",
        ts="1000",
    )
    m = _new_message(data, 1234)
    assert (
        m
        == '🧛🧛 [Boost Bots] [#0 Hello World] Ben boosted 1234 sats saying "That was amazing" @0:16:40 via BoostCLI'
    )


def test_new_message_parts():
    m = _new_message(dict(), 1234)
    assert m == "🧛🧛 Anonymous boosted 1234 sats"
    m = _new_message(dict(sender_name="Ben"), 1234)
    assert m == "🧛🧛 Ben boosted 1234 sats"
    m = _new_message(dict(podcast="Boost Bots"), 1234)
    assert m == "🧛🧛 [Boost Bots] Anonymous boosted 1234 sats"
    m = _new_message(dict(episode="#0 Hello World"), 1234)
    assert m == "🧛🧛 [#0 Hello World] Anonymous boosted 1234 sats"
    m = _new_message(dict(episode="#0 Hello World"), 1234)
    assert m == "🧛🧛 [#0 Hello World] Anonymous boosted 1234 sats"
    m = _new_message(dict(message="That was amazing!!!"), 1234)
    assert m == '🧛🧛 Anonymous boosted 1234 sats saying "That was amazing!!!"'
    m = _new_message(dict(app_name="BoostCLI"), 1234)
    assert m == "🧛🧛 Anonymous boosted 1234 sats via BoostCLI"
    m = _new_message(dict(ts="1000"), 1234)
    assert m == "🧛🧛 Anonymous boosted 1234 sats @0:16:40"
