"""Command-line entry point: python -m arc_agent.main <token_address>"""

import json
import sys

from . import SCHEMA_VERSION, config
from .analyze import build_flags, compute_stats, holder_address, pct_number, to_int
from .errors import AgentError
from .fetch import fetch_holders, fetch_token, http_get
from .sanitize import clean_text
from .summary import build_summary
from .validate import require_evm_address


def _raw_label(item):
    """Pick the explorer's label for a holder, if any (still untrusted)."""
    address = item.get("address") or {}
    if address.get("name"):
        return address["name"]
    tags = address.get("public_tags")
    if isinstance(tags, list) and tags and isinstance(tags[0], dict):
        return tags[0].get("display_name")
    return None


def _error(code_error):
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "error": {"code": code_error.code, "message": code_error.message},
    }


def build_report(address, token, holders, chain):
    """Turn raw explorer data into the output document."""
    stats = compute_stats(token, holders)

    name = clean_text(token.get("name"))
    symbol = clean_text(token.get("symbol"))
    labels = {holder_address(item): clean_text(_raw_label(item)) for item in holders}

    injection_fields = set()
    if name.injection:
        injection_fields.add("name")
    if symbol.injection:
        injection_fields.add("symbol")
    if any(label.injection for label in labels.values()):
        injection_fields.add("label")

    flags = build_flags(stats, bool(injection_fields))
    decimals = token.get("decimals")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "chain": chain,
        "token": {
            "address": address,
            "name": name.text,
            "symbol": symbol.text,
            "decimals": to_int(decimals) if decimals is not None else None,
            "total_supply": str(stats.total_supply),
        },
        "holders": {
            "count": stats.count,
            "top10_share_pct": pct_number(stats.top10_share_bp),
            "top_holders": [
                {"address": h.address, "share_pct": pct_number(h.share_bp), "label": labels[h.address].text}
                for h in stats.top_holders
            ],
        },
        "risk_flags": flags,
        "telegram_summary": build_summary(address, stats, flags, injection_fields),
    }


def run(address, get=http_get):
    """Return the output document for an address; never raises for expected failures."""
    try:
        require_evm_address(address)
        chain = config.chain()
        token = fetch_token(address, get)
        holders = fetch_holders(address, get)
        return build_report(address, token, holders, chain)
    except AgentError as exc:
        return _error(exc)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    config.load_dotenv()
    result = run(args[0]) if len(args) == 1 else _error(AgentError("INVALID_ADDRESS"))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
