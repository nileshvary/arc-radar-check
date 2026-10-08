"""Plain-text summary for Telegram.

Built only from fixed templates, the short token address, computed numbers and
the set of flags that fired. Token text (name, symbol, labels) is never used.
"""

from .analyze import format_pct

# Words chosen in code for the fields where injection was detected.
FIELD_WORDS = {"name": "name", "symbol": "symbol", "label": "holder labels"}


def short_address(address):
    return f"{address[:6]}…{address[-4:]}"


def _join(words):
    if len(words) == 1:
        return words[0]
    return ", ".join(words[:-1]) + " and " + words[-1]


def _injection_clause(fields):
    words = [FIELD_WORDS[f] for f in ("name", "symbol", "label") if f in fields]
    plural = len(words) > 1 or words == ["holder labels"]
    verb = "contain" if plural else "contains"
    return f"the token's {_join(words)} {verb} text aimed at automated tools"


def build_summary(address, stats, flags, injection_fields):
    """Return at most three short sentences."""
    codes = {flag["code"] for flag in flags}
    holders_word = "holder" if stats.count == 1 else "holders"
    sentences = [f"Token {short_address(address)} has {stats.count} {holders_word}."]

    if stats.single_wallet_over_limit:
        sentences.append(f"One wallet holds {format_pct(stats.largest_share_bp)}% of supply.")
    else:
        sentences.append(f"The top 10 wallets hold {format_pct(stats.top10_share_bp)}% of supply.")

    warnings = []
    if "METADATA_INJECTION" in codes and injection_fields:
        warnings.append(_injection_clause(injection_fields))
    if "LOW_HOLDER_COUNT" in codes:
        warnings.append("very few wallets hold this token")
    if warnings:
        sentences.append("Warning: " + ", and ".join(warnings) + ".")

    return " ".join(sentences)
