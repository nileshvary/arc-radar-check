# Arc token check agent

A small command-line tool that checks a token on Arc and prints a JSON report.

## What it does

1. Validates the input as an EVM address (`0x` + 40 hex characters).
2. Fetches token metadata and the holder list from the Arc explorer (Blockscout API v2), with a
   10 second timeout and one retry.
3. Treats all token text (name, symbol, holder labels) as hostile: removes invisible and
   direction-changing Unicode and control characters, strips HTML/script markup, caps length at 64,
   and detects injection-style content.
4. Calculates holder count, each top holder's share and the top-10 share in code, using integer
   math on the raw balance strings. No AI or LLM is used anywhere.
5. Applies fixed risk rules:
   - `HOLDER_CONCENTRATION` - high if one wallet holds more than 50%; medium if the top 10 hold more than 80%
   - `METADATA_INJECTION` - high if injection-style content was detected
   - `LOW_HOLDER_COUNT` - medium if there are fewer than 50 holders
6. Prints JSON using the v0.1 schema from the root README (token, holders, risk_flags), plus a
   `telegram_summary` built from a template.

Code layout (`arc_agent/`): `validate.py`, `fetch.py`, `sanitize.py`, `analyze.py`, `summary.py`,
`main.py`, plus `config.py` (env vars) and `errors.py` (error codes and messages).

## Setup

Requires Python 3.11 or newer. The tool itself uses only the standard library; `pytest` is needed
for the tests.

```bash
cd agent
python -m venv .venv
.venv\Scripts\activate          # Windows;  macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
```

### Configuration

| Variable | Required | Meaning |
|---|---|---|
| `ARC_EXPLORER_URL` | no | Explorer base URL, https only. Default `https://explorer.arc.io`. |
| `ARC_CHAIN_ID` | no | Chain ID reported in the output. Default `5042` (Arc mainnet). |
| `ARC_CHAIN_NAME` | no | Chain name reported in the output. Default `Arc`. |
| `ARC_EXPLORER_API_KEY` | no | Blockscout API key. Sent as the `apikey` query parameter only if set. |

Values are read from the environment, or from a `.env` file in the folder you run from. `.env` is
git-ignored. There are no keys or secrets in the code.

## How to run

```bash
cd agent
python -m arc_agent.main <token_address>
```

The JSON report is printed to stdout. Exit code is `0` for `status: ok` and `1` for `status: error`.

### Known limitation: mainnet explorer blocks scripts

`https://explorer.arc.io` currently answers non-browser clients with a Cloudflare challenge page
(HTTP 403). The tool does not try to get around this. It returns:

```json
{
  "schema_version": "0.1",
  "status": "error",
  "error": {
    "code": "EXPLORER_UNAVAILABLE",
    "message": "The Arc explorer refused the request or is unavailable."
  }
}
```

For a live run, use the Arc testnet explorer, which runs the same Blockscout API and is open:

```bash
# macOS / Linux
export ARC_EXPLORER_URL=https://explorer.testnet.arc.io ARC_CHAIN_ID=5042002 ARC_CHAIN_NAME="Arc Testnet"
python -m arc_agent.main 0x3600000000000000000000000000000000000000
```

```bash
# Windows PowerShell
$env:ARC_EXPLORER_URL = "https://explorer.testnet.arc.io"
$env:ARC_CHAIN_ID = "5042002"
$env:ARC_CHAIN_NAME = "Arc Testnet"
python -m arc_agent.main 0x3600000000000000000000000000000000000000
```

The `chain` block in the output comes from `ARC_CHAIN_NAME` and `ARC_CHAIN_ID` (defaults `Arc` and
`5042`). The tool does not ask the explorer which chain it serves, so set these to match the
explorer you point at. `5042002` is the Arc testnet chain ID from third-party documentation; check
it against the official Arc docs before relying on it.

