# ROTATION ENGINE DECISION — RelativeStrengthRotation_v1

**Status:** ARCHITECTURE DECISION DOCUMENT (no implementation, no tests, no
backtests, no market data, no research run)

**Scope:** Decide whether the existing `Backtester` can correctly host
`RelativeStrengthRotation_v1`, or whether a dedicated `RotationBacktester` is
required, before any rotation execution code is written.

**Does NOT do any of the following:**
- No research was run.
- No backtest was run.
- No market data was used.
- This decision does not approve the strategy.
- This decision does not create RESEARCH-GO or LIVE-GO.
- Prior NO-GO verdicts (`BreakoutVolumeConfluence_v1`,
  `TrendPullbackConfluence_v1`, `MomentumContinuationConfluence_v1`) remain
  unchanged.

---

## 1. Decision

    DECISION: DEDICATED_ROTATION_BACKTESTER_REQUIRED

The existing `Backtester` cannot host `RelativeStrengthRotation_v1` without
semantic distortion of the strategy spec. A dedicated `RotationBacktester` is
required and must be scaffolded in a later step (Step 3 of the spec
checklist). This document does NOT implement that engine.

---

## 2. Existing Backtester Assumptions

Static inspection of `backtester.py` (197 lines) confirms the following
hard-coded assumptions:

**A1. Single-asset DataFrame.** `Backtester.run(df)` accepts one DataFrame
that represents one symbol. All decisions iterate `df.itertuples()` with no
cross-symbol reference (`backtester.py:33-49`).

**A2. Single open position at a time.** `open_position = None` /
`open_position is not None` (`backtester.py:44, 61-77`). One position object
is held per backtester instance for the duration of the run. There is no
collection or map of positions.

**A3. Pending-entry / next-bar execution.** Entry executes at
`next_row = rows[i + 1].open` after `row.signal == 1` and a confluence-score
gate pass (`backtester.py:79-120`). The execution model is event-driven on
discrete signal bars, not calendar-driven.

**A4. ATR-based stop and 3R take-profit.** Every entry computes
`stop_price = entry_price - atr_stop_multiplier * row.atr_14` and
`tp_price = entry_price + take_profit_r * risk_per_share`
(`backtester.py:102-110`). Exits are checked every bar via `_check_exit`
against stop / take-profit / gap conditions (`backtester.py:62-77, 135-156`).

**A5. Risk-per-trade sizing.** Position sizing is
`shares = (cash * max_risk_pct) / risk_per_share` (`backtester.py:108-109`),
i.e. fixed-fractional risk per discrete trade.

**A6. Drawdown kill switch.** `drawdown >= max_drawdown_kill_pct` causes the
backtester to break the loop (`backtester.py:56-59`). This is a single-equity
property and the kill is permanent for the run.

**A7. Confluence-score gate.** Every entry requires
`score >= min_confluence_score` from either the variant's `calculate_score`
or the legacy `calculate_confluence_score` (`backtester.py:82-87`).

**A8. Single-symbol portfolio.** `PortfolioTracker` (`portfolio.py:1-12`)
exposes a scalar `_position_value` set by `update_position_value(shares,
current_price)`. There is no per-symbol map.

**A9. Single-symbol execution simulator.** `ExecutionSimulator.open_position`
(`execution.py:11-37`) and `close_position` (`execution.py:39-67`) directly
mutate `portfolio.cash` and `portfolio._position_value` as scalars — no
per-symbol bookkeeping, no concurrent positions.

**A10. WalkForwardEngine drives one ticker at a time.**
`WalkForwardEngine.evaluate_ticker(df_full, ticker, ...)` runs splits per
ticker, returning per-ticker per-split rows (`walk_forward.py:100-125`). The
aggregation step (`walk_forward.aggregate`) consumes per-ticker per-split
rows and aggregates trade-count and Calmar metrics across them.

**A11. Result schema is trade-list / equity-curve.** `Backtester.run`
returns `{"equity_curve", "trades", "final_equity", "kill_switch_triggered",
"ambiguous_exits"}` (`backtester.py:127-133`). Every output diagnostic is
keyed on discrete trades — there is no concept of holding period, no concept
of allocation weight per symbol, no concept of cash slot share.

