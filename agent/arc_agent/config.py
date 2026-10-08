"""Configuration from environment variables (optionally via a local .env file)."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from .errors import AgentError

DEFAULT_EXPLORER_URL = "https://explorer.arc.io"


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
