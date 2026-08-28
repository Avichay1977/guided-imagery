# PROTOCOL v1.2 — Exposure-Fair Diagnostic Layer

**Protocol:** v1.2
**Status:** DESIGN (spec only — not implemented)
**Depends on:** Protocol v1.1, RESEARCH_DECISION_RECORD_001
**Type:** Diagnostic layer (not a gate replacement)

---

## 1. Purpose

Protocol v1.2 answers a research question that Protocol v1.1 does not ask:

> Does a partial-exposure strategy show edge versus **exposure-matched**
> alternatives — both an exposure-matched Buy & Hold and exposure-matched
> randomized timing?

v1.1 asks whether a strategy beats full Buy & Hold Calmar and beats randomized
timing. v1.2 asks a separate question about exposure-adjusted edge. The two
protocols are reported **side by side**; v1.2 never replaces a v1.1 answer.

Exposure-matched evaluation answers a different research question. It is not
assumed to be easier or harder, and it is not assumed to save or reject any
variant. It is tested explicitly and reported in its own table.

---

## 2. Why v1.1 Remains Valid

- v1.1 verdicts are final and preserved:
  `BreakoutVolumeConfluence_v1 = NO-GO`,
  `TrendPullbackConfluence_v1 = NO-GO`,
  `MomentumContinuationConfluence_v1 = NO-GO`.
- v1.1 measured the strategy against the realistic default a passive investor
  would actually hold: full Buy & Hold. That question stands on its own.
- The individual-stock partial-exposure entry-timing family remains archived
  under v1.1 regardless of any v1.2 result.

---

## 3. What v1.2 Adds

- An **exposure-matched Buy & Hold** benchmark: the same underlying held at the
  strategy's own market-exposure fraction, not at 100%.
- An **exposure-matched randomized timing** distribution: random entry schedules
  with the same trade count and holding periods as the strategy.
- A side-by-side report showing, for every (strategy, ticker, window): the v1.1
  verdict (preserved) and the v1.2 diagnostic labels.
- Distinct, non-overlapping labels so v1.1 and v1.2 results can never be confused.

---

## 4. What v1.2 Explicitly Does Not Do

- Does **not** overwrite, delete, or alter any v1.1 verdict.
- Does **not** convert any NO-GO into RESEARCH-GO.
- Does **not** output RESEARCH-GO or LIVE-GO as an overall trading decision.
- Does **not** recommend live trading or capital allocation.
- Does **not** weaken or change v1.1 thresholds.
- Does **not** change its own thresholds after results are seen.
- Does **not** select tickers based on which performed well.
- Does **not** use synthetic market data as research evidence (synthetic data is
  permitted only for unit tests, never as a research result).
- Does **not** claim profitability.
- Does **not** assume the exposure-matched benchmark is easier or harder than
  Buy & Hold.

---

## 5. Exposure-Matched Benchmark Definition

The exposure-matched Buy & Hold benchmark is defined with:

- the **same test window** as the strategy,
- the **same ticker / universe** as the strategy,
- the **same exposure percentage** as the strategy (fraction of trading days the
  strategy held a position),
- the **same starting capital** as the strategy,
- the **same transaction-cost assumptions** where applicable,
- **cash return assumed zero** unless explicitly configured otherwise,
- **both** the raw full Buy & Hold and the exposure-matched Buy & Hold reported,
  never only one.

No leverage. No interest on idle cash unless explicitly configured. The
exposure-matched benchmark is a reporting comparator, not a gate.

---

## 6. Exposure-Matched Random Timing Definition

The exposure-matched randomized timing distribution is defined with:

- the **same trade count** as the strategy,
- the **same holding periods** as the strategy,
- the **same test window** as the strategy,
- the **same ticker / universe** as the strategy,
- a **minimum of 1000 randomized simulations**,
- comparison on both **Calmar Ratio** and **total return**,
- a **default threshold of p95** unless explicitly configured otherwise.

A strategy demonstrates timing edge under v1.2 only if it exceeds the configured
percentile of the randomized distribution on the specified metrics.

---

## 7. Required Metrics

Per (strategy, ticker, window):

- strategy exposure percentage
- strategy total return
- strategy Calmar
- raw Buy & Hold total return and Calmar
- exposure-matched Buy & Hold total return and Calmar
- randomized timing p95 total return and Calmar (≥ 1000 sims)

Aggregation across windows/tickers is reported but is diagnostic only; it does
not produce a trading decision.

---

## 8. Required Output Columns

