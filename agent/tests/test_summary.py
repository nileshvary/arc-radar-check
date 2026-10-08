import itertools
import re

from arc_agent.analyze import build_flags, compute_stats
from arc_agent.summary import build_summary, short_address

ADDRESS = "0x7777777777777777777777777777777777777777"


def stats_for(largest, count):
    token = {"total_supply": "1000", "holders_count": str(count)}
    holders = [{"address": {"hash": "0x" + "1" * 40}, "value": str(largest)}]
    return compute_stats(token, holders)


def sentence_count(text):
    return len(re.findall(r"[.!?](?:\s|$)", text.replace("97.50", "97_50")))


def test_short_address():
    assert short_address(ADDRESS) == "0x7777…7777"


def test_example_from_the_brief():
    stats = stats_for(975, 3)
    flags = build_flags(stats, True)
    assert build_summary(ADDRESS, stats, flags, {"name"}) == (
        "Token 0x7777…7777 has 3 holders. One wallet holds 97.50% of supply. "
        "Warning: the token's name contains text aimed at automated tools, "
        "and very few wallets hold this token."
    )


def test_quiet_token_has_two_sentences():
    stats = stats_for(100, 1284)
    assert build_summary(ADDRESS, stats, build_flags(stats, False), set()) == (
        "Token 0x7777…7777 has 1284 holders. The top 10 wallets hold 10.00% of supply."
    )


def test_every_template_branch_is_short_plain_and_never_says_safe():
    field_sets = [set(c) for n in range(4) for c in itertools.combinations(["name", "symbol", "label"], n)]
    for largest, count, fields in itertools.product([100, 975], [1, 3, 1284], field_sets):
        stats = stats_for(largest, count)
        text = build_summary(ADDRESS, stats, build_flags(stats, bool(fields)), fields)
        assert "safe" not in text.lower()
        assert not re.search(r"https?:|://|www\.|[<>\[\]`*_]", text)
        assert text.count(". ") <= 2 and text.endswith(".")
        assert len(text) < 240


def test_field_wording():
    stats = stats_for(100, 1284)
    flags = build_flags(stats, True)
    assert "the token's symbol contains text" in build_summary(ADDRESS, stats, flags, {"symbol"})
    assert "the token's holder labels contain text" in build_summary(ADDRESS, stats, flags, {"label"})
    assert "the token's name, symbol and holder labels contain text" in build_summary(
        ADDRESS, stats, flags, {"name", "symbol", "label"}
    )
