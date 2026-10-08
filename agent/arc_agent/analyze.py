"""Holder statistics and risk flags.

Everything here is computed with integer math on the raw balance strings.
No token text is read in this module, so hostile metadata cannot change a number.
Flag titles and explanations are written here and only ever formatted with
numbers computed here.
"""

from dataclasses import dataclass

from .errors import AgentError
from .validate import is_evm_address

TOP_N = 10
SINGLE_WALLET_LIMIT_PCT = 50
TOP10_LIMIT_PCT = 80
MIN_HOLDERS = 50


@dataclass(frozen=True)
class HolderShare:
    address: str
    share_bp: int  # hundredths of a percent: 9750 == 97.50%


@dataclass(frozen=True)
class HolderStats:
    count: int
    total_supply: int
    top_holders: tuple[HolderShare, ...]
    top10_share_bp: int
    largest_share_bp: int
    single_wallet_over_limit: bool
    top10_over_limit: bool


def to_int(value):
    """Parse a non-negative integer from an explorer value (string or int)."""
    if isinstance(value, bool):
        raise AgentError("BAD_RESPONSE")
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    raise AgentError("BAD_RESPONSE")


def format_pct(share_bp):
    """9750 -> '97.50' without going through floating point."""
    return f"{share_bp // 100}.{share_bp % 100:02d}"


def pct_number(share_bp):
    """JSON number with two decimals for the output schema."""
    return share_bp / 100


def holder_address(item):
    address = item.get("address") if isinstance(item, dict) else None
    hash_ = address.get("hash") if isinstance(address, dict) else None
    if not is_evm_address(hash_):
        raise AgentError("BAD_RESPONSE")
    return hash_


def compute_stats(token, holders):
    """Build HolderStats from the raw token dict and the raw holder items."""
    supply = to_int(token.get("total_supply"))
    if supply == 0:
        raise AgentError("BAD_RESPONSE")

    balances = []
    for item in holders:
        address = holder_address(item)  # also rejects items that are not objects
        balances.append((to_int(item.get("value")), address))
    # Do not rely on the explorer's ordering.
    balances.sort(key=lambda pair: pair[0], reverse=True)
    top = balances[:TOP_N]

    top10_total = sum(value for value, _ in top)
    largest = top[0][0] if top else 0
    reported = token.get("holders_count")
    count = to_int(reported) if reported is not None else len(balances)

    return HolderStats(
        count=count,
        total_supply=supply,
        top_holders=tuple(HolderShare(address, value * 10000 // supply) for value, address in top),
        top10_share_bp=top10_total * 10000 // supply,
        largest_share_bp=largest * 10000 // supply,
        single_wallet_over_limit=largest * 100 > supply * SINGLE_WALLET_LIMIT_PCT,
        top10_over_limit=top10_total * 100 > supply * TOP10_LIMIT_PCT,
    )


def _flag(code, severity, title, explanation):
    return {"code": code, "severity": severity, "title": title, "explanation": explanation}


def build_flags(stats, injection_detected):
    """Apply the fixed rules. `injection_detected` is a plain boolean."""
    flags = []
    if stats.single_wallet_over_limit:
        flags.append(
            _flag(
                "HOLDER_CONCENTRATION",
                "high",
                f"One wallet holds {format_pct(stats.largest_share_bp)}% of supply",
                "A single wallet controls more than half of all tokens and could move the price sharply by selling.",
            )
        )
    elif stats.top10_over_limit:
        flags.append(
            _flag(
                "HOLDER_CONCENTRATION",
                "medium",
                f"Top 10 wallets hold {format_pct(stats.top10_share_bp)}% of supply",
                "A small group of wallets holds more than 80% of all tokens and could move the price sharply by selling.",
            )
        )
    if injection_detected:
        flags.append(
            _flag(
                "METADATA_INJECTION",
                "high",
                "Token text contains manipulation attempts",
                "The token's name, symbol or holder labels contain markup, hidden characters or wording "
                "designed to mislead people or automated tools.",
            )
        )
    if stats.count < MIN_HOLDERS:
        flags.append(
            _flag(
                "LOW_HOLDER_COUNT",
                "medium",
                f"Only {stats.count} wallets hold this token" if stats.count != 1 else "Only 1 wallet holds this token",
                "Tokens with fewer than 50 holders are easy for a few wallets to control.",
            )
        )
    return flags
