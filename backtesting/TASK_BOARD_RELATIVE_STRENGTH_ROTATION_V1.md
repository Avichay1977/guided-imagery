# Task Board — RelativeStrengthRotation_v1

Branch: `claude/backtester-nan-validation-loader-2lssL`

Legend: ✅ DONE | 🔄 CURRENT | ⏭ NEXT | 🔒 BLOCKED UNTIL LATER

---

## ✅ DONE

### Step 0 — Spec freeze
- **Owner:** A0_OWNER_AVI + A1_ORCHESTRATOR_GATEKEEPER
- **Artifact:** `RESEARCH_SPEC_RELATIVE_STRENGTH_ROTATION_V1.md` (patched, commit 4d69a23)
- **Proof:** A0 accepted CONDITIONAL-PASS, 5 corrections applied, re-accepted
- **Pass criterion:** Spec document frozen; §5/§8/§10/§11/§12/§13/§16/§17 locked

### Step 1 — Contract tests
- **Owner:** A2_LOCAL_IMPLEMENTER_CLAUDE_CODE
- **Artifact:** `tests/test_relative_strength_rotation_v1_spec.py` (commit e0a0d52)
- **Proof:** 117 passed in 0.13s, exit 0
- **Pass criterion:** All 20 sections, all frozen thresholds, all forbidden moves asserted

### Step 2 — Strategy class scaffold
- **Owner:** A2_LOCAL_IMPLEMENTER_CLAUDE_CODE
- **Artifact:** `strategy_variants.py` (modified), `tests/test_relative_strength_rotation_v1_scaffold.py` (commit e66686d)
- **Proof:** 155 passed in 6.29s, exit 0
- **Pass criterion:** UNIVERSE×15, TOP_N=3, weights 0.40/0.40/0.20, calculate_score, describe, SCAFFOLD_ONLY

### Step 3a — Rotation engine decision
- **Owner:** A1_ORCHESTRATOR_GATEKEEPER + A3_SPEC_AUDITOR
- **Artifact:** `ROTATION_ENGINE_DECISION_RELATIVE_STRENGTH_ROTATION_V1.md` (commit 50ec965)
- **Decision:** `DEDICATED_ROTATION_BACKTESTER_REQUIRED`
- **Pass criterion:** Explicit decision, no code executed, no market data

### Step 3b — RotationBacktester scaffold
- **Owner:** A2_LOCAL_IMPLEMENTER_CLAUDE_CODE
- **Artifact:** `rotation_backtester.py`, `tests/test_rotation_backtester_scaffold.py` (commit 1922c1a)
- **Proof:** 198 passed in 0.87s, exit 0
- **Pass criterion:** run() raises NotImplementedError, hysteresis 4-step, equal weights=1/top_n, cash for unused slots

### Step 4 — Rotation feature matrix builder
- **Owner:** A2_LOCAL_IMPLEMENTER_CLAUDE_CODE
- **Artifact:** `rotation_feature_matrix.py`, `tests/test_rotation_feature_matrix_builder.py` (commit 239e8f0)
- **Proof:** 235 passed in 1.27s, exit 0
- **Pass criterion:** shift(1) everywhere, no fill, RS_252 ≠ benchmark_RS separated

### Step 5a — B2 equal-weight universe benchmark
- **Owner:** A2_LOCAL_IMPLEMENTER_CLAUDE_CODE + A6_METRICS_BENCHMARK_AGENT
- **Artifact:** `rotation_benchmark_b2.py`, `tests/test_rotation_benchmark_b2.py` (commit 231ee58)
- **Proof:** 271 passed in 1.89s, exit 0
- **Pass criterion:** report_only=True, v1_1_verdict_impact=NONE, no fill, monthly rebalance

### Step 5b — Randomized-selection p95 comparator
- **Owner:** A2_LOCAL_IMPLEMENTER_CLAUDE_CODE + A6_METRICS_BENCHMARK_AGENT
- **Artifact:** `rotation_random_selection_comparator.py`, `tests/test_rotation_random_selection_comparator.py` (commit 4acd94f)
- **Proof:** 310 passed in 6.70s, exit 0
- **Pass criterion:** 1000 sims default, np.nanpercentile(95), no aliasing to lower threshold, report_only=True

---

## 🔄 CURRENT

*(Comparator p95 just passed. Awaiting next payload.)*

---

## ⏭ NEXT

### Step 6 — Rotation portfolio path engine
- **Owner:** A2_LOCAL_IMPLEMENTER_CLAUDE_CODE
- **Allowed:** Implement `RotationBacktester.run()` on toy deterministic data
- **Forbidden:** Real market data, strategy_lab_runner, research run
- **Required proof:** pytest -q, exit 0, raw stdout
- **Pass criterion:** Equity curve from toy OHLCV, rebalance events, exposure_pct populated, no fabricated returns

### Step 7 — RotationBacktester.run toy integration tests
- **Owner:** A2_LOCAL_IMPLEMENTER_CLAUDE_CODE + A4_TEST_AUDITOR
- **Allowed:** Toy DataFrames only
- **Required proof:** pytest -q, exit 0, all prior tests still passing
- **Pass criterion:** run() produces RotationBacktesterResult with non-None equity_curve and per_ticker_contribution_pct

### Step 8 — v1.2 metric-source wiring for rotation outputs
- **Owner:** A2_LOCAL_IMPLEMENTER_CLAUDE_CODE + A6_METRICS_BENCHMARK_AGENT
- **Allowed:** Wire RotationBacktesterResult into enrich_lab_row() / build_summary_row_with_v1_2_metrics()
- **Forbidden:** Producing real metrics; toy wiring only
- **Required proof:** pytest -q, exit 0, all prior tests still passing
- **Pass criterion:** v1.2 fields populated from rotation result, no fabrication

### Step 9 — WalkForwardEngine integration tests
- **Owner:** A2_LOCAL_IMPLEMENTER_CLAUDE_CODE
- **Allowed:** Wire RotationBacktester into existing WalkForwardEngine adapter; toy data only
- **Forbidden:** Real market data, real research run
- **Required proof:** pytest -q, exit 0

### Step 10 — Dry CSV report generation for rotation outputs
- **Owner:** A2_LOCAL_IMPLEMENTER_CLAUDE_CODE + A7_RDR_GIT_AGENT
- **Allowed:** Run v1_2_generate_dry_reports and v1_2_dry_adapter_cli over toy rotation summary CSV
- **Required proof:** Generated CSV exists, all LIVE-GO=0, all NO-GO->RESEARCH-GO=0

### Step 11 — Research-run authorization gate
- **Owner:** A0_OWNER_AVI (explicit written authorization required)
- **Allowed:** Nothing until A0 provides explicit written instruction
- **Forbidden:** Starting research run, fetching market data, running strategy_lab_runner
- **Note:** Authorization is NOT implied by Steps 0–10 passing

### Step 12 — RDR-002
- **Owner:** A7_RDR_GIT_AGENT
- **Allowed:** Record the verdict (whichever it is) in a new Research Decision Record
- **Forbidden:** Modifying or rescinding RDR-001; retroactively changing parameters

---

## 🔒 BLOCKED UNTIL LATER (require Step 11 authorization)

- Full research run with real market data
- `strategy_lab_runner` execution
- `fetch_yfinance_data` or any yfinance call
- Any capital allocation recommendation
- Any LIVE-GO output
- Any RESEARCH-GO output before both v1.1 and v1.2 gates confirm

---

*This board is the single source of truth for pipeline status.*
*Update after every gate passage.*
