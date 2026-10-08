"""End-to-end tests of the CLI pipeline, offline, using fixture files."""

import json
import re

import pytest

from arc_agent import main as cli
from arc_agent.sanitize import MAX_LENGTH

from conftest import FIXTURES, load_fixture

NORMAL = "0x1111111111111111111111111111111111111111"
HOSTILE = "0x7777777777777777777777777777777777777777"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("ARC_EXPLORER_URL", raising=False)
    monkeypatch.delenv("ARC_EXPLORER_API_KEY", raising=False)
    monkeypatch.delenv("ARC_CHAIN_ID", raising=False)
    monkeypatch.delenv("ARC_CHAIN_NAME", raising=False)


def fixture_get(prefix):
    """Fake HTTP layer that serves token_<prefix>.json / holders_<prefix>.json."""

    def get(url, timeout):
        name = "holders" if url.endswith("/holders") else "token"
        return 200, (FIXTURES / f"{name}_{prefix}.json").read_bytes()

    return get


def codes(result):
    return [(f["code"], f["severity"]) for f in result["risk_flags"]]


# --- normal token -----------------------------------------------------------


def test_normal_token_output():
    result = cli.run(NORMAL, fixture_get("normal"))
    assert result["schema_version"] == "0.1"
    assert result["status"] == "ok"
    assert result["chain"] == {"name": "Arc", "chain_id": 5042}
    assert result["token"] == {
        "address": NORMAL,
        "name": "Sample Token",
        "symbol": "SMPL",
        "decimals": 18,
        "total_supply": "1000000000000000000000000000",
    }
    holders = result["holders"]
    assert holders["count"] == 1284
    assert holders["top10_share_pct"] == 58.4
    assert [h["share_pct"] for h in holders["top_holders"]] == [21.3, 12.1, 8.7, 6.2, 4.0, 2.0, 1.5, 1.0, 0.9, 0.7]
    assert [h["label"] for h in holders["top_holders"]][:5] == ["liquidity_pool", "deployer", None, None, "burn_address"]
    assert result["risk_flags"] == []
    assert result["telegram_summary"] == (
        "Token 0x1111…1111 has 1284 holders. The top 10 wallets hold 58.40% of supply."
    )


def test_output_has_only_the_agreed_fields():
    result = cli.run(NORMAL, fixture_get("normal"))
    assert set(result) == {"schema_version", "status", "chain", "token", "holders", "risk_flags", "telegram_summary"}
    assert isinstance(result["token"]["total_supply"], str)
    assert set(result["holders"]["top_holders"][0]) == {"address", "share_pct", "label"}
    for flag in result["risk_flags"]:
        assert set(flag) == {"code", "severity", "title", "explanation"}


def test_chain_comes_from_env(monkeypatch):
    monkeypatch.setenv("ARC_CHAIN_ID", "5042002")
    monkeypatch.setenv("ARC_CHAIN_NAME", "Arc Testnet")
    result = cli.run(NORMAL, fixture_get("normal"))
    assert result["chain"] == {"name": "Arc Testnet", "chain_id": 5042002}


@pytest.mark.parametrize("value", ["abc", "-1", "0", "5042.5", "0x13b2"])
def test_bad_chain_id_is_config_error(monkeypatch, value):
    monkeypatch.setenv("ARC_CHAIN_ID", value)
    assert_error(cli.run(NORMAL, fixture_get("normal")), "CONFIG_ERROR")


# --- hostile token ----------------------------------------------------------


def test_fixture_uses_the_strings_from_the_sample_file():
    sample = json.loads((FIXTURES.parents[2] / "samples" / "check-hostile.json").read_text(encoding="utf-8"))
    token = load_fixture("token_hostile.json")
    items = load_fixture("holders_hostile.json")["items"]
    assert token["name"] == sample["token"]["name"]
    assert token["symbol"] == sample["token"]["symbol"]
    assert [i["address"]["name"] for i in items] == [h["label"] for h in sample["holders"]["top_holders"]]


def test_hostile_numbers_are_identical_to_the_clean_twin():
    hostile = cli.run(HOSTILE, fixture_get("hostile"))
    twin = cli.run(HOSTILE, fixture_get("twin"))

    def numbers(result):
        holders = result["holders"]
        return (
            result["token"]["decimals"],
            result["token"]["total_supply"],
            holders["count"],
            holders["top10_share_pct"],
            [(h["address"], h["share_pct"]) for h in holders["top_holders"]],
        )

    assert numbers(hostile) == numbers(twin)
    assert hostile["holders"]["top10_share_pct"] == 100.0
    assert [h["share_pct"] for h in hostile["holders"]["top_holders"]] == [97.5, 2.4, 0.1]

    def without_injection(result):
        return [f for f in result["risk_flags"] if f["code"] != "METADATA_INJECTION"]

    assert without_injection(hostile) == without_injection(twin)