If the explorer operator provides an API key or an allow-listed endpoint, set
`ARC_EXPLORER_API_KEY` and/or `ARC_EXPLORER_URL`.

## Example output

Live testnet run for `0x3600000000000000000000000000000000000000` (top holders shortened here):

```json
{
  "schema_version": "0.1",
  "status": "ok",
  "chain": { "name": "Arc Testnet", "chain_id": 5042002 },
  "token": {
    "address": "0x3600000000000000000000000000000000000000",
    "name": "USDC",
    "symbol": "USDC",
    "decimals": 6,
    "total_supply": "317482413450001083"
  },
  "holders": {
    "count": 4984308,
    "top10_share_pct": 99.65,
    "top_holders": [
      { "address": "0x4E42177AB52202Ced872A5EF661dfc4794bB37bF", "share_pct": 78.17, "label": null },
      { "address": "0x591e17159fB5385bDC254Af2997554303F844cc7", "share_pct": 14.61, "label": null }
    ]
  },
  "risk_flags": [
    {
      "code": "HOLDER_CONCENTRATION",
      "severity": "high",
      "title": "One wallet holds 78.17% of supply",
      "explanation": "A single wallet controls more than half of all tokens and could move the price sharply by selling."
    }
  ],
  "telegram_summary": "Token 0x3600…0000 has 4984308 holders. One wallet holds 78.17% of supply."
}
```

Hostile token (from the offline fixture) - the summary uses only numbers and fixed wording:

```
Token 0x7777…7777 has 3 holders. One wallet holds 97.50% of supply. Warning: the token's name, symbol and holder labels contain text aimed at automated tools, and very few wallets hold this token.
```

### Notes on the numbers

- `total_supply` is the raw on-chain value as a string (not divided by `decimals`).
- `share_pct` values are rounded down to two decimals. Thresholds (50%, 80%) are checked on the
  exact integers, not on the rounded values.
- `holders.count` is the explorer's `holders_count`. `top_holders` is the 10 largest balances from
  the first page of the holder list.
- `label` is the explorer's name or first public tag for that address, sanitized, or `null`.

### Error codes

| Code | When |
|---|---|
| `INVALID_ADDRESS` | Input is not `0x` + 40 hex characters (no request is made) |
| `TOKEN_NOT_FOUND` | Explorer returned 404 for the token |
| `EXPLORER_TIMEOUT` | No response within 10 s, twice |
| `EXPLORER_UNAVAILABLE` | Blocked (403 / challenge page), 5xx after one retry, connection failure, non-JSON reply |
| `BAD_RESPONSE` | JSON arrived but not in the expected shape |
| `CONFIG_ERROR` | `ARC_EXPLORER_URL` is not an https URL, or `ARC_CHAIN_ID` / `ARC_CHAIN_NAME` is invalid |

## How to run the tests

```bash
cd agent
python -m pytest -q
```

Tests are offline and use the files in `tests/fixtures/`. The hostile fixtures contain the exact
strings from `samples/check-hostile.json` in the repo root.

### Optional: real mainnet fixtures

Because mainnet blocks scripts, real mainnet responses can only be saved by hand from a browser.
Open each URL and save the JSON into `tests/fixtures/` under the given name:

| Open in browser | Save as |
|---|---|
| https://explorer.arc.io/api/v2/tokens/0x3600000000000000000000000000000000000000 | `mainnet_token_usdc.json` |
| https://explorer.arc.io/api/v2/tokens/0x3600000000000000000000000000000000000000/holders | `mainnet_holders_usdc.json` |

`test_main.py::test_mainnet_fixtures_parse_if_present` runs against these files when both exist and
is skipped otherwise. Both files are included in this branch (saved on 7 October 2026); the field
names the tool reads are the same on mainnet and testnet.

## Security

See [THREAT_MODEL.md](THREAT_MODEL.md).

## Out of scope

Burns and buybacks, manipulation detection, verdict or score, Telegram bot, x402 payments,
deployment, and any web page or front end.
