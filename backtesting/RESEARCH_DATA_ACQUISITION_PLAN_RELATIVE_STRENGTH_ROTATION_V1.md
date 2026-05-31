# Research Data Acquisition Plan — RelativeStrengthRotation_v1

**Status:** PLAN ONLY.
**No market data is fetched by this document.**
**No research run is authorized by this document.**
**No live trading is authorized by this document.**

## Purpose

This plan freezes — in advance and in writing — exactly which tickers,
which columns, which provider rules, and which file-handling rules a future
data-acquisition gate must obey. Locking these choices before any data is
acquired prevents data-snooping and silent contract drift.

## Frozen universe (verbatim, in order)

`AAPL, MSFT, NVDA, AMD, META, AMZN, GOOGL, TSLA, NFLX, AVGO, CRM, ORCL, INTC, CSCO, IBM`

The universe is exactly 15 tickers. Substitution, addition, or removal of
any ticker requires a new RDR.

## Required date range

- `2015-01-01` through `2024-12-31`.
- A ticker that lacks coverage at the target start is reported as a
  coverage failure by the data audit. The window is not extended past
  `2024-12-31` for this plan.

## Required columns

Per-bar daily OHLCV CSV, exactly:

- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`

Optional (recorded but not relied on for trading decisions):

- `adjusted_close`

Any other column is permitted in the CSV but is ignored by the rotation
pipeline. Missing any of the six required columns invalidates the CSV.

## Provider rules

- **`auto_adjust=False`** if `yfinance` (or any equivalent) is used.
  Acquisition calls MUST explicitly set `auto_adjust=False`. An adjusted
  series is acceptable as `adjusted_close` only, never as `close`.
- Daily OHLCV bars only. No intraday, options, fundamentals, earnings
  calendar, alternative data.
- Each CSV must carry a `timestamp` column parseable to dates with no NaT.

## Data integrity rules

- No forward-fill.
- No back-fill.
- No interpolation.
- No synthetic fabrication of any bar.
- Missing or invalid bars must be reported, not silently repaired.
- A ticker with a gap inside the research window is invalid for that run.
- Synthetic / toy data must never be presented as research evidence.

## Local audit precedes acquisition

Before any data is acquired, the local audit (`rotation_data_audit`) must
be run against the repository's data roots and the resulting JSON report
must show:

- `all_required_tickers_present` clearly true or false
- the explicit list of `missing_tickers`
- the explicit list of `invalid_tickers`

The audit is read-only: it never fetches and never modifies CSVs.

## Currently missing tickers (per latest STOP report)

The following 8 tickers are missing locally and must be acquired in a
separate, explicitly approved gate:

`AMD, TSLA, NFLX, AVGO, CRM, INTC, CSCO, IBM`

## File placement and provenance

- All acquired market data must be written into a dedicated folder:
  `backtesting/data/` (or a sibling subdirectory specifically reserved for
  research data). It must NOT be mixed into code folders.
- Each acquired file must be named with the convention used by the existing
  repo: `<TICKER>_<start>_<end>.csv`.
- Every acquired CSV must record its provenance: which provider, which
  fetch parameters (`auto_adjust=False`, period range), and the timestamp
  of the fetch. Provenance is recorded in a sidecar JSON or a dedicated
  ledger file — not embedded into the OHLCV CSV.
- The set of generated CSVs must be listed explicitly in the acquisition
  commit and either committed or `.gitignore`d according to repository
  policy. They must never be auto-added by glob.

## What this plan does NOT authorize

- This plan does NOT fetch market data.
- This plan does NOT authorize a research run.
- This plan does NOT create a RESEARCH-GO or a LIVE-GO.
- This plan does NOT override any prior NO-GO verdict.
- This plan does NOT permit changing the frozen strategy parameters.
- This plan does NOT permit altering the frozen universe.
- This plan does NOT permit running `strategy_lab_runner` on rotation.

## Required gate for acquisition execution

Acquisition execution requires a **separate gate** explicitly approved by
the orchestrator. That gate must specify:

- the exact provider call (including `auto_adjust=False`),
- the target output folder,
- the provenance ledger path,
- a post-fetch audit run that must show
  `all_required_tickers_present = True` and
  `all_required_tickers_valid = True`,
- and an explicit statement that no live or research verdict is created.

Without that separate gate, no acquisition occurs.