def test_hostile_token_raises_metadata_injection():
    hostile = cli.run(HOSTILE, fixture_get("hostile"))
    twin = cli.run(HOSTILE, fixture_get("twin"))
    assert codes(hostile) == [
        ("HOLDER_CONCENTRATION", "high"),
        ("METADATA_INJECTION", "high"),
        ("LOW_HOLDER_COUNT", "medium"),
    ]
    assert ("METADATA_INJECTION", "high") not in codes(twin)


def test_hostile_summary_contains_no_token_text():
    summary = cli.run(HOSTILE, fixture_get("hostile"))["telegram_summary"]
    lowered = summary.lower()
    for scam in ("ignore", "previous instructions", "safe", "official", "verified", "circle", "trust", "evil", "alert", "onerror"):
        assert scam not in lowered
    assert "<script>" not in lowered and "<" not in summary and ">" not in summary
    assert not re.search(r"https?:|://|www\.|javascript:", lowered)
    assert "0x7777…7777" in summary
    assert summary.count(". ") <= 2


def test_flag_text_is_never_copied_from_token_data():
    result = cli.run(HOSTILE, fixture_get("hostile"))
    for flag in result["risk_flags"]:
        text = (flag["title"] + " " + flag["explanation"]).lower()
        for scam in ("ignore all", "safe", "circle", "trust_me", "evil", "<", ">"):
            assert scam not in text


def test_hostile_text_fields_are_sanitized_in_the_output():
    result = cli.run(HOSTILE, fixture_get("hostile"))
    labels = [h["label"] for h in result["holders"]["top_holders"]]
    assert result["token"]["symbol"] is None  # was only a <script> block
    assert "<" not in result["token"]["name"] and "onerror" not in result["token"]["name"]
    assert len(labels[0]) == MAX_LENGTH  # long label capped
    assert labels[1] == "evil-label"  # U+202E removed
    assert labels[2] is None  # empty label -> null
    assert "‮" not in json.dumps(result, ensure_ascii=False)


# --- errors -----------------------------------------------------------------


def assert_error(result, code):
    assert set(result) == {"schema_version", "status", "error"}
    assert result["status"] == "error"
    assert result["error"]["code"] == code
    assert result["error"]["message"]


@pytest.mark.parametrize("value", ["nonsense", "0x123", "", HOSTILE + "0", "<script>alert(1)</script>"])
def test_invalid_address_makes_no_request(value):
    def get(url, timeout):
        raise AssertionError("no network call expected")

    result = cli.run(value, get)
    assert_error(result, "INVALID_ADDRESS")
    assert value == "" or value not in result["error"]["message"]


def test_token_not_found():
    result = cli.run(NORMAL, lambda url, timeout: (404, b'{"message":"Not found"}'))
    assert_error(result, "TOKEN_NOT_FOUND")


def test_timeout_after_one_retry():
    calls = []

    def get(url, timeout):
        calls.append(url)
        raise TimeoutError

    assert_error(cli.run(NORMAL, get), "EXPLORER_TIMEOUT")
    assert len(calls) == 2


def test_cloudflare_block_is_explorer_unavailable():
    result = cli.run(NORMAL, lambda url, timeout: (403, b"<title>Just a moment...</title>"))
    assert_error(result, "EXPLORER_UNAVAILABLE")


def test_cli_prints_json_and_sets_exit_code(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # no .env here
    assert cli.main(["not-an-address"]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_ADDRESS"
    assert cli.main([]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"


# --- optional mainnet fixtures saved from a browser -------------------------


def test_mainnet_fixtures_parse_if_present():
    token_file = FIXTURES / "mainnet_token_usdc.json"
    holders_file = FIXTURES / "mainnet_holders_usdc.json"
    if not (token_file.is_file() and holders_file.is_file()):
        pytest.skip("mainnet fixtures not saved yet (see README)")

    def get(url, timeout):
        return 200, (holders_file if url.endswith("/holders") else token_file).read_bytes()

    result = cli.run("0x3600000000000000000000000000000000000000", get)
    assert result["status"] == "ok", result
    assert result["chain"] == {"name": "Arc", "chain_id": 5042}
    assert result["token"]["decimals"] == 6
    assert result["holders"]["count"] > 0
    assert len(result["holders"]["top_holders"]) == 10
    assert 0 <= result["holders"]["top10_share_pct"] <= 100
    shares = [h["share_pct"] for h in result["holders"]["top_holders"]]
    assert shares == sorted(shares, reverse=True)
