# Arc Radar Check - front-end test task

Test task for: front-end page for a pay-per-check token verification service on Arc.
Deadline: **Sunday 12 October 2026**
Budget: fixed price, max 3 hours ($90)

## What to build

One web page (Next.js) that:

1. Lets a user enter a token address on Arc mainnet (validate it as an EVM address before sending).
2. Calls the check endpoint and shows the result clearly for a non-technical user:
   verdict, holder distribution, burn/buyback verification and risk flags.
3. Lets the user connect a wallet on Arc mainnet and shows their USDC balance.
4. Shows a clear placeholder for the "Pay per check" button (the x402 payment flow is built by us).
5. Is mobile-first and works in light and dark mode.

Until the endpoint is live, work against the files in `samples/`. Make the endpoint URL configurable via an environment variable.

## States the page must handle

| Sample file | Situation |
|---|---|
| `samples/check-ok.json` | Normal result |
| `samples/check-hostile.json` | Hostile token metadata (must render safely) |
| `samples/check-error.json` | Error (e.g. token not found) |
| `samples/check-payment-required.json` | HTTP 402: payment required, show pay button placeholder |

Plus: loading state, network/timeout error, and wallet connected to the wrong network.

## Security rules (non-negotiable)

- **Every string in the response is untrusted**, including token name, symbol, holder labels, risk flag texts, summary and source labels.
- Render all strings as plain text. Never use `dangerouslySetInnerHTML` or equivalent.
- Only render links with an `https:` URL. Anything else (e.g. `javascript:`) is shown as plain text or dropped.
- Long strings must not break the layout (truncate with full value available on hover or tap).
- Invisible or direction-changing Unicode characters (e.g. U+202E) must not alter how other text displays.
- No keys, secrets or private RPC URLs in the code. Use environment variables and an `.env.example`.

## Arc mainnet configuration

| Setting | Value |
|---|---|
| Chain ID | 5042 (hex 0x13b2) |
| Gas / native currency | USDC (native balance uses 18 decimals) |
| USDC ERC-20 interface | 0x3600000000000000000000000000000000000000 (6 decimals) |
| Explorer | https://explorer.arc.io |
| RPC | via env var `NEXT_PUBLIC_ARC_RPC_URL` (public endpoints may be permissioned; we will provide one) |

Show the USDC balance via the ERC-20 interface (6 decimals).
These values were collected from third-party documentation on 07/10/2026. Check them against the official Arc docs before relying on them.

## Response schema (v0.1)

| Field | Type | Notes |
|---|---|---|
| `status` | `ok` / `error` / `payment_required` | Drives which view to show |
| `sample` | boolean | `true` in all sample files; show a visible "Sample data" badge when true |
| `chain` | object | `name`, `chain_id` |
| `token` | object | `address`, `name`*, `symbol`*, `decimals`, `total_supply` (string) |
| `verdict` | object | `level` (`ok` / `caution` / `danger` / `unknown`), `score` (0-100), `headline`* |
| `holders` | object | `count`, `top10_share_pct`, `top_holders[]` (`address`, `share_pct`, `label`* or null) |
| `burns` | object | `claimed`, `verified`, `total_burned`, `burned_pct_of_supply`, `events[]` |
| `buybacks` | object | `claimed`, `verified`, `note`* or null |
| `risk_flags[]` | array | `code`, `severity` (`info` / `low` / `medium` / `high`), `title`*, `explanation`* |
| `summary` | string* | Plain-language summary |
| `sources[]` | array | `type`, `label`*, `url`* (only render as link if https) |
| `error` | object | Only when `status` is `error`: `code`, `message`* |
| `payment` | object | Only when `status` is `payment_required`: `price_usdc`, `network`, `chain_id` |

`*` = untrusted text. Large numbers are strings; do not convert them to JS numbers.

## Out of scope

- The x402 payment flow itself
- Backend, database, authentication
- Telegram Mini App wrapper (possible follow-up task)

## Acceptance criteria

- All four sample files render correctly, including the hostile one with nothing executing or breaking layout.
- Wallet connect works on Arc mainnet and shows the USDC balance, or a clear message on the wrong network.
- Lint and typecheck pass; a few tests cover safe rendering of the hostile sample.
- Clean, readable code with a short section in this README on how to run it.

## Delivery

Fork this repository and open a pull request. Code will be reviewed before merging.
This repository is public and may be published under an open-source license; rights to the delivered code transfer on payment.
