# RESEARCH SPEC — RelativeStrengthRotation_v1

**Status:** SPECIFICATION ONLY (no code, no tests, no backtests, no market data)

**Protocol gates that apply:** v1.1 (decision gate) + v1.2 (diagnostic, side-by-side)

**This document does not approve the strategy.** It defines the rules under
which the strategy may later be tested. Every parameter, weight, and threshold
named below is **frozen** before any backtest is run. Changing any of them
after seeing results is forbidden by the protocols.

---

## 1. Strategy Name

`RelativeStrengthRotation_v1`

Variant id (for the strategy_variants registry, once implemented):

    RelativeStrengthRotation_v1

Strategy family classification: **asset-selection / rotation**, NOT
entry-timing. This is the defining identity of the variant.

---

## 2. Research Question

> Does **selecting stronger assets relative to the universe and benchmark on a
> fixed rebalance schedule** produce a more robust edge under Protocol v1.1
> and a separately-reported exposure-fair edge under Protocol v1.2 than the
> three entry-timing variants archived as NO-GO?

This is a falsifiable question with a binary answer per gate:

- v1.1 verdict ∈ {V1_1_NO_GO, V1_1_RESEARCH_GO, V1_1_INSUFFICIENT_DATA}
- v1.2 diagnostic labels ∈ {PASS, FAIL, INSUFFICIENT_DATA} per edge, with
  the row-level v1.2 label always `PORTFOLIO_DIAGNOSTIC_ONLY`

A "yes" answer requires both gates to be satisfied independently. Either
gate failing kills this variant; v1.2 alone can never approve it.

---

## 3. Why This Is A Different Family

The three archived NO-GO variants all asked the same kind of question:

> "Inside one stock, when is the best moment to enter?"

Across `BreakoutVolumeConfluence_v1`, `TrendPullbackConfluence_v1`, and
`MomentumContinuationConfluence_v1`, the family-level failure mode was:

