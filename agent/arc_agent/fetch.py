"""Fetch token metadata and holders from the Arc explorer (Blockscout API v2).

Uses a timeout and exactly one retry. All failures are mapped to AgentError
codes; error messages never include the request URL or any response text.
"""

import json
import socket
import urllib.error
import urllib.request
from urllib.parse import urlencode

from . import config
from .errors import AgentError

TIMEOUT_SECONDS = 10
RETRIES = 1
_MAX_BODY_BYTES = 5 * 1024 * 1024
_USER_AGENT = "arc-agent/0.1"


def http_get(url, timeout):
    """Return (status, body_bytes). Raises TimeoutError or OSError on network failure."""
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(_MAX_BODY_BYTES)
    except urllib.error.HTTPError as exc:
        return exc.code, b""
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise TimeoutError from None
        raise OSError("connection failed") from None


def _build_url(path):
    url = f"{config.explorer_url()}/api/v2/{path}"
    key = config.api_key()
    if key:
        url += "?" + urlencode({"apikey": key})
    return url


def _get_json(path, get):
    url = _build_url(path)
    failure = "EXPLORER_UNAVAILABLE"
    for _attempt in range(1 + RETRIES):
        try:
            status, body = get(url, TIMEOUT_SECONDS)
        except TimeoutError:
            failure = "EXPLORER_TIMEOUT"
            continue
        except OSError:
            failure = "EXPLORER_UNAVAILABLE"
            continue
        if status >= 500:
            failure = "EXPLORER_UNAVAILABLE"
            continue
        if status == 404:
            raise AgentError("TOKEN_NOT_FOUND")
        if status != 200:
            # Includes 403 from a bot-protection challenge page. Not retried, not bypassed.
            raise AgentError("EXPLORER_UNAVAILABLE")
        try:
            data = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            raise AgentError("EXPLORER_UNAVAILABLE") from None
        if not isinstance(data, dict):
            raise AgentError("BAD_RESPONSE")
        return data
    raise AgentError(failure)


def fetch_token(address, get=http_get):
    """Token metadata dict. `address` must already be validated."""
    return _get_json(f"tokens/{address}", get)


def fetch_holders(address, get=http_get):
    """First page of holders (largest balances first) as a list of dicts."""
    items = _get_json(f"tokens/{address}/holders", get).get("items")
    if not isinstance(items, list):
        raise AgentError("BAD_RESPONSE")
    return items
