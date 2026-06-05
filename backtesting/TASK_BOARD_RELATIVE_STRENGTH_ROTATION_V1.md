# Task Board — RelativeStrengthRotation_v1

Branch: `claude/backtester-nan-validation-loader-2lssL`

Legend: ✅ DONE | 🔄 CURRENT | ⏭ NEXT | 🔒 BLOCKED UNTIL LATER

---

## ✅ DONE

### Step 0 — Spec freeze
- **Artifact:** `RESEARCH_SPEC_RELATIVE_STRENGTH_ROTATION_V1.md` (commit 4d69a23)
- **Proof:** A0 accepted CONDITIONAL-PASS, 5 corrections applied, re-accepted

### Step 1 — Contract tests
- **Artifact:** `tests/test_relative_strength_rotation_v1_spec.py` (commit e0a0d52)
- **Proof:** 117 passed, exit 0

### Step 2 — Strategy class scaffold
- **Artifact:** `strategy_variants.py`, `tests/test_relative_strength_rotation_v1_scaffold.py` (commit e66686d)
- **Proof:** 155 passed, exit 0

### Step 3a — Rotation engine decision
- **Artifact:** `ROTATION_ENGINE_DECISION_RELATIVE_STRENGTH_ROTATION_V1.md` (commit 50ec965)
- **Decision:** `DEDICATED_ROTATION_BACKTESTER_REQUIRED`

### Step 3b — RotationBacktester scaffold
- **Artifact:** `rotation_backtester.py`, `tests/test_rotation_backtester_scaffold.py` (commit 1922c1a)
- **Proof:** 198 passed, exit 0

### Step 4 — Rotation feature matrix builder
- **Artifact:** `rotation_feature_matrix.py`, `tests/test_rotation_feature_matrix_builder.py` (commit 239e8f0)
- **Proof:** 235 passed, exit 0

### Step 5a — B2 equal-weight universe benchmark
- **Artifact:** `rotation_benchmark_b2.py`, `tests/test_rotation_benchmark_b2.py` (commit 231ee58)
- **Proof:** 271 passed, exit 0

### Step 5b — Randomized-selection p95 comparator
- **Artifact:** `rotation_random_selection_comparator.py`, `tests/test_rotation_random_selection_comparator.py` (commit 4acd94f)
- **Proof:** 310 passed, exit 0

### Step 6 — Rotation portfolio path engine (RotationBacktester.run)
- **Artifact:** `rotation_backtester.py` fully implemented
- **Proof:** run() produces equity curve, weights_by_date, rebalance_events, hysteresis logic

### Step 7 — RotationBacktester.run toy integration tests
- **Artifact:** tests passing; B1 module added (`rotation_benchmark_b1.py`)
- **Proof:** All tests pass, exit 0

### Step 8 — v1.2 metric-source wiring
- **Artifact:** `rotation_v1_2_metric_adapter.py`, `rotation_v1_2_report_generator.py`, `rotation_v1_2_toy_csv_report.py`, `protocol_v1_2_reporting.py`
- **Proof:** All tests pass; LIVE-GO/RESEARCH-GO tokens forbidden and tested

### Step 9 — Walk-forward adapter
- **Artifact:** `rotation_walk_forward_adapter.py`, `tests/test_rotation_walk_forward_adapter.py`
- **Proof:** Train/test isolation enforced; no train-window leakage; tests pass

### Step 10 — Dry CSV report generation
- **Artifact:** `rotation_v1_2_toy_csv_report.py` fully implemented
- **Proof:** All prior 708 tests passing

### Research Gate 1 — B1 primary benchmark + split spec
- **Artifact:** `rotation_benchmark_b1.py`, `RESEARCH_SPLIT_SPEC_RELATIVE_STRENGTH_ROTATION_V1.md`
- **Proof:** Contract tests pass; split spec frozen (train=3/test=1/step=1)

### Research Gate 2 — Data audit + acquisition plan
- **Artifact:** `rotation_data_audit.py`, `RESEARCH_DATA_ACQUISITION_PLAN_RELATIVE_STRENGTH_ROTATION_V1.md`
- **Proof:** Audit runs; initial result: 7 valid, 8 missing

### Research Gate 3 — Holiday boundary patch
- **Artifact:** `rotation_data_audit.py` — trading_day_slack_days=7 (commit a4b047b)
- **Proof:** 708 tests pass; 2015-01-02 first bars accepted; no fill applied

### Research Gate 4 — Data acquisition (8 missing tickers)
- **Artifact:** `data/{AMD,TSLA,NFLX,AVGO,CRM,INTC,CSCO,IBM}_2015-01-01_2024-12-31.csv` + `data/provenance_ledger.json` (commit 07da3ec)
- **Data audit result:** `research_ready = True`, all 15/15 tickers valid, 2016 rows each
- **Source:** dtwParallel (2015-2018) + brownbear (2019-2024); TSLA ÷3 / AVGO ÷10 harmonization for split consistency
- **Note:** Yahoo Finance was blocked in this environment; provenance ledger records sources and split factors

---

## 🔄 CURRENT

**All infrastructure complete. Data audit: `research_ready = True`.**

Awaiting Research Gate 5 payload from A1_ORCHESTRATOR_GATEKEEPER.

---

## ⏭ NEXT

### Research Gate 5 — Research orchestrator wiring
- **Owner:** A2_LOCAL_IMPLEMENTER_CLAUDE_CODE
- **Task:** Build `rotation_research_orchestrator.py` that chains:
  `data → features → RotationBacktester → B1/B2/p95 → v1.2 adapter → CSV report`
- **Scope:** Walk-forward over 7 splits (WF-01 to WF-07), real CSVs from `data/`
- **Forbidden:** RESEARCH-GO output, LIVE-GO output, parameter changes, yfinance calls
- **Required proof:** pytest -q, exit 0; orchestrator runs without error on toy inputs first

### Research Gate 6 — Actual research run (ONE RUN)
- **Owner:** A0_OWNER_AVI + A1_ORCHESTRATOR_GATEKEEPER (explicit written authorization required)
- **Requires:** RDR-002 drafted and accepted BEFORE execution
- **Forbidden:** Running before RDR-002 exists; any parameter optimization; post-result selection

### Step 12 — RDR-002
- **Owner:** A7_RDR_GIT_AGENT
- **Task:** Draft Research Decision Record for RelativeStrengthRotation_v1
- **Forbidden:** Running research before RDR is accepted; modifying RDR after run

---

## 🔒 BLOCKED UNTIL LATER (require explicit A0 + A1 authorization)

- Full research run with real market data
- `strategy_lab_runner` execution
- Any yfinance call
- Any capital allocation recommendation
- Any LIVE-GO output
- Any RESEARCH-GO output before both v1.1 and v1.2 gates confirm

---

*Last updated: Research Gate 4 PASSED — data_audit research_ready=True*
*This board is the single source of truth for pipeline status.*