---

## 3. RelativeStrengthRotation_v1 Requirements

From `RESEARCH_SPEC_RELATIVE_STRENGTH_ROTATION_V1.md` §§5, 10–14:

**R1. Multi-asset universe.** Fixed 15 tickers
(`AAPL, MSFT, NVDA, AMD, META, AMZN, GOOGL, TSLA, NFLX, AVGO, CRM, ORCL,
INTC, CSCO, IBM`). Decisions at each rebalance bar require simultaneous
cross-sectional ranking across all eligible tickers in the universe.

**R2. Up to N=3 simultaneous holdings.** Equal-weight (1/N) sizing across
selected positions. Cash for unused slots (e.g. only 2 tickers eligible →
2/3 invested, 1/3 cash). Cash is NEVER redistributed to bring positions to
1/2 each (spec §13).

**R3. Calendar-driven monthly rebalance.** Decisions execute on the first
trading day of each calendar month within the OOS window — NOT on signal
bars. The decision cadence is structural and time-based, not event-based
(spec §11).

**R4. No intra-month exits.** No stops, no trailing stops, no take-profit,
no kill switch inside the month. Risk control is rebalance-only (spec §12).

**R5. Hysteresis with hard cap at N.** The selection algorithm is the
4-step algorithm in spec §12: keep existing holdings ≥0.50 rank percentile,
trim to top-N if oversized, fill from non-held assets, cash for the
remainder. The post-rebalance portfolio has exactly
`min(N, |eligible|)` holdings — never more, never less.

**R6. No risk-per-trade sizing.** Allocation is equal-weight 1/N
(33.3% with N=3). Spec §13 forbids fractional sub-positions and forbids
cash redistribution within positions. No ATR-based sizing.

**R7. Cross-sectional ranking.** Rank requires simultaneous knowledge of
shifted features across the entire eligible universe at the rebalance bar.
Single-symbol iteration is structurally insufficient — the ranking step is
an inherently multi-symbol reduction.

**R8. Cross-sectional eligibility filters.** Trend (EMA200), volatility
(ATR%≤0.08), liquidity (mean-volume≥1M) evaluated per ticker at each
rebalance bar. Filtering produces the eligible set; only the eligible set
participates in ranking.

**R9. Equal-weight universe index B2.** Spec §6/§8 requires
reconstruction of an equal-weight universe portfolio (B2) for both
RS-normalization and for diagnostic reporting. This requires the engine to
hold and update a portfolio benchmark constructed from the same universe in
parallel with the strategy.

**R10. Randomized-selection comparator (v1.2).** Spec §16: 1000+
simulations per split, each simulating the same calendar, same N, same
universe, same eligibility filters, with random ticker selection at each
rebalance. The randomized comparator must be evaluable on the same engine
without code-path drift.

**R11. v1.2 metric source compatibility.** Spec §16 requires emitting all 8
v1.2 metric fields: `strategy_total_return`, `strategy_calmar`,
`buy_hold_total_return`, `buy_hold_calmar`,
`exposure_matched_bh_total_return`, `exposure_matched_bh_calmar`,
`randomized_timing_p95_total_return`, `randomized_timing_p95_calmar`. These
must be portfolio-level, not per-trade.

**R12. No LIVE-GO, no RESEARCH-GO directly from rotation.** The rotation
engine must feed v1.1 verdict logic unchanged. The engine cannot reuse the
existing single-ticker `Backtester` result schema and pretend it represents
a portfolio.

**R13. Per-ticker contribution tracking.** Spec §14 (and falsifier F2 in
§17) requires per-ticker contribution to cumulative OOS return with a
default cap of 25%. This is a portfolio-level diagnostic and requires
per-symbol return attribution at engine output, not per-trade output.

---

## 4. Compatibility Matrix

