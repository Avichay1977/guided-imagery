# Research Split Specification — RelativeStrengthRotation_v1

**Status:** SPECIFICATION ONLY.
**This document does not authorize a research run by itself.**
**No research run has been executed under this specification.**
**No market data has been used in producing this specification.**

## Purpose

This document fixes — in advance and in writing — the data range, the
walk-forward split structure, and the data-handling rules that any future
research evaluation of `RelativeStrengthRotation_v1` must follow. Locking
these choices before any data is touched eliminates the most common form of
selection bias (picking the split structure that flatters the strategy).

## Frozen universe (verbatim, in order)

`AAPL, MSFT, NVDA, AMD, META, AMZN, GOOGL, TSLA, NFLX, AVGO, CRM, ORCL, INTC, CSCO, IBM`

The universe is exactly 15 tickers. It is identical to the universe declared
by `RelativeStrengthRotation_v1` in `strategy_variants.py` and must not be
expanded, narrowed, or substituted for a research run.

## Data rules

- **Daily OHLCV only.** No intraday, options, fundamentals, earnings
  calendar, or alternative data.
- **`auto_adjust=False`** if data is fetched via `yfinance` (or any
  equivalent provider). Adjusted-close synthetic series are not acceptable.
- No forward-fill. No back-fill. No interpolation.
- Missing or invalid data must be reported, not silently repaired. A ticker
  with a coverage gap inside the research window invalidates the run for
  that ticker.
- Every decision-time feature is shifted by 1 bar (no same-bar lookahead).
  This is already enforced by `rotation_feature_matrix.py`.

## Date range target

- **Target window:** `2015-01-01` through `2024-12-31`.
- This is the target; the actual usable range is bounded by the universe's
  worst-coverage ticker. If a frozen-universe ticker lacks coverage at the
  start of the target window, the research window must be **shortened** at
  the start to the latest "first available bar" across the 15 tickers. The
  end date is never extended past `2024-12-31` for this spec.
- Any change to the target window (extending past 2024-12-31, expanding to
  earlier years, or selecting a different end date) requires a new RDR
  before research.

## Walk-forward split structure (frozen)

- `train_years = 3`
- `test_years = 1`
- `step_years = 1`
- **First test window starts immediately after the first 3 full training
  years.**
- Sliding (rolling) walk-forward, not expanding.
- Every test window is exactly 1 year long.
- Splits step forward by 1 year so each test year is covered exactly once.
- No parameter optimization inside `train`. The train window may be used
  ONLY for warmup of trailing features (e.g. 252-day relative strength,
  EMA200, 20-day volume average, 14-day ATR) and for eligibility validation.
  It may not be used to tune `top_n`, hysteresis, ranking weights, or the
  universe.
- OOS metrics are reported **only** from the test window. Train-window
  performance is never reported as research evidence.

### Concrete splits under the target window (illustrative)

| split_id | train_start | train_end  | test_start | test_end   |
|----------|-------------|------------|------------|------------|
| WF-01    | 2015-01-01  | 2017-12-31 | 2018-01-01 | 2018-12-31 |
| WF-02    | 2016-01-01  | 2018-12-31 | 2019-01-01 | 2019-12-31 |
| WF-03    | 2017-01-01  | 2019-12-31 | 2020-01-01 | 2020-12-31 |
| WF-04    | 2018-01-01  | 2020-12-31 | 2021-01-01 | 2021-12-31 |
| WF-05    | 2019-01-01  | 2021-12-31 | 2022-01-01 | 2022-12-31 |
| WF-06    | 2020-01-01  | 2022-12-31 | 2023-01-01 | 2023-12-31 |
| WF-07    | 2021-01-01  | 2023-12-31 | 2024-01-01 | 2024-12-31 |

The table above is illustrative — the actual splits derived by code must
match this rule deterministically. If any frozen-universe ticker lacks
coverage at the target start, the table is truncated from the top until all
fold train_starts are valid.

## What this spec does NOT authorize

- This spec does **not** authorize a research run.
- This spec does **not** create a RESEARCH-GO.
- This spec does **not** override or modify any prior NO-GO verdict.
- This spec does **not** permit changing the frozen strategy parameters
  (`top_n=3`, ranking weights `0.40/0.40/0.20`, hysteresis `0.50`,
  `volatility_atr_pct_max=0.08`, `liquidity_volume_avg_20_min=1_000_000`,
  long-only, no leverage, no shorting, cash_return=0.0).
- This spec does **not** permit parameter optimization, grid search,
  ticker substitution, or post-result selection of winners.

## Change control

Changing the split structure (`train_years`, `test_years`, `step_years`),
the date range, the data rules, or the frozen universe requires a new
RDR drafted and accepted **before** any research run that uses the new
structure. Splits cannot be re-cut after viewing results.

## Diagnostic stamp

A research run that follows this spec must include in its diagnostics:

- `split_spec_version = "RSR_V1_SPLIT_SPEC_v1"`
- `split_spec_authorized_research = false`
- `split_spec_train_years = 3`
- `split_spec_test_years = 1`
- `split_spec_step_years = 1`

The presence of these fields confirms the run honored this specification.
Their values are read-only and must not be edited after the run.
