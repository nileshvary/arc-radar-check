import json

import pytest

from arc_agent import fetch
from arc_agent.errors import AgentError

ADDRESS = "0x1111111111111111111111111111111111111111"


class FakeGet:
    """Replays a list of outcomes: (status, body) tuples or exceptions."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.urls = []

    def __call__(self, url, timeout):
        self.urls.append(url)
        assert timeout == fetch.TIMEOUT_SECONDS
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def ok(data):
    return 200, json.dumps(data).encode()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("ARC_EXPLORER_URL", raising=False)
    monkeypatch.delenv("ARC_EXPLORER_API_KEY", raising=False)


def test_fetch_token_uses_default_url_without_key():
    get = FakeGet(ok({"name": "x"}))
    assert fetch.fetch_token(ADDRESS, get) == {"name": "x"}
    assert get.urls == [f"https://explorer.arc.io/api/v2/tokens/{ADDRESS}"]


def test_explorer_url_comes_from_env(monkeypatch):
    monkeypatch.setenv("ARC_EXPLORER_URL", "https://explorer.testnet.arc.io/")
    get = FakeGet(ok({"items": []}))
    assert fetch.fetch_holders(ADDRESS, get) == []
    assert get.urls == [f"https://explorer.testnet.arc.io/api/v2/tokens/{ADDRESS}/holders"]


def test_api_key_is_sent_only_when_set(monkeypatch):
    monkeypatch.setenv("ARC_EXPLORER_API_KEY", "test-key")
    get = FakeGet(ok({}))
    fetch.fetch_token(ADDRESS, get)
    assert get.urls[0].endswith("?apikey=test-key")

    monkeypatch.setenv("ARC_EXPLORER_API_KEY", "   ")
    get = FakeGet(ok({}))
    fetch.fetch_token(ADDRESS, get)
    assert "apikey" not in get.urls[0]


def test_non_https_explorer_url_is_rejected(monkeypatch):
    monkeypatch.setenv("ARC_EXPLORER_URL", "http://explorer.arc.io")
    with pytest.raises(AgentError) as exc:
        fetch.fetch_token(ADDRESS, FakeGet())
    assert exc.value.code == "CONFIG_ERROR"


def test_404_is_token_not_found_without_retry():
    get = FakeGet((404, b'{"message":"Not found"}'))
    with pytest.raises(AgentError) as exc:
        fetch.fetch_token(ADDRESS, get)
    assert exc.value.code == "TOKEN_NOT_FOUND"
    assert len(get.urls) == 1


def test_timeout_is_retried_exactly_once_then_reported():
    get = FakeGet(TimeoutError(), TimeoutError())
    with pytest.raises(AgentError) as exc:
        fetch.fetch_token(ADDRESS, get)
    assert exc.value.code == "EXPLORER_TIMEOUT"
    assert len(get.urls) == 2


def test_timeout_then_success_recovers():
    get = FakeGet(TimeoutError(), ok({"name": "x"}))
    assert fetch.fetch_token(ADDRESS, get) == {"name": "x"}


def test_server_error_is_retried_once():
    get = FakeGet((502, b""), (503, b""))
    with pytest.raises(AgentError) as exc:
        fetch.fetch_token(ADDRESS, get)
    assert exc.value.code == "EXPLORER_UNAVAILABLE"
    assert len(get.urls) == 2


def test_cloudflare_challenge_is_unavailable_and_not_retried():
    get = FakeGet((403, b"<!DOCTYPE html><title>Just a moment...</title>"))
    with pytest.raises(AgentError) as exc:
        fetch.fetch_token(ADDRESS, get)
    assert exc.value.code == "EXPLORER_UNAVAILABLE"
    assert len(get.urls) == 1


def test_html_body_with_200_is_unavailable():
    with pytest.raises(AgentError) as exc:
        fetch.fetch_token(ADDRESS, FakeGet((200, b"<html>nope</html>")))
    assert exc.value.code == "EXPLORER_UNAVAILABLE"


@pytest.mark.parametrize("payload", [[1, 2], {"items": "nope"}, {}])
def test_unexpected_holders_shape_is_bad_response(payload):
    with pytest.raises(AgentError) as exc:
        fetch.fetch_holders(ADDRESS, FakeGet(ok(payload)))
    assert exc.value.code == "BAD_RESPONSE"


def test_error_message_never_contains_url_or_key(monkeypatch):
    monkeypatch.setenv("ARC_EXPLORER_API_KEY", "test-key")
    with pytest.raises(AgentError) as exc:
        fetch.fetch_token(ADDRESS, FakeGet((403, b"")))
    assert "test-key" not in exc.value.message
    assert "http" not in exc.value.message
