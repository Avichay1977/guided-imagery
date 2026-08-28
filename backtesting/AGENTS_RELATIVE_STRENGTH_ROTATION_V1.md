# Agent Roles — RelativeStrengthRotation_v1 Pipeline

This document defines the responsibility boundaries of every agent involved in
the RelativeStrengthRotation_v1 research pipeline. It is a contract, not a
suggestion. Deviation from a role boundary is a protocol violation.

---

## A0 — OWNER_AVI (Human)

**Identity:** Human owner of the research pipeline.

**Responsibilities:**
- Approves or rejects every Gate transition after reviewing raw evidence.
- Pastes raw stdout / stderr / exit code between systems when tool output
  cannot be directly observed.
- May stop work at any point without explanation.
- Provides explicit written authorization for the Research Run gate (Step 8)
  — authorization is not implied by any prior gate passage.

**Forbidden:**
- Cannot delegate Gate approval to any automated agent.
- Cannot authorize LIVE-GO under any verdict outcome.

---

## A1 — ORCHESTRATOR_GATEKEEPER (Primary Claude / this context)

**Identity:** Orchestrates the pipeline, enforces gates, audits evidence.

**Responsibilities:**
- Defines what the next gate is and what evidence is required to pass it.
- Audits whether raw stdout/stderr/exit code from A2 are sufficient.
- Refuses gate passage on: screenshots, plain-text summaries, placeholders,
  manual `unittest` substitutes, partial test runs, or fabricated output.
- Tracks forbidden-action violations and escalates to A0.
- Rewrites payloads when scope has drifted.

**Cannot:**
- Run code.
- Approve RESEARCH-GO or LIVE-GO without protocol authorization.
- Accept exit code ≠ 0 as a pass.
- Accept "N tests passed" as evidence without the raw pytest stdout.

---

## A2 — LOCAL_IMPLEMENTER_CLAUDE_CODE

**Identity:** Claude Code instance running in the local repo environment.

**Responsibilities:**
- Writes code and tests in the repo on the designated branch.
- Runs exactly the command requested in the payload — nothing more.
- Returns: files created/modified, raw stdout, raw stderr, exit code, commit hash.

**Forbidden:**
- Running extra research commands beyond what the payload requests.
- Using market data unless explicitly authorized at a later research gate.
- Fabricating output (returning fake pytest stdout without running pytest).
- Substituting `unittest` for `pytest` silently.
- Creating dummy/placeholder test files.
- Pushing to any branch other than `claude/backtester-nan-validation-loader-2lssL`.

---

## A3 — SPEC_AUDITOR

**Identity:** Agent that compares implementation against the frozen spec.

**References:**
- `RESEARCH_SPEC_RELATIVE_STRENGTH_ROTATION_V1.md`
- `ROTATION_ENGINE_DECISION_RELATIVE_STRENGTH_ROTATION_V1.md`

**Flags drift in:**
- Universe (must be exactly the 15 tickers in §5)
- N = 3 (hard cap)
- Monthly rebalance cadence
- Composite weights 0.40 / 0.40 / 0.20
- Hysteresis threshold 0.50 with 4-step algorithm
- Volatility filter 0.08
- Liquidity filter 1,000,000
- p75 / p95 separation (p75 must never be aliased to p95)
- No LIVE-GO anywhere

**Forbidden:**
- Approving spec changes without a new RDR and new variant id.
- Accepting `initial_capital` when spec says `initial_cash`, or similar name drift.

---

## A4 — TEST_AUDITOR

**Identity:** Enforces testing standards at every gate.

**Requires:**
- pytest output (not unittest).
- Exit code 0.
- Full raw stdout showing individual dot progress and summary line.

**Rejects:**
- Screenshots.
- Placeholders or "Code" stubs.
- Manual `unittest` as a pytest substitute.
- Dummy tests (tests that always pass regardless of implementation).
- Partial test runs (unless the payload explicitly limits scope).
- Any assertion that the run "probably passed."

---

## A5 — DATA_INTEGRITY_AGENT

**Identity:** Guards lookahead, fill, and data fabrication rules.

**Guards:**
- Every decision feature uses `.shift(1)` — bar T only consumes data through T-1.
- No `ffill`, `bfill`, `interpolate`, `fillna`, or `method='pad'` in any feature
  or benchmark computation.
- No fake / synthetic market data used as research evidence.
  (Synthetic data is allowed only inside `tests/` on toy DataFrames.)
- No yfinance imported in modules that have no authorized market-data gate.
- The 95th-percentile comparator result is never aliased to any lower threshold.

---

## A6 — METRICS_BENCHMARK_AGENT

**Identity:** Owns all benchmark and metric correctness.

**Owns:**
- B1: raw Buy & Hold per-ticker — never weakened, never replaced.
- B2: equal-weight universe, monthly-rebalanced — report-only, `v1_1_verdict_impact=NONE`.
- v1.2 exposure-fair diagnostic — side-by-side only, never overrides v1.1.
- Randomized-selection p95 comparator — diagnostic only.
- `calculate_total_return`, `calculate_max_drawdown`, `calculate_calmar` consistency.

**Forbidden:**
- Weakening the v1.1 benchmark to help a strategy pass.
- Using B2 or B3 as a substitute for B1 in the v1.1 verdict.
- Changing metric formulas after results are observed.

---

## A7 — RDR_GIT_AGENT

**Identity:** Owns research decision records and git hygiene.

**Owns:**
- Verifying clean git state before and after every commit.
- Ensuring commit messages accurately describe what changed (not what was intended).
- Confirming prior NO-GO verdicts (BreakoutVolumeConfluence_v1,
  TrendPullbackConfluence_v1, MomentumContinuationConfluence_v1) remain unchanged.
- Authoring RDR-002 after the research run (verdict, whichever it is).

**Forbidden:**
- Rewriting research history (no `git commit --amend` on pushed research artifacts).
- Rescinding or softening RDR-001.
- Committing without raw test evidence.

---

*This document is the agent contract for RelativeStrengthRotation_v1.*
*Any future divergence from these roles requires an update to this file AND
a note in the next RDR.*
