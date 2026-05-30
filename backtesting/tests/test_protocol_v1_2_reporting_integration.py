"""
Protocol v1.2 reporting-integration tests.

Deterministic toy rows / DataFrames only. No market data, no fetching, no
backtests, no full-runner execution.
"""

import pandas as pd

from protocol_v1_2_exposure_fair import REQUIRED_V1_2_OUTPUT_COLUMNS
from protocol_v1_2_reporting import (
    add_v1_2_columns,
    build_v1_2_report_row,
    normalize_v1_1_verdict,
)


# ---------------------------------------------------------------------------
# Toy v1.1 rows (mirror the walk-forward / strategy-lab row shape)
# ---------------------------------------------------------------------------

def _v1_1_row(**overrides) -> dict:
    base = dict(
        ticker="TOY",
        strategy_name="TrendPullbackConfluence",
        strategy_version="v1",
        test_start="2018-01-01",
        test_end="2019-01-01",
        test_total_trades=10,
        test_calmar=0.80,
        test_benchmark_calmar=0.90,
        test_exposure_matched_calmar=0.60,
        test_random_p75_calmar=0.70,
        status="OK",
        failure_reasons="",
        v1_1_verdict="V1_1_NO_GO",
    )
    base.update(overrides)
    return base


# Full set of explicit metrics so edges can actually be classified PASS/FAIL.
def _full_metrics(**overrides) -> dict:
    base = dict(
        strategy_total_return=0.30,
        strategy_calmar=0.80,
        buy_hold_total_return=0.50,
        buy_hold_calmar=0.90,
        exposure_matched_bh_total_return=0.20,
        exposure_matched_bh_calmar=0.60,
        randomized_timing_p95_total_return=0.25,
        randomized_timing_p95_calmar=0.70,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. Outputs required columns
# ---------------------------------------------------------------------------

def test_v1_2_reporting_outputs_required_columns():
    row = build_v1_2_report_row(_v1_1_row(), **_full_metrics())
    assert list(row.keys()) == REQUIRED_V1_2_OUTPUT_COLUMNS


# ---------------------------------------------------------------------------
# 2. Preserves v1.1 NO-GO
# ---------------------------------------------------------------------------

def test_v1_2_reporting_preserves_v1_1_no_go():
    row = build_v1_2_report_row(_v1_1_row(v1_1_verdict="V1_1_NO_GO"), **_full_metrics())
    assert row["v1_1_verdict_preserved"] == "V1_1_NO_GO"


# ---------------------------------------------------------------------------
# 3. Preserves v1.1 RESEARCH-GO verbatim without modifying it
# ---------------------------------------------------------------------------

def test_v1_2_reporting_preserves_v1_1_research_go_without_modifying():
    src = _v1_1_row(v1_1_verdict="V1_1_RESEARCH_GO")
    row = build_v1_2_report_row(src, **_full_metrics())
    assert row["v1_1_verdict_preserved"] == "V1_1_RESEARCH_GO"
    # The source row must not have been mutated
    assert src["v1_1_verdict"] == "V1_1_RESEARCH_GO"


# ---------------------------------------------------------------------------
# 4. EXPOSURE_EDGE_PASS does not change v1.1 NO-GO
# ---------------------------------------------------------------------------

def test_v1_2_exposure_edge_pass_does_not_change_v1_1_no_go():
    # Make exposure edge clearly PASS
    metrics = _full_metrics(
        strategy_total_return=0.99,
        strategy_calmar=9.9,
        exposure_matched_bh_total_return=0.10,
        exposure_matched_bh_calmar=0.20,
    )
    row = build_v1_2_report_row(_v1_1_row(v1_1_verdict="V1_1_NO_GO"), **metrics)
    assert row["exposure_edge_label"] == "EXPOSURE_EDGE_PASS"
    assert row["v1_1_verdict_preserved"] == "V1_1_NO_GO"
    assert row["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY"


# ---------------------------------------------------------------------------
# 5. TIMING_EDGE_PASS does not create RESEARCH-GO
# ---------------------------------------------------------------------------

def test_v1_2_timing_edge_pass_does_not_create_research_go():
    metrics = _full_metrics(
        strategy_total_return=0.99,
        strategy_calmar=9.9,
        randomized_timing_p95_total_return=0.10,
        randomized_timing_p95_calmar=0.20,
    )
    row = build_v1_2_report_row(_v1_1_row(v1_1_verdict="V1_1_NO_GO"), **metrics)
    assert row["timing_edge_label"] == "TIMING_EDGE_PASS"
    assert "RESEARCH" not in row["v1_2_diagnostic_label"].upper()
    assert row["v1_1_verdict_preserved"] == "V1_1_NO_GO"


# ---------------------------------------------------------------------------
# 6. Failure reasons include exposure failure
# ---------------------------------------------------------------------------

def test_v1_2_failure_reasons_include_exposure_failure():
    metrics = _full_metrics(
        strategy_total_return=0.05,   # below EM 0.20
        strategy_calmar=0.10,         # below EM 0.60
    )
    row = build_v1_2_report_row(_v1_1_row(), **metrics)
    assert row["exposure_edge_label"] == "EXPOSURE_EDGE_FAIL"
    assert "EXPOSURE_EDGE_FAIL" in row["failure_reasons"]


# ---------------------------------------------------------------------------
# 7. Failure reasons include timing failure
# ---------------------------------------------------------------------------

def test_v1_2_failure_reasons_include_timing_failure():
    metrics = _full_metrics(
        strategy_total_return=0.22,   # beats EM 0.20, below p95 0.25
        strategy_calmar=0.80,         # beats EM 0.60 and p95 0.70
    )
    row = build_v1_2_report_row(_v1_1_row(), **metrics)
    assert row["timing_edge_label"] == "TIMING_EDGE_FAIL"
    assert "TIMING_EDGE_FAIL" in row["failure_reasons"]


# ---------------------------------------------------------------------------
# 8. v1.2 labels are separate fields from v1.1 verdict
# ---------------------------------------------------------------------------

def test_v1_2_labels_are_separate_from_v1_1_verdict():
    row = build_v1_2_report_row(_v1_1_row(), **_full_metrics())
    # Distinct keys, distinct value namespaces
    assert "v1_1_verdict_preserved" in row
    assert "exposure_edge_label" in row
    assert "timing_edge_label" in row
    assert row["exposure_edge_label"].startswith("EXPOSURE_EDGE_")
    assert row["timing_edge_label"].startswith("TIMING_EDGE_")
    assert row["v1_1_verdict_preserved"].startswith("V1_1_")


# ---------------------------------------------------------------------------
# 9. Never outputs LIVE-GO
# ---------------------------------------------------------------------------

def test_v1_2_reporting_never_outputs_live_go():
    for s_ret, s_cal in [(0.99, 9.9), (-0.9, -0.9), (0.0, 0.0)]:
        row = build_v1_2_report_row(
            _v1_1_row(),
            **_full_metrics(strategy_total_return=s_ret, strategy_calmar=s_cal),
        )
        for value in row.values():
            assert "LIVE-GO" not in str(value)
            assert "LIVE_GO" not in str(value)


# ---------------------------------------------------------------------------
# 10. Protocol version is v1.2
# ---------------------------------------------------------------------------

def test_v1_2_reporting_protocol_version_is_v1_2():
    row = build_v1_2_report_row(_v1_1_row(), **_full_metrics())
    assert row["protocol_version"] == "v1.2"


# ---------------------------------------------------------------------------
# 11. Handles insufficient metrics (v1.1 rows lack total returns / p95)
# ---------------------------------------------------------------------------

def test_v1_2_reporting_handles_insufficient_metrics():
    # No explicit metrics: only mapped calmars are present; returns + p95 absent
    row = build_v1_2_report_row(_v1_1_row())
    assert row["exposure_edge_label"] == "EXPOSURE_EDGE_INSUFFICIENT_DATA"
    assert row["timing_edge_label"] == "TIMING_EDGE_INSUFFICIENT_DATA"
    # Still produces full column set and preserves verdict
    assert list(row.keys()) == REQUIRED_V1_2_OUTPUT_COLUMNS
    assert row["v1_1_verdict_preserved"] == "V1_1_NO_GO"


# ---------------------------------------------------------------------------
# 12. Does not require market data (pure dict in, dict out)
# ---------------------------------------------------------------------------

def test_v1_2_reporting_does_not_require_market_data():
    # Build from a minimal dict with no price series whatsoever
    minimal = {"ticker": "X", "status": "OK", "v1_1_verdict": "V1_1_NO_GO"}
    row = build_v1_2_report_row(minimal, **_full_metrics())
    assert row["ticker"] == "X"
    assert row["v1_1_verdict_preserved"] == "V1_1_NO_GO"
    assert list(row.keys()) == REQUIRED_V1_2_OUTPUT_COLUMNS


# ---------------------------------------------------------------------------
# 13. Uses existing exposure-matched metrics when supplied
# ---------------------------------------------------------------------------

def test_v1_2_reporting_uses_existing_exposure_matched_metrics_when_supplied():
    # The mapped exposure-matched calmar from the v1.1 row should flow through
    src = _v1_1_row(test_exposure_matched_calmar=0.55)
    # Supply a strategy calmar above it and total returns to enable PASS/FAIL
    row = build_v1_2_report_row(
        src,
        strategy_total_return=0.40,
        strategy_calmar=0.95,
        exposure_matched_bh_total_return=0.30,
        # exposure_matched_bh_calmar intentionally NOT overridden -> comes from row (0.55)
    )
    assert row["exposure_matched_bh_calmar"] == 0.55
    # strategy 0.95 > 0.55 calmar and 0.40 > 0.30 return -> PASS
    assert row["exposure_edge_label"] == "EXPOSURE_EDGE_PASS"


# ---------------------------------------------------------------------------
# 14. Uses existing randomized p95 metrics when supplied
# ---------------------------------------------------------------------------

def test_v1_2_reporting_uses_existing_randomized_p95_metrics_when_supplied():
    row = build_v1_2_report_row(
        _v1_1_row(),
        strategy_total_return=0.40,
        strategy_calmar=0.95,
        randomized_timing_p95_total_return=0.10,
        randomized_timing_p95_calmar=0.20,
    )
    assert row["randomized_timing_p95_total_return"] == 0.10
    assert row["randomized_timing_p95_calmar"] == 0.20
    assert row["timing_edge_label"] == "TIMING_EDGE_PASS"


# ---------------------------------------------------------------------------
# 15. Deterministic + DataFrame adapter preserves v1.1 columns
# ---------------------------------------------------------------------------

def test_v1_2_reporting_is_deterministic():
    src = _v1_1_row()
    r1 = build_v1_2_report_row(src, **_full_metrics())
    r2 = build_v1_2_report_row(src, **_full_metrics())
    assert r1 == r2

    # DataFrame adapter: existing columns preserved, v1.2 columns appended
    df = pd.DataFrame([_v1_1_row(), _v1_1_row(ticker="TOY2")])
    out = add_v1_2_columns(
        df,
        strategy_total_return=0.40,
        strategy_calmar=0.95,
        buy_hold_total_return=0.50,
        buy_hold_calmar=0.90,
        exposure_matched_bh_total_return=0.20,
        exposure_matched_bh_calmar=0.60,
        randomized_timing_p95_total_return=0.25,
        randomized_timing_p95_calmar=0.70,
    )
    # Original v1.1 columns intact
    for col in df.columns:
        assert col in out.columns
    # v1.2 diagnostic columns added (status already exists, so failure_reasons
    # collides -> note v1.1 'failure_reasons' must remain unchanged)
    assert "exposure_edge_label" in out.columns
    assert "timing_edge_label" in out.columns
    assert "protocol_version" in out.columns
    # v1.1 failure_reasons column preserved (not overwritten by v1.2 prefix logic)
    assert (out["failure_reasons"] == df["failure_reasons"].values).all()
    assert "v1_2_failure_reasons" in out.columns
    assert len(out) == 2
