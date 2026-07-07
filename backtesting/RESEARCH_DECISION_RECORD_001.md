# RESEARCH_DECISION_RECORD_001

**Protocol:** v1.1
**Record ID:** RDR-001
**Date:** 2026-05-30
**Status:** ACTIVE
**Subject:** Individual-Stock Partial-Exposure Entry-Timing Candidate Family

---

## 1. Decision

Archive the **individual-stock partial-exposure entry-timing candidate family**
under Protocol v1.1.

Three independent entry logics were evaluated through the full research gate.
All three returned **NO-GO**. The family is frozen: no additional entry-timing
variant on the same 2015–2024 test regime will be evaluated under v1.1.

This decision does **not** declare the strategies profitable, does **not**
weaken any gate, and does **not** convert any NO-GO into RESEARCH-GO.

---

## 2. Scope

**In scope:**
- BreakoutVolumeConfluence_v1
- TrendPullbackConfluence_v1
- MomentumContinuationConfluence_v1
- Test regime: 2015-01-01 → 2024-12-31, pre-specified momentum universe (12 tickers)
- Walk-forward splits: train 3y / test 1y / step 1y

**Out of scope (not addressed by this record):**
- Bear-regime data (e.g. 2000–2010)
- Multi-asset rotation or selection strategies
- Short-side strategies
- Any change to gate thresholds or benchmark definitions

---

## 3. Evidence Table

| Metric | v1 Breakout | v2 Pullback | v3 Momentum | Threshold |
|--------|------------:|------------:|------------:|:---------:|
| OOS total trades | 25 | 294 | 289 | ≥ 50 |
| Eligible splits | 5 | 41 | 42 | — |
| Positive expectancy rate | 60.0% | 68.3% | 69.0% | ≥ 60% |
| Avg profit factor | 1.83 | 1.97 | 2.04 | ≥ 1.2 |
| Max ticker concentration | 40.0% | 14.6% | 13.1% | ≤ 25% |
| Calmar vs Buy & Hold rate | 20.0% | 29.3% | 33.3% | ≥ 60% |
| Timing vs random rate | 20.0% | 24.4% | 31.0% | ≥ 60% |
| **Verdict** | **NO-GO** | **NO-GO** | **NO-GO** | — |

---

## 4. What Improved Across Variants

- **Signal starvation: solved.** Trade count rose from 25 (v1) to ~290 (v2, v3).
  Eligible walk-forward splits rose from 5 to 42.
- **Trade quality: consistently positive.** Positive-expectancy rate climbed to
  ~69%; average profit factor reached 2.04.
- **Concentration risk: resolved.** Single-ticker dependence fell from 40% to
  ~13%, well under the 25% limit.
- **The two failing metrics trended upward**, not downward:
  Calmar-vs-BH 20% → 29% → 33%; Timing-vs-random 20% → 24% → 31%.

---

## 5. What Still Failed

Two gates failed in **every** variant, by a wide margin:

1. **Calmar superiority vs Buy & Hold** — best observed 33.3% (need ≥ 60%).
2. **Timing edge vs randomized entry** — best observed 31.0% (need ≥ 60%).

The improvement trend is real but insufficient: even the best variant reached
only roughly half the required pass rate on both gates.

---

## 6. Root Cause Hypothesis

The failures are **structural to the family**, not specific to any entry logic:

- In a predominantly bull regime (2015–2024), Buy & Hold holds 100% market
  exposure continuously. A partial-exposure strategy sits out part of the time,
  so its CAGR-to-drawdown ratio rarely exceeds that of continuous exposure.
- In a rising market, **a random entry is also frequently profitable**, so
  demonstrating timing skill above the randomized p75 distribution is intrinsically
  hard.
- **Exposure-matched evaluation is a separate research question.** It must be
  tested explicitly under Protocol v1.2 and must not be assumed to save or reject
  any variant. As a starting observation only, in the existing v1.1 result files
  the exposure-matched Calmar pass rates were close to the Buy & Hold pass rates;
  this is an empirical observation on this data, not a general claim that
  exposure-matched evaluation is easier, harder, or equivalent. The v1.2 layer
  exists precisely to answer that question with its own table.

---

## 7. Why This Is Not A Bug

- The same failure mode reproduced across three independent entry logics with
  different signal-generation code paths.
- The metrics that *should* improve (trade count, expectancy, profit factor,
  concentration) **did** improve, demonstrating the pipeline responds correctly
  to genuine strategy differences.
- The failing metrics are ratio-based comparisons against an aggressive
  bull-market benchmark; their behavior is mathematically expected for
  partial-exposure strategies.
- No anomaly, no NaN leakage, no lookahead, and no degenerate trade behavior was
  observed. The verdicts are coherent with the strategy economics.

---

## 8. Why Further Entry-Timing Variants Are Frozen Under v1.1

Three variants spanning breakout, pullback, and momentum-continuation logic all
failed at the same two gates with the same magnitude. The marginal gains between
variants (a few percentage points) are far smaller than the gap to threshold
(~27–29 points). Continuing to test additional entry-timing variants on the same
2015–2024 regime is unlikely to be informative and risks specification search /
overfitting. The family is frozen until the regime or the strategy class changes.

---

## 9. Preserved Verdicts

These verdicts are locked and must not be retroactively altered:

```
BreakoutVolumeConfluence_v1        = NO-GO
TrendPullbackConfluence_v1         = NO-GO
MomentumContinuationConfluence_v1  = NO-GO
Family verdict under v1.1          = NO-GO
```

Allowed verdict vocabulary: RESEARCH-GO, NO-GO, INSUFFICIENT-DATA.
Forbidden verdict: LIVE-GO.

---

## 10. Next Research Branches

Two distinct branches are sanctioned. Neither reopens the frozen family, and
neither converts a v1.1 NO-GO into a pass.

**A. Protocol v1.2 — Exposure-Fair Diagnostic Layer**
A diagnostic-only layer asking a *different* question: does the family have an
exposure-adjusted edge worth studying? This is an analysis layer, not a gate
replacement. It cannot promote any v1.1 NO-GO. Exposure-matched evaluation must
be tested explicitly and must not be assumed in advance to save or reject any
variant; v1.2 reports its own side-by-side table against v1.1.

**B. RelativeStrengthRotation_v1 — New Strategy Family**
A shift from *entry timing* to *asset selection*: rank-and-rotate among the
universe by relative strength rather than timing entries on a single name. This
is a new family with its own identity and its own pass through the full v1.1 gate.

Recommended order: (1) lock this Decision Record → (2) v1.2 Diagnostic →
(3) RelativeStrengthRotation_v1.

---

## 11. Anti-Overfit Constraints

The following remain in force and were not violated in reaching this decision:

- Do not change strategy rules to fit observed results.
- Do not optimize parameters after seeing results.
- Do not lower or weaken any gate threshold.
- Do not change the benchmark definition to make a strategy pass.
- Do not select tickers based on which performed well.
- Do not interpret positive expectancy or profit factor as proof of edge.
- Do not recommend trading real money.
- Three variants with the same failure are sufficient to freeze the family;
  additional same-regime entry-timing variants are not permitted under v1.1.
