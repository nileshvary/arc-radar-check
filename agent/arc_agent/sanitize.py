"""Sanitize untrusted token text (name, symbol, holder labels).

Every string that comes from the explorer is treated as hostile. This module
returns a cleaned plain-text value plus a boolean saying whether the raw value
looked like an attempt to manipulate a reader or an automated tool.
"""

import html
import re
import unicodedata
from dataclasses import dataclass

MAX_LENGTH = 64
_MAX_INPUT = 4096  # bound the work done on absurdly long inputs

_SCRIPT_BLOCK_RE = re.compile(r"<\s*(script|style)\b.*?(?:<\s*/\s*\1\s*>|$)", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]*>")
_TAG_START_RE = re.compile(r"<\s*[/!?]?\s*[a-z]", re.I)
_WHITESPACE_RE = re.compile(r"\s+")

_INJECTION_PATTERNS = [
    re.compile(p, re.I | re.S)
    for p in (
        r"(?<![a-z])(ignore|disregard|forget|override|bypass)(?![a-z]).{0,40}"
        r"(?<![a-z])(instructions?|prompts?|rules?|guidelines?)(?![a-z])",
        r"(?<![a-z])system\s+prompt(?![a-z])",
        r"(?<![a-z])you\s+are\s+now(?![a-z])",
        r"(?<![a-z])javascript\s*:",
        # Trust-claim words. Underscores and digits count as separators so
        # "OFFICIAL_SAFE_VERIFIED" is caught.
        r"(?<![a-z])(safe|verified|official)(?![a-z])",
    )
]


@dataclass(frozen=True)
class CleanText:
    text: str | None
    injection: bool


def _is_invisible(ch):
    # Cf = format (bidi overrides, zero-width chars, BOM); Cc = control;
    # Cs/Co/Cn = surrogates, private use, unassigned.
    return unicodedata.category(ch).startswith("C")


def _decode(raw):
    """Undo HTML entities and compatibility forms so nothing hides from the checks."""
    text = raw[:_MAX_INPUT]
    for _ in range(3):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    return unicodedata.normalize("NFKC", text)


def _drop_invisible(text):
    return "".join(" " if ch in "\t\n\r" else ch for ch in text if ch in "\t\n\r" or not _is_invisible(ch))


def detect_injection(raw):
    """True if the raw text contains hidden characters, markup or manipulation phrases."""
    if not isinstance(raw, str):
        return False
    decoded = _decode(raw)
    if any(unicodedata.category(ch) == "Cf" for ch in decoded):
        return True
    visible = _drop_invisible(decoded)
    if _TAG_START_RE.search(visible):
        return True
    return any(p.search(visible) for p in _INJECTION_PATTERNS)


def clean_text(raw):
    """Return CleanText(text, injection). text is None when nothing usable remains."""
    if not isinstance(raw, str):
        return CleanText(None, False)
    injection = detect_injection(raw)
    text = _drop_invisible(_decode(raw))
    text = _SCRIPT_BLOCK_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    text = text.replace("<", " ").replace(">", " ").replace("`", " ")
    text = _WHITESPACE_RE.sub(" ", text).strip()
    text = text[:MAX_LENGTH].rstrip()
    return CleanText(text or None, injection)