| # | Requirement                                       | Existing Backtester | Verdict |
|---|---------------------------------------------------|---------------------|---------|
| R1  | Multi-asset universe (15)                       | Single-asset only (A1)         | **INCOMPATIBLE** |
| R2  | Up to N=3 simultaneous holdings                 | One position at a time (A2)    | **INCOMPATIBLE** |
| R3  | Calendar-driven monthly rebalance               | Event-driven next-bar (A3)     | **INCOMPATIBLE** |
| R4  | No intra-month exits, no stops                  | Mandatory stop/TP (A4)         | **INCOMPATIBLE** |
| R5  | Hysteresis hard-cap selection                   | No multi-position concept (A2) | **INCOMPATIBLE** |
| R6  | Equal-weight 1/N sizing                         | ATR risk-per-trade sizing (A5) | **INCOMPATIBLE** |
| R7  | Cross-sectional ranking                         | Single-DataFrame iteration (A1)| **INCOMPATIBLE** |
| R8  | Cross-sectional eligibility filters             | Per-row signal gate only       | **INCOMPATIBLE** |
| R9  | Equal-weight universe index B2 in parallel      | Single equity curve only (A11) | **INCOMPATIBLE** |
| R10 | Randomized-selection comparator (1000+ sims)    | Randomized-**timing** only     | **INCOMPATIBLE** |
| R11 | Portfolio-level v1.2 metric sources             | Trade-keyed output (A11)       | **PARTIAL — needs portfolio wrapper** |
| R12 | Drawdown kill switch absent                     | Mandatory kill switch (A6)     | **INCOMPATIBLE** |
| R13 | Per-ticker contribution tracking                | No per-symbol map (A8)         | **INCOMPATIBLE** |

**11 of 13 requirements are incompatible.** The two non-incompatible items
(R11 partial; nothing else fits) are downstream of the engine's output
schema and cannot rescue the upstream incompatibilities.

The conclusion is structural, not parametric — there is no `BacktestConfig`
knob that converts a single-asset event-driven engine into a multi-asset
calendar-rebalanced portfolio engine.

---

## 5. Semantic Risks If Reusing Existing Backtester

These are the concrete failure modes that would occur if the existing
`Backtester` were forced to run `RelativeStrengthRotation_v1`. They are
listed so the decision is reversible only by someone who explicitly accepts
each risk in writing.

**S1. Sequential single-asset emulation collapses to entry-timing.** Running
the existing Backtester separately per ticker would convert
`RelativeStrengthRotation_v1` into 15 independent single-asset entry-timing
runs — which is *exactly* the family that `BreakoutVolumeConfluence_v1`,
`TrendPullbackConfluence_v1`, and `MomentumContinuationConfluence_v1`
already exhausted. This violates spec §3 ("structurally distinct family").

**S2. Sequential emulation cannot enforce N=3 cap.** Independent per-ticker
runs cannot enforce a portfolio-wide N=3 — every ticker would
independently take its own signal whenever its features qualified. This
violates spec §11 and §12 hard cap.

**S3. Sequential emulation has no cash slot.** With independent per-ticker
runs, capital is replicated across instances, not partitioned. This
violates spec §13 equal-weight 1/N sizing and produces fictitious leverage
at the portfolio level.