```
strategy_name
strategy_version
protocol_version
ticker
test_window
strategy_exposure_pct
strategy_total_return
strategy_calmar
buy_hold_total_return
buy_hold_calmar
exposure_matched_bh_total_return
exposure_matched_bh_calmar
randomized_timing_p95_total_return
randomized_timing_p95_calmar
exposure_edge_label
timing_edge_label
v1_1_verdict_preserved
v1_2_diagnostic_label
failure_reasons
```

---

## 9. Pass / Fail Labels

v1.1 labels (preserved, read-only in v1.2):

- `V1_1_NO_GO`
- `V1_1_RESEARCH_GO`
- `V1_1_INSUFFICIENT_DATA`

v1.2 diagnostic labels:

- `EXPOSURE_EDGE_PASS` — strategy Calmar ≥ exposure-matched BH Calmar
- `EXPOSURE_EDGE_FAIL` — strategy Calmar < exposure-matched BH Calmar
- `EXPOSURE_EDGE_INSUFFICIENT_DATA` — too few trades/days to evaluate
- `TIMING_EDGE_PASS` — strategy exceeds randomized p95 on configured metrics
- `TIMING_EDGE_FAIL` — strategy does not exceed randomized p95
- `TIMING_EDGE_INSUFFICIENT_DATA` — fewer than the minimum required simulations/trades
- `PORTFOLIO_DIAGNOSTIC_ONLY` — overall v1.2 record marker; never a trading decision

`v1_2_diagnostic_label` is always `PORTFOLIO_DIAGNOSTIC_ONLY` at the record level
to make explicit that v1.2 emits diagnostics, not go/no-go decisions.

---

## 10. Side-by-Side Reporting With v1.1

Every v1.2 row carries `v1_1_verdict_preserved` so the two protocols appear
together without merging:

| Column group | Source | Mutable by v1.2? |
|--------------|--------|:----------------:|
| `v1_1_verdict_preserved` | Protocol v1.1 | No (read-only) |
| `exposure_edge_label` | Protocol v1.2 | Yes |
| `timing_edge_label` | Protocol v1.2 | Yes |
| `v1_2_diagnostic_label` | Protocol v1.2 | Yes (fixed to `PORTFOLIO_DIAGNOSTIC_ONLY`) |

A v1.2 `EXPOSURE_EDGE_PASS` next to a `V1_1_NO_GO` is a valid, expected, and
non-contradictory state: it means "failed the full-exposure gate, but shows an
exposure-adjusted signal worth further study." It does **not** promote the v1.1
verdict.

---

## 11. Failure Conditions

A v1.2 evaluation is marked `*_INSUFFICIENT_DATA` (not PASS, not FAIL) when:

- the strategy produced too few trades to estimate exposure reliably,
- the randomized timing run completed fewer than 1000 simulations,
- the test window is too short to compute a stable Calmar,
- exposure percentage is zero (no positions) or undefined.

A v1.2 record is invalid (must be discarded, not reported as a result) if:

- it is produced from synthetic market data,
- thresholds were changed after results were observed,
- only winning tickers were included,
- any v1.1 verdict column was modified.

---

## 12. Anti-Overfit Constraints

- Fixed thresholds, set before results are seen.
- Pre-specified universe; no post-hoc ticker selection.
- No parameter tuning inside any strategy variant.
- No gate weakening; v1.1 remains intact.
- Synthetic data for unit tests only — never as research evidence.
- Exposure-matched evaluation assumed neither easier nor harder in advance.
- Diagnostic labels never escalate to RESEARCH-GO or LIVE-GO.

---

## 13. Implementation Checklist

> Spec only. The items below are the planned order of work; none are done yet.

1. Define `ExposureFairConfig` (percentile default p95, min_simulations=1000,
   cash_return=0.0, transaction-cost passthrough).
2. Implement exposure-matched Buy & Hold comparator (reuse existing
   `ExposureMatchedBenchmarkEngine`; report raw BH alongside).
3. Implement exposure-matched randomized timing comparator (reuse existing
   `RandomizedTimingBenchmarkEngine`; enforce ≥ 1000 sims, p95 default).
4. Implement v1.2 evaluator that emits the Required Output Columns (§8) and the
   labels (§9), carrying `v1_1_verdict_preserved` read-only from v1.1 results.
5. Implement side-by-side reporter (§10) — v1.1 and v1.2 columns never merged.
6. Write tests (synthetic data only): label correctness, INSUFFICIENT_DATA
   handling, v1.1-verdict immutability, ≥1000-sim enforcement, p95 logic,
   raw-BH-plus-exposure-matched-BH both present.
7. Only after tests pass on a real local terminal with raw stdout/stderr: run on
   the pre-specified universe with real data and report side-by-side with v1.1.
8. Do not proceed to RelativeStrengthRotation_v1 until v1.2 reporting is settled.