- Signal starvation was solved (variants 2 and 3 each produced ~290 OOS trades
  vs variant 1's 25).
- But the strategy could not consistently beat benchmark Calmar on a per-OOS
  basis at the required rate, nor exceed the randomized-timing p75 comparator,
  during the 2015–2024 window on the 12-ticker momentum universe.
- The structural problem is that partial-exposure entry timing inside a single
  bull-market stock fights both the benchmark's natural Calmar and a
  randomized timing that catches the same up-trend.

`RelativeStrengthRotation_v1` asks a different question:

> "Across a fixed universe, which assets are strongest right now, and does
> rotating into them at fixed schedule produce edge that the entry-timing
> family could not?"

This is **asset selection across a universe at fixed cadence**, not entry
timing within a single asset. The signal source is cross-sectional rank, not
intra-asset technical pattern. The exposure profile is continuous (held assets
rotated periodically), not discrete trade-per-signal.

This is a structurally distinct family, and that distinction is the
justification for testing it after the entry-timing family was archived.

---

## 4. Hypothesis

**H1 (primary, falsifiable):**
Selecting the top-N assets by a fixed composite relative-strength score on a
fixed monthly rebalance, within a fixed universe and fixed eligibility
filters, produces an OOS Calmar above benchmark on a ≥60% pass rate of
eligible walk-forward splits **AND** beats a randomized-selection comparator
at the p75 threshold under Protocol v1.1.

**H1.2 (secondary, diagnostic — never a decision gate):**
Under Protocol v1.2, the same strategy beats the exposure-matched Buy & Hold
on both total return AND Calmar, AND beats the randomized-selection comparator
at the p95 threshold on both total return AND Calmar.

**Null hypothesis (default belief):**
Cross-sectional relative strength does not produce robust edge in a long-only,
no-leverage, no-shorting, monthly-rebalance regime on this universe and
window. The strategy is NO-GO unless H1 is satisfied.

The null is the prior. Evidence must clear both protocol gates to displace it.

---

## 5. Universe Definition

The universe must be **frozen before any test is run** and may not be edited
after results are seen.

**Primary universe:** the existing 15-ticker baseline universe used by the
multi-ticker runners in the repo (referenced in `multi_ticker_summary_*.csv`
fixtures). The exact ticker list must be locked from an existing repo-defined
universe file or constant; this document does not invent a new list.

If the existing 15-ticker baseline is unavailable at implementation time, the
fallback universe is the 12-ticker momentum10y universe used in
`walk_forward_momentum10y.csv` and the strategy_lab outputs — frozen as it
appears in the repo on the implementation date.

**Universe rules:**
- Universe membership is fixed for the entire test window.
- No survivorship-bias-driven curation (no post-hoc removal of tickers that
  performed poorly).
- No addition of tickers based on prior results.
- A ticker that lacks sufficient historical data on the start date of a split
  is excluded from that split's eligibility set, but is NOT removed from the
  universe definition. This must be recorded per split.

**Anti-cherry-pick clause:** under no circumstance may the universe be
reduced post-hoc to `META / GOOGL / NVDA / CRWD / AAPL` or any subset
selected because those tickers happened to perform well. That move is
explicitly forbidden by RDR-001.

---

## 6. Benchmark Definition

Three benchmarks must be reported. **None of them may be weakened or replaced
after results are observed.**

**B1 — Raw Buy & Hold per-ticker (Protocol v1.1 primary):**
For each ticker held by the strategy, a fully-invested per-ticker Buy & Hold
over the same OOS window. The aggregated v1.1 per-split benchmark Calmar is
the existing `test_benchmark_calmar` column, unchanged.

**B2 — Equal-weight universe Buy & Hold (secondary diagnostic, REPORT ONLY):**
A monthly-rebalanced equal-weight portfolio across the same fixed universe,
under the same OOS window. Reported as a separate column in the output, never
used to upgrade or downgrade the v1.1 verdict. Treated as a diagnostic
sanity-check answering "did the rotation add anything over equal-weight?"

**B3 — Exposure-matched Buy & Hold (Protocol v1.2, side-by-side):**
Computed via the existing `protocol_v1_2_exposure_fair.calculate_exposure_matched_benchmark`
helper, using the strategy's observed exposure percentage for the same window.
Reported under the existing v1.2 column names. Never overrides the v1.1
verdict; the row-level v1.2 label remains `PORTFOLIO_DIAGNOSTIC_ONLY`.

**Hard prohibition:** the strategy's edge claim must hold against B1 to pass
v1.1. B2 is reported but is never used to displace B1. B3 is diagnostic only.

---

## 7. Required Data

- Daily OHLCV per ticker for the full universe, over the full test window.
- Adjustment policy: `auto_adjust=False` in yfinance fetch — NEVER True.
  (Repo-wide hard constraint, reaffirmed here.)
- Optional `adjusted_close` column may be used by `DataLoader(use_adjusted_close=True)`
  for benchmark/return computation, but the same setting must be used for
  strategy and benchmark within a single test run.
- No intraday data.
- No earnings calendar.
- No fundamental data (no PE, no EPS, no revenue, no fundamentals of any kind)
  for v1.
- No alternative data (no sentiment, no news, no analyst ratings).

Test window: the same windows already used in `walk_forward_momentum10y.csv`
and the strategy_lab outputs, locked from the repo's existing
`WalkForwardConfig` rather than chosen here.

---

## 8. Required Features

All features below are computed per ticker from daily OHLCV.

- `relative_strength_63d` — total return of the ticker over the trailing 63
  bars, divided by the total return of B1 (per-ticker Buy & Hold cannot serve
  as the cross-sectional reference; the cross-sectional reference is the
  equal-weight universe portfolio B2 for relative-strength normalization
  purposes). Formally:
  `RS_63 = (P_t / P_{t-63}) / (U_t / U_{t-63})`
  where `U_t` is the equal-weight universe index value at bar t.

- `relative_strength_126d` — same as `RS_63` but with a 126-bar lookback.

- `relative_strength_252d` — same with a 252-bar lookback.

- `benchmark_relative_strength` — ratio of the ticker's 252-bar total return to
  the **raw aggregate Buy & Hold** benchmark return (B1 aggregated across the
  universe, equal-weight). This is a separate quantity from `RS_252` and is
  defined explicitly so a future implementer cannot collapse the two.

- `rank_percentile` — cross-sectional percentile rank of the composite score
  (see §10) within the universe, in [0.0, 1.0]. Computed on the decision bar
  using only shifted features.

- `trend_filter_ema200` — boolean: `Close_{t-1} > EMA200_{t-1}`. Trend filter.

- `volatility_filter_atr_pct` — boolean: `ATR14_{t-1} / Close_{t-1} <= 0.08`.
  Excludes assets in extreme volatility regimes. The threshold (0.08) is
  frozen here and may NOT be tuned after results.

- `liquidity_filter_volume_avg_20` — boolean: `mean(Volume_{t-20 .. t-1}) >= 1_000_000`.
  Liquidity floor. The threshold is frozen here.

All thresholds (0.08 for volatility, 1,000,000 for liquidity, ranking weights
in §10, top-N and rebalance cadence in §11) are frozen by this document. Any
post-results adjustment is a protocol violation.

---

## 9. Feature Integrity Rules

These rules are absolute. Violation invalidates a research run.

- Every decision-time feature MUST be `.shift(1)` of the underlying series.
  Bar N may only consume information from bars `0..N-1`.
- No same-bar lookahead. The close of bar N is not visible to the decision
  that allocates capital at bar N's open or N+1's open.
- The ranking computation at rebalance bar N uses only shifted features
  computed from bars up to N-1.
- NaN, ±inf, or otherwise invalid feature values for a ticker on a rebalance
  bar MUST disqualify that ticker from that rebalance. No imputation. No
  forward-fill, back-fill, or interpolation of decision-time features.
- Volume features may use raw volume, but volume on bar N is not a
  decision-time input — only the 20-bar trailing volume average **as of bar
  N-1** is consumed.
- Returns used in features are simple daily returns
  `(P_t / P_{t-1}) - 1` derived from the chosen close (raw or adjusted, fixed
  per run).
- The equal-weight universe index `U_t` used for RS normalization is
  reconstructed from per-ticker daily returns under the same `.shift(1)`
  discipline — no use of "future" universe values to scale "past" RS.

---

## 10. Ranking Logic

The composite relative-strength score is a **fixed linear combination** that
may not be tuned after results.

    composite_rs = 0.40 * rank(relative_strength_126d)
                 + 0.40 * rank(relative_strength_252d)
                 + 0.20 * rank(benchmark_relative_strength)

Where `rank(.)` is the cross-sectional rank within the eligible universe at
the rebalance bar, mapped to [0.0, 1.0]. Ties are broken by alphabetical
ticker order — deterministic, never by performance.

`composite_rs` is then mapped to `rank_percentile` in [0.0, 1.0].

Notes:
- `relative_strength_63d` is computed and reported but NOT included in the
  primary composite. It is recorded for diagnostic analysis only. (Reason: 63d
  is closer to the entry-timing horizon that the archived NO-GO family used;
  giving it weight here would blur the cross-sectional/intra-asset boundary.)
- Weights `0.40 / 0.40 / 0.20` are frozen in this document. They may NOT be
  re-tuned after seeing results. A weight change requires a new RDR and a new
  variant id (e.g. `RelativeStrengthRotation_v2`).

---

## 11. Entry Logic

- **Rebalance cadence:** monthly, on the first trading day of each calendar
  month within the OOS test window. Cadence is frozen.
- **Selection rule:** rank eligible tickers by `rank_percentile`, descending.
  Select the top **N = 3** tickers as the target portfolio. N is frozen.
- **Eligibility:** a ticker is eligible at rebalance bar B only if ALL of
  these hold on bar B-1:
  - `trend_filter_ema200` is True
  - `volatility_filter_atr_pct` is True
  - `liquidity_filter_volume_avg_20` is True
  - All required RS features are finite (no NaN/inf)
- **Insufficient eligible tickers:** if fewer than N tickers are eligible, the
  strategy holds the remainder in cash. No substitution, no leverage, no
  filter relaxation.
- **No look-ahead:** the rebalance executes at the open of the rebalance bar
  using decisions computed from features shifted by 1 (i.e. as of the close
  of the prior trading day).

---

## 12. Exit / Rotation Logic

- At each rebalance, the new target portfolio replaces the prior one.
- **Hysteresis allowance:** an existing holding may remain in the portfolio
  if its `rank_percentile` on the rebalance bar is ≥ 0.50, even if it is no
  longer in the top N. This reduces churn. The threshold 0.50 is frozen.
- **Forced exits:** an existing holding is exited at the next rebalance if
  any of these occur at the rebalance bar:
  - It fails the EMA200 trend filter.
  - It fails the liquidity or volatility filter.
  - It dropped below `rank_percentile = 0.50`.
- **No intra-month exits.** There are no stops, no trailing stops, no
  take-profit targets, no kill switches inside the month. Risk control is
  performed at rebalance only. This is a defining property of the rotation
  family vs the entry-timing family.
- **Cash:** capital not allocated to selected tickers sits in cash with a
  cash return of 0.0 by default.

---

## 13. Position Sizing Rules

- **Equal weight across selected positions.** If N=3 are selected, each gets
  1/3 of the portfolio NAV at rebalance. If only 2 are eligible, each gets
  1/3 and the remaining 1/3 is cash. (Cash is not redistributed to bring
  positions to 1/2 each — that would change exposure regime after results.)
- **Max position weight:** 1/N = 33.3% with N=3. No exception.
- **No fractional sub-positions** within a ticker.
- **No leverage.** Total portfolio weight ≤ 100% of NAV at all times.
- **No shorting.** All weights are in [0, 1/N].
- **No options.**

---

## 14. Risk Controls

- The three eligibility filters (trend / volatility / liquidity) are the
  rotation strategy's risk controls. They are evaluated at every rebalance.
- **Concentration cap (universe-level):** no single ticker may receive more
  than 1/N of NAV. Already enforced by §13.
- **Cash floor:** none. Cash is unconstrained between 0% and 100%.
- **No kill switch on cumulative drawdown.** This differs from the
  entry-timing variants intentionally — drawdown management is achieved by
  the monthly trend-filter rotation, not by an emergency cash-out. This
  must be reported in v1.2 as part of the exposure profile.
- **Risk-per-trade does not apply** at this layer. There are no "trades" in
  the entry-timing sense — there are rebalance allocations. The protocol
  v1.1 trade-count metrics will count each rebalance position as one "trade"
  for falsification purposes.

---

## 15. Protocol v1.1 Evaluation

The walk-forward gate is the **only** decision gate. Verdicts must come from
the existing `WalkForwardEngine.aggregate()` logic unchanged.

Required reporting (per the existing v1.1 schema):
- `test_total_trades` (counted as rebalance positions, one per rebalance per
  selected ticker per split)
- `test_calmar`
- `test_benchmark_calmar` (B1, per-ticker raw Buy & Hold aggregated)
- `test_exposure_matched_calmar` (used by v1.2 layer; v1.1 may continue to
  report this column as-is)
- `test_random_p75_calmar` (existing p75 randomized-timing comparator
  retained as a legacy diagnostic; see §16 for the rotation-specific
  comparator under v1.2)
- `falsifier_pass`, `exposure_matched_pass`, `randomized_timing_pass`,
  `status`, `failure_reasons`

**v1.1 pass criteria (unchanged from current protocol):**
- ≥60% of eligible OOS splits exceed `test_benchmark_calmar`
- ≥60% of eligible OOS splits pass the randomized timing comparator
- Minimum trade count per split satisfied
- Falsifier signals do not invalidate the variant

If any of these fails, the final verdict is `V1_1_NO_GO` — and this verdict
is preserved verbatim through the v1.2 reporting adapter without alteration.

**No weakening of v1.1.** No new "rotation-friendly" threshold can be
introduced into v1.1 to make this variant pass. The v1.1 gate is fixed.

---

## 16. Protocol v1.2 Exposure-Fair Diagnostic Evaluation

The v1.2 layer is reported **side-by-side**, never as a decision gate, and
never overrides v1.1. All v1.2 output fields are produced via the existing
`protocol_v1_2_reporting.add_v1_2_columns` adapter and `enrich_lab_row`
helper.

Required metric sources to be supplied (one or more dicts) to
`enrich_lab_row(...)` so v1.2 edges can be classified PASS/FAIL rather than
INSUFFICIENT_DATA:

- `strategy_total_return`
- `strategy_calmar`
- `buy_hold_total_return`
- `buy_hold_calmar`
- `exposure_matched_bh_total_return`
- `exposure_matched_bh_calmar`
- `randomized_timing_p95_total_return`
- `randomized_timing_p95_calmar`

**Randomized-selection comparator (rotation-specific):**

- Same rebalance dates as the strategy.
- Same N (number of holdings = 3).
- Same fixed universe.
- Same eligibility filters at each rebalance (trend / volatility / liquidity).
- Asset selection randomized uniformly from the eligible set at each
  rebalance.
- Minimum 1000 simulations per split.
- Compute Calmar and total return per simulation, then take the p95 of each
  across simulations.
- Compare strategy Calmar AND strategy total return to the p95 of each.
- Strategy must beat BOTH p95 metrics to earn `TIMING_EDGE_PASS`.
  (Naming preserved from v1.2 even though the rotation equivalent is "asset
  selection edge" — the existing column names remain unchanged to avoid
  schema drift.)
- The default p95 threshold is fixed by this document. Lowering it to p75 or
  p50 after results is a forbidden move.

**v1.2 labels emitted:**
- `exposure_edge_label` ∈ {`EXPOSURE_EDGE_PASS`, `EXPOSURE_EDGE_FAIL`,
  `EXPOSURE_EDGE_INSUFFICIENT_DATA`}
- `timing_edge_label` ∈ {`TIMING_EDGE_PASS`, `TIMING_EDGE_FAIL`,
  `TIMING_EDGE_INSUFFICIENT_DATA`}
- `v1_2_diagnostic_label` = `PORTFOLIO_DIAGNOSTIC_ONLY` (always)
- `v1_1_verdict_preserved` = the unchanged v1.1 verdict

v1.2 never emits `RESEARCH-GO` or `LIVE-GO`. The reporting adapter already
enforces this; this spec reaffirms it.

---

## 17. Falsification Criteria

The variant is `V1_1_NO_GO` if any of the following hold (each criterion is
sufficient on its own):

- F1 — Insufficient trades: fewer than the v1.1 minimum trade count per OOS
  split on a majority of splits.
- F2 — Per-ticker concentration: >50% of cumulative OOS return concentrated
  in a single ticker. Computed across the test window.
- F3 — Per-year concentration: >70% of cumulative OOS return concentrated
  in a single calendar year.
- F4 — Per-month concentration: >25% of cumulative OOS return concentrated
  in a single rebalance month.
- F5 — Benchmark Calmar: strategy fails the v1.1 ≥60% benchmark-Calmar pass
  rate.
- F6 — Randomized comparator (v1.1 legacy p75): strategy fails the v1.1
  randomized-timing pass rate.
- F7 — v1.2 exposure edge: `EXPOSURE_EDGE_FAIL` on a majority of rows that
  carry sufficient v1.2 metric data. (Diagnostic — does not by itself trigger
  V1_1_NO_GO, but is required to be reported.)
- F8 — v1.2 randomized-selection p95: strategy fails the rotation-specific
  p95 comparator on a majority of rows that carry sufficient data.
  (Diagnostic only, same caveat as F7.)
- F9 — Post-hoc ticker selection: any evidence in the run log that the
  universe was reduced based on observed results.
- F10 — Post-hoc parameter change: any weight, threshold, N, or cadence
  changed between the spec and the executed run without a new RDR.

F1–F6 are v1.1 verdict drivers. F7–F8 are v1.2 diagnostics that must be
reported but never override v1.1. F9–F10 are protocol violations that
invalidate the run entirely and require a fresh RDR.

---

## 18. Anti-Overfit Rules

- All parameters in this spec (weights, N, cadence, hysteresis threshold,
  volatility threshold, liquidity threshold, RS lookback windows) are frozen
  before any backtest.
- No grid search, no Bayesian optimization, no random search over the
  parameter space prior to v1.1 evaluation.
- No ticker selection based on observed results.
- The universe is fixed in §5 and may not be edited after results.
- The walk-forward train/test cadence is taken from the existing
  `WalkForwardConfig` and not tuned for this strategy.
- The randomized-selection comparator (§16) uses the same universe and
  filters as the strategy — comparator and strategy share their constraints.
- If any anti-overfit rule is violated, the run's verdict is automatically
  `V1_1_NO_GO` regardless of metric outcomes, and the violation must be
  documented in the `failure_reasons` field and in a new RDR.
- A v2 of this variant requires (a) a new variant id
  (`RelativeStrengthRotation_v2`) and (b) a new RDR documenting why v1 is
  archived and how v2 differs. No silent edits.

---

## 19. Forbidden Research Moves

The following moves are forbidden by this spec and by the repo-wide
constraints inherited from RDR-001:

- No live trading recommendation under any verdict outcome.
- No `LIVE-GO` output.
- No capital allocation recommendation.
- No claiming profitability ("X% return" framed as an actionable result).
- No selecting tickers after seeing results. In particular, no narrowing of
  the universe to the post-hoc set `{META, GOOGL, NVDA, CRWD, AAPL}` or any
  similar winners-only subset.
- No changing ranking weights after seeing results.
- No changing rebalance frequency after seeing results.
- No changing N after seeing results.
- No changing eligibility-filter thresholds after seeing results.
- No weakening of the v1.1 benchmark (B1) to make the variant pass.
- No use of B2 (equal-weight universe) or B3 (exposure-matched) as a
  substitute for B1 in the v1.1 verdict.
- No conversion of any prior NO-GO verdict (BreakoutVolumeConfluence_v1,
  TrendPullbackConfluence_v1, MomentumContinuationConfluence_v1) into an
  approval based on results of this variant.
- No use of synthetic / toy / simulated market data as research evidence.
  Synthetic data is allowed only in unit tests.
- No use of `auto_adjust=True` in yfinance fetch.
- No skipping of pre-commit hooks or signing during commits of research
  artifacts.
- No aliasing of p75 results as p95 in v1.2 reporting.

---

## 20. Implementation Checklist

This checklist defines the order of permitted future work. Each step is a
gate; later steps may not begin until earlier ones produce raw passing
stdout/stderr evidence.

- [ ] **Step 0 — Spec freeze.** This document is reviewed and accepted as
      written. No edits to §5, §8, §10, §11, §12, §13, §16, §17 after this
      step except via a new RDR.

- [ ] **Step 1 — Contract tests.** Create
      `tests/test_relative_strength_rotation_v1_spec.py` containing
      document-contract tests that read THIS file and assert each section
      exists, the family identity statement is present, all hard-coded
      thresholds appear verbatim (weights 0.40/0.40/0.20, N=3, hysteresis
      0.50, volatility 0.08, liquidity 1,000,000), and the forbidden-moves
      list is present. No strategy code is written in this step.

- [ ] **Step 2 — Strategy class scaffolding.** Add
      `RelativeStrengthRotation_v1` to `strategy_variants.py` as a new
      `StrategyVariant` subclass with `required_features`, `prepare_features`,
      `generate_signal`, `calculate_score`, `describe`. No backtest run.
      Per-class unit tests verify the API conforms to the existing variant
      contract and that all decision features are shifted by 1.

- [ ] **Step 3 — Rotation engine extension.** Decide whether the existing
      `Backtester` can host a multi-asset rotation strategy as-is, or whether
      a dedicated `RotationBacktester` is required. If the latter, scaffold
      it with unit tests on toy deterministic data only. No market data, no
      runner execution. This decision is itself documented in a new RDR if
      a new engine is introduced.

- [ ] **Step 4 — Equal-weight universe benchmark (B2).** Implement and unit
      test the equal-weight universe index reconstruction used by §8 and
      §16. Toy data only.

- [ ] **Step 5 — Randomized-selection comparator.** Implement the p95
      randomized-selection comparator described in §16, with 1000+ sims,
      same-universe / same-filters discipline. Unit tests on toy data only.

- [ ] **Step 6 — Walk-forward integration.** Wire the rotation strategy
      into `WalkForwardEngine`, including the rotation-specific comparator.
      Unit tests only at this point — no full research run.

- [ ] **Step 7 — Dry adapter check.** Run `v1_2_dry_adapter_cli` and
      `v1_2_generate_dry_reports` over the eventual strategy_lab summary CSV
      with `--no-summary` disabled, to verify the v1.2 side-by-side fields
      flow end-to-end without fabrication.

- [ ] **Step 8 — Research run — explicit user authorization required.**
      Only after Steps 0–7 pass with raw stdout/stderr evidence may a full
      research run be initiated. Authorization for the run is a separate
      explicit user instruction; it is NOT implied by reaching this step in
      the checklist.

- [ ] **Step 9 — RDR-002.** Record the verdict (whichever it is) in a new
      Research Decision Record. RDR-002 must NOT modify or rescind RDR-001.

The bullets above represent the only sanctioned future order of work. No
step may be skipped or reordered without a new RDR.

---

**End of specification.**

This document is the contract. Any future divergence — in weights, N,
cadence, universe, benchmark, filter thresholds, or forbidden moves —
constitutes a protocol violation unless preceded by a new RDR.
