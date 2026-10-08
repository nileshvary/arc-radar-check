"""Configuration from environment variables (optionally via a local .env file)."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from .errors import AgentError

DEFAULT_EXPLORER_URL = "https://explorer.arc.io"
DEFAULT_CHAIN_NAME = "Arc"
DEFAULT_CHAIN_ID = 5042
_MAX_CHAIN_NAME = 32


def load_dotenv(path=".env"):
    """Load KEY=VALUE lines from a .env file without overriding real env vars."""
    file = Path(path)
    if not file.is_file():
        return
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def explorer_url():
    url = (os.environ.get("ARC_EXPLORER_URL") or DEFAULT_EXPLORER_URL).strip().rstrip("/")
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc:
        raise AgentError("CONFIG_ERROR")
    return url


def api_key():
    """Optional explorer API key; None when not configured."""
    return (os.environ.get("ARC_EXPLORER_API_KEY") or "").strip() or None


def chain():
    """Chain block for the output, from ARC_CHAIN_NAME / ARC_CHAIN_ID."""
    name = (os.environ.get("ARC_CHAIN_NAME") or DEFAULT_CHAIN_NAME).strip()
    raw_id = (os.environ.get("ARC_CHAIN_ID") or str(DEFAULT_CHAIN_ID)).strip()
    if not (raw_id.isascii() and raw_id.isdigit() and int(raw_id) > 0):
        raise AgentError("CONFIG_ERROR")
    if not name or len(name) > _MAX_CHAIN_NAME or not name.isprintable():
        raise AgentError("CONFIG_ERROR")
    return {"name": name, "chain_id": int(raw_id)}
