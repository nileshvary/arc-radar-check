import pytest

from arc_agent.analyze import build_flags, compute_stats, format_pct, to_int
from arc_agent.errors import AgentError

from conftest import load_fixture


def addr(n):
    return f"0x{n:040x}"


def holders(*values):
    return [{"address": {"hash": addr(i + 1)}, "value": str(v)} for i, v in enumerate(values)]


def token(supply, count=None):
    data = {"total_supply": str(supply)}
    if count is not None:
        data["holders_count"] = str(count)
    return data


def codes(flags):
    return [(f["code"], f["severity"]) for f in flags]


def test_normal_token_numbers():
    stats = compute_stats(load_fixture("token_normal.json"), load_fixture("holders_normal.json")["items"])
    assert stats.count == 1284
    assert stats.top10_share_bp == 5840
    assert [h.share_bp for h in stats.top_holders] == [2130, 1210, 870, 620, 400, 200, 150, 100, 90, 70]
    assert len(stats.top_holders) == 10
    assert build_flags(stats, False) == []


def test_only_top_ten_are_counted_and_order_is_not_trusted():
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]  # ascending on purpose
    stats = compute_stats(token(1000, 500), holders(*values))
    assert [h.share_bp for h in stats.top_holders][:2] == [120, 110]
    assert stats.top10_share_bp == sum(range(3, 13)) * 10


def test_huge_balances_keep_full_precision():
    supply = 3 * 10**40
    stats = compute_stats(token(supply, 100), holders(10**40))
    assert stats.top_holders[0].share_bp == 3333  # floor of 33.33...%
    assert stats.total_supply == supply


@pytest.mark.parametrize(
    "largest, expected",
    [(500, []), (501, [("HOLDER_CONCENTRATION", "high")])],
)
def test_single_wallet_threshold_is_strictly_over_50(largest, expected):
    stats = compute_stats(token(1000, 500), holders(largest))
    assert codes(build_flags(stats, False)) == expected


@pytest.mark.parametrize(
    "each, expected",
    [(80, []), (81, [("HOLDER_CONCENTRATION", "medium")])],
)
def test_top10_threshold_is_strictly_over_80(each, expected):
    stats = compute_stats(token(1000, 500), holders(*[each] * 10))
    assert codes(build_flags(stats, False)) == expected


def test_single_wallet_rule_wins_over_top10_rule():
    stats = compute_stats(token(1000, 500), holders(600, 300))
    flags = build_flags(stats, False)
    assert codes(flags) == [("HOLDER_CONCENTRATION", "high")]
    assert flags[0]["title"] == "One wallet holds 60.00% of supply"


@pytest.mark.parametrize("count, flagged", [(49, True), (50, False), (0, True)])
def test_low_holder_count_threshold(count, flagged):
    stats = compute_stats(token(10**6, count), holders(1))
    assert (("LOW_HOLDER_COUNT", "medium") in codes(build_flags(stats, False))) is flagged


def test_holder_count_falls_back_to_listed_holders():
    stats = compute_stats(token(1000), holders(1, 1, 1))
    assert stats.count == 3


def test_injection_flag_depends_only_on_the_boolean():
    stats = compute_stats(token(10**6, 500), holders(1))
    assert codes(build_flags(stats, True)) == [("METADATA_INJECTION", "high")]
    assert build_flags(stats, False) == []


@pytest.mark.parametrize("supply", ["0", "abc", "-5", "1.5", "", None, True, "１２"])
def test_bad_total_supply_is_bad_response(supply):
    with pytest.raises(AgentError) as exc:
        compute_stats({"total_supply": supply}, holders(1))
    assert exc.value.code == "BAD_RESPONSE"


@pytest.mark.parametrize(
    "item",
    [
        {"address": {"hash": addr(1)}, "value": "1e18"},
        {"address": {"hash": "<script>"}, "value": "1"},
        {"address": None, "value": "1"},
        {"value": "1"},
        "nope",
    ],
)
def test_bad_holder_item_is_bad_response(item):
    with pytest.raises(AgentError) as exc:
        compute_stats(token(1000, 5), [item])
    assert exc.value.code == "BAD_RESPONSE"


def test_format_pct_and_to_int():
    assert format_pct(9750) == "97.50"
    assert format_pct(5) == "0.05"
    assert format_pct(10000) == "100.00"
    assert to_int("0012") == 12
