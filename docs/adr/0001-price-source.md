# ADR 0001 — CoinGecko as the only price source

status: accepted (owner decision) · date: 2026-09-02 · supersedes: nothing

## Context

The product needs prices for the top 50 coins and must alert on sudden moves.
CoinGecko's free plan caps usage at roughly 10,000 requests per month — about
one request every 4.3 minutes for the whole month.

A hybrid design (exchange websocket for prices, CoinGecko for metadata) was
proposed because it gives ~1s price latency at zero request cost. The owner
chose CoinGecko only.

## Decision

CoinGecko is the single upstream. The request budget is spent as follows:

| call | frequency | monthly cost |
|---|---|---|
| `/coins/markets` with an explicit `ids` set | every 5 min | ~8,640 |
| `/coins/markets` ordered top-N (defines the tracked set) | daily | ~30 |
| `/coins/{id}/market_chart` | twice per new coin | ~120 |

Everything else is derived locally: candles are aggregated from our own
5-minute snapshots, search runs against our `coins` table, and the market page
and coin page are served from Redis and PostgreSQL. No user action can spend a
request.

## Consequences

* Alert latency is up to 5 minutes (mean ~2.5 minutes).
* Moves that cross a threshold and revert between two samples are invisible.
  The UI states this; percentage windows start at 15 minutes because anything
  shorter is noise at a 5-minute sampling rate.
* `POLL_INTERVAL_SECONDS` is the cap-defining constant. 300s is the floor on the
  free plan; 180s would mean ~14,400 requests and a mid-month cut-off.
* The `PriceSource` protocol keeps the escape route cheap: a paid key means
  changing one environment variable, and a different provider means one class.