**S4. Mandatory stop/TP injects intra-month exits.** `Backtester._check_exit`
runs every bar (`backtester.py:62-77, 135-156`). With a rotation strategy
this would force intra-month exits and violate spec §12 ("No intra-month
exits").

**S5. Mandatory ATR sizing injects risk-per-trade.** `risk_amount = cash *
max_risk_pct` (`backtester.py:108`) is structurally incompatible with
equal-weight rotation. Sizing would be wrong and the diagnostics would
report a misrepresented portfolio.

**S6. Confluence-score gate is non-rotational.** `min_confluence_score`
(`backtester.py:86`) does not represent cross-sectional rank. Wedging a
rotation signal through this gate would either bypass the rank entirely or
distort it into a per-row absolute threshold.

**S7. Kill switch invalidates the rotation risk model.** Spec §14 states
"No kill switch on cumulative drawdown" — risk control is the monthly
trend-filter rotation. `Backtester.run` (`backtester.py:56-59`) hard-codes a
drawdown kill, which would terminate runs early and produce censored
diagnostics.

**S8. Aggregation in `WalkForwardEngine.aggregate` is keyed on per-ticker
trade counts.** `ticker_trades[t] += test_total_trades`
(`walk_forward.py:191-201`) computes concentration as a fraction of
*trades* per ticker, not as a fraction of *cumulative-return contribution*
per ticker. Spec §14 / falsifier F2 requires the latter. Reusing the
existing engine would silently swap the metric.

**S9. Randomized-timing comparator is the wrong comparator.** The current
`RandomizedTimingBenchmarkEngine` randomizes *entry timing* on a single
asset. Spec §16 requires randomized *asset selection* on the universe with
the same calendar and filters. Reusing the timing comparator as if it were
the selection comparator is an explicit forbidden alias under spec §16
("p75 ≠ p95" boundary — separate, but related, alias prohibition).

**S10. v1.2 metric sources would be fabricated.** The existing engine's
`final_equity` is single-asset. Treating it as `strategy_total_return` at
the portfolio level would be fabrication, which spec §16 and the
`protocol_v1_2_metric_sources` adapter both refuse (INSUFFICIENT_DATA
surfaces are the correct response).

---

## 6. Recommended Engine Architecture

This document defines the contract for the future engine WITHOUT
implementing it.

**RotationBacktester (recommended, not implemented in this step):**

- Driven by a calendar of rebalance bars (monthly, derived from the test
  window's trading calendar). The engine iterates over rebalance bars, not
  every bar.
- At each rebalance bar:
  - Computes eligibility per ticker using `.shift(1)` features only.
  - Computes composite RS rank across the eligible set.
  - Applies the 4-step hysteresis-capped selection algorithm (spec §12).
  - Updates the target portfolio with up to N equal-weight holdings.
  - Records per-ticker allocation and contribution.
- Between rebalances:
  - Marks each holding to market daily for the portfolio equity curve.
  - Does NOT check stops, take-profits, or kill switches.
- At the end of the test window:
  - Emits a portfolio result dict containing all 8 v1.2 metric fields,
    per-ticker contribution map, rebalance event log, and the equity curve.

**ExecutionSimulator extensions (later step, not now):**
- Add an `open_positions: dict[ticker, dict]` map or replace
  `_position_value` with `_position_values: dict[ticker, float]`.
- Add `rebalance_to_targets(target_weights: dict[ticker, float])` that
  computes per-ticker delta, applies slippage, and updates the portfolio
  state.

**RandomizedSelectionBenchmarkEngine (new, later step):**
- Same calendar as the strategy.
- Same N and eligibility filters.
- Random uniform selection from the eligible set at each rebalance.
- 1000+ simulations per split.
- p95 of total return and Calmar across simulations.
- Strictly separate from `RandomizedTimingBenchmarkEngine`. The existing
  timing comparator (today p75) MUST NOT be aliased as p95.

**WalkForwardEngine integration (later step, not now):**
- Add a rotation code path that, when a rotation variant is supplied,
  delegates to `RotationBacktester` instead of `Backtester`.
- The aggregation step must consume portfolio-level rows, not per-ticker
  per-split rows. Per-ticker contribution percentage replaces the existing
  per-ticker trade-count concentration.

---

## 7. Required Future Interfaces

These interfaces are required for a future `RotationBacktester`
implementation. They are listed for completeness so that the upcoming Step 3
scaffold knows what surface to expose.

```
class RotationBacktester:
    def __init__(self, config, portfolio, execution, strategy_variant, universe): ...
    def run(
        self,
        df_by_ticker: dict[str, pd.DataFrame],   # one DataFrame per universe member
        test_start: str,
        test_end: str,
    ) -> dict:
        # Returns:
        # {
        #   "equity_curve": list[float],          # portfolio NAV, one per trading day
        #   "rebalance_events": list[dict],       # one per rebalance bar
        #   "per_ticker_contribution_pct": dict[str, float],
        #   "exposure_pct": float,
        #   "final_equity": float,
        #   "strategy_total_return": float,
        #   "strategy_calmar": float,
        #   "v1_2_metric_sources": dict,
        # }
```

```
class RandomizedSelectionBenchmarkEngine:
    def __init__(self, n_simulations: int = 1000): ...
    def run(
        self,
        df_by_ticker: dict[str, pd.DataFrame],
        rebalance_calendar: list[pd.Timestamp],
        eligibility_fn,
        n_holdings: int,
    ) -> dict:
        # Returns:
        # {
        #   "p95_total_return": float,
        #   "p95_calmar": float,
        #   "n_simulations": int,
        # }
```

These signatures are illustrative for the architecture decision; they may
be refined when Step 3 scaffolding begins, provided the spec contract is
preserved.

---

## 8. Required Future Unit Tests

For the upcoming Step 3 scaffold step, the following unit tests must exist
**before** any market data is loaded:

- `test_rotation_backtester_calendar_only_decisions` — confirms the engine
  iterates only on rebalance bars.
- `test_rotation_backtester_no_intra_month_exits` — confirms no stop / TP /
  kill switch is evaluated between rebalances.
- `test_rotation_backtester_equal_weight_1_over_n` — confirms allocation
  is exactly 1/N for selected positions.
- `test_rotation_backtester_cash_when_fewer_than_n_eligible` — confirms
  cash slot is preserved (NOT redistributed) when fewer than N eligible.
- `test_rotation_backtester_n_hard_cap` — confirms portfolio never holds
  more than N positions post-rebalance (hysteresis 4-step algorithm).
- `test_rotation_backtester_uses_shifted_features_only` — confirms no
  same-bar lookahead at the rebalance bar.
- `test_rotation_backtester_emits_v1_2_metric_sources` — confirms the
  result dict carries all 8 v1.2 metric fields.
- `test_randomized_selection_comparator_uses_same_universe_and_filters` —
  confirms the comparator is constrained identically to the strategy.
- `test_randomized_selection_p95_not_aliased_to_timing_p75` — confirms the
  `randomized_timing_p95_*` outputs come from `RandomizedSelectionBenchmarkEngine`,
  not from `RandomizedTimingBenchmarkEngine`.
- `test_per_ticker_contribution_capped_at_25pct` — confirms F2 (spec §17)
  is enforced at the portfolio diagnostics layer.

All toy-deterministic data. No market data. No runner execution.

---

## 9. Non-Goals

This decision document explicitly does NOT:

- Implement `RotationBacktester`.
- Implement `RandomizedSelectionBenchmarkEngine`.
- Modify `Backtester`, `Portfolio`, `Execution`, `FeatureEngine`, or
  `WalkForwardEngine`.
- Modify `strategy_variants.py`.
- Modify the spec `RESEARCH_SPEC_RELATIVE_STRENGTH_ROTATION_V1.md`.
- Run any backtest.
- Run `strategy_lab_runner` or any runner.
- Fetch market data.
- Use market data.
- Produce a v1.1 or v1.2 verdict.
- Change Protocol v1.1 or v1.2 gates.
- Overturn or revisit any existing NO-GO verdict.

---

## 10. Gate Decision

    DECISION: DEDICATED_ROTATION_BACKTESTER_REQUIRED

**Rationale (one-line summary):** 11 of 13 requirements are incompatible
with the existing single-asset event-driven `Backtester`; the only
compatible items are downstream of the engine and cannot rescue the
structural mismatch. Forcing reuse would replicate the entry-timing family
the spec explicitly forbids (spec §3).

**Permitted next step:** Step 3 of the implementation checklist —
*Rotation engine extension*. That step scaffolds a `RotationBacktester`
class with the interface in §7 and the unit tests in §8, on toy
deterministic data only.

**Forbidden between this step and Step 3 scaffold:**
- No backtest run.
- No market data fetch.
- No runner execution.
- No changes to existing variants.
- No changes to the spec.
- No claims of RESEARCH-GO / LIVE-GO.

A new RDR (RDR-002) is **NOT** required for this decision because the spec
checklist explicitly anticipates this branch ("If the latter, scaffold it
with unit tests on toy deterministic data only" — spec §20 Step 3). An RDR
**WOULD** be required if Step 3 were to introduce architectural choices that
deviate from the spec contract.

---

**End of decision document.**
