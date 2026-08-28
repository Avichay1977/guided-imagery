"""
Protocol v1.2 metric-source integration tests.

Deterministic toy dicts only. No market data, no backtests, no full runner.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from protocol_v1_2_metric_sources import (
    V1_2_METRIC_FIELDS,
    extract_v1_2_metric_overrides,
    merge_v1_2_metric_overrides,
    has_required_v1_2_metrics,
)
from protocol_v1_2_reporting import build_v1_2_report_row


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_source() -> dict:
    """A source dict carrying every recognized canonical v1.2 metric key."""
    return {
        "strategy_total_return": 0.30,
        "strategy_calmar": 0.80,
        "buy_hold_total_return": 0.50,
        "buy_hold_calmar": 0.90,
        "exposure_matched_bh_total_return": 0.20,
        "exposure_matched_bh_calmar": 0.60,
        "randomized_timing_p95_total_return": 0.25,
        "randomized_timing_p95_calmar": 0.70,
    }


# ---------------------------------------------------------------------------
# 1-8. Extraction of each metric when present
# ---------------------------------------------------------------------------

def test_extracts_strategy_total_return_when_present():
    out = extract_v1_2_metric_overrides({"strategy_total_return": 0.33})
    assert out["strategy_total_return"] == 0.33
    # alias form
    out2 = extract_v1_2_metric_overrides({"total_return": 0.44})
    assert out2["strategy_total_return"] == 0.44


def test_extracts_strategy_calmar_when_present():
    out = extract_v1_2_metric_overrides({"strategy_calmar": 1.1})
    assert out["strategy_calmar"] == 1.1
    out2 = extract_v1_2_metric_overrides({"calmar": 1.2})
    assert out2["strategy_calmar"] == 1.2


def test_extracts_buy_hold_total_return_when_present():
    out = extract_v1_2_metric_overrides({"buy_hold_total_return": 0.55})
    assert out["buy_hold_total_return"] == 0.55
    out2 = extract_v1_2_metric_overrides({"benchmark_total_return": 0.66})
    assert out2["buy_hold_total_return"] == 0.66


def test_extracts_buy_hold_calmar_when_present():
    out = extract_v1_2_metric_overrides({"buy_hold_calmar": 0.95})
    assert out["buy_hold_calmar"] == 0.95
    out2 = extract_v1_2_metric_overrides({"benchmark_calmar": 0.85})
    assert out2["buy_hold_calmar"] == 0.85


def test_extracts_exposure_matched_total_return_when_present():
    out = extract_v1_2_metric_overrides({"exposure_matched_bh_total_return": 0.21})
    assert out["exposure_matched_bh_total_return"] == 0.21
    out2 = extract_v1_2_metric_overrides({"exposure_matched_total_return": 0.22})
    assert out2["exposure_matched_bh_total_return"] == 0.22


def test_extracts_exposure_matched_calmar_when_present():
    out = extract_v1_2_metric_overrides({"exposure_matched_bh_calmar": 0.61})
    assert out["exposure_matched_bh_calmar"] == 0.61
    out2 = extract_v1_2_metric_overrides({"exposure_matched_calmar": 0.62})
    assert out2["exposure_matched_bh_calmar"] == 0.62


def test_extracts_randomized_p95_total_return_when_present():
    out = extract_v1_2_metric_overrides({"randomized_timing_p95_total_return": 0.25})
    assert out["randomized_timing_p95_total_return"] == 0.25


def test_extracts_randomized_p95_calmar_when_present():
    out = extract_v1_2_metric_overrides({"randomized_timing_p95_calmar": 0.70})
    assert out["randomized_timing_p95_calmar"] == 0.70


# ---------------------------------------------------------------------------
# 9-10. p75 must NOT be mapped to p95
# ---------------------------------------------------------------------------

def test_does_not_map_p75_total_return_to_p95():
    out = extract_v1_2_metric_overrides({"randomized_timing_p75_total_return": 0.99})
    assert out["randomized_timing_p95_total_return"] is None


def test_does_not_map_p75_calmar_to_p95():
    out = extract_v1_2_metric_overrides({"randomized_timing_p75_calmar": 0.99})
    assert out["randomized_timing_p95_calmar"] is None


# ---------------------------------------------------------------------------
# 11. Missing metrics remain None
# ---------------------------------------------------------------------------

def test_missing_metrics_remain_none():
    out = extract_v1_2_metric_overrides({})
    assert set(out.keys()) == set(V1_2_METRIC_FIELDS)
    for field in V1_2_METRIC_FIELDS:
        assert out[field] is None


# ---------------------------------------------------------------------------
# 12. Merge preserves existing v1.1 fields
# ---------------------------------------------------------------------------

def test_merge_v1_2_metric_overrides_preserves_existing_v1_1_fields():
    row = {
        "ticker": "TOY",
        "status": "OK",
        "failure_reasons": "CALMAR_BELOW_BENCHMARK",
        "test_calmar": 0.40,
    }
    overrides = extract_v1_2_metric_overrides(_full_source())
    merged = merge_v1_2_metric_overrides(row, overrides)

    # Existing v1.1 fields intact
    assert merged["ticker"] == "TOY"
    assert merged["status"] == "OK"
    assert merged["failure_reasons"] == "CALMAR_BELOW_BENCHMARK"
    assert merged["test_calmar"] == 0.40
    # Overrides added
    assert merged["strategy_total_return"] == 0.30
    # Source row not mutated
    assert "strategy_total_return" not in row


# ---------------------------------------------------------------------------
# 13. Merge does not overwrite existing v1.1 verdict
# ---------------------------------------------------------------------------

def test_merge_does_not_overwrite_existing_v1_1_verdict():
    row = {"v1_1_verdict": "V1_1_NO_GO", "status": "OK"}
    # Even a malicious override trying to flip the verdict is ignored
    overrides = {"v1_1_verdict": "V1_1_RESEARCH_GO", "strategy_total_return": 0.3}
    merged = merge_v1_2_metric_overrides(row, overrides)
    assert merged["v1_1_verdict"] == "V1_1_NO_GO"
    assert merged["strategy_total_return"] == 0.3


# ---------------------------------------------------------------------------
# 14-16. has_required_v1_2_metrics
# ---------------------------------------------------------------------------

def test_has_required_v1_2_metrics_true_when_all_required_present():
    assert has_required_v1_2_metrics(_full_source()) is True


def test_has_required_v1_2_metrics_false_when_total_return_missing():
    src = _full_source()
    src["strategy_total_return"] = None
    assert has_required_v1_2_metrics(src) is False


def test_has_required_v1_2_metrics_false_when_p95_missing():
    src = _full_source()
    del src["randomized_timing_p95_calmar"]
    assert has_required_v1_2_metrics(src) is False


# ---------------------------------------------------------------------------
# 17. Adapter with missing p95 -> TIMING_EDGE_INSUFFICIENT_DATA
# ---------------------------------------------------------------------------

def test_adapter_with_missing_p95_produces_timing_insufficient_data():
    src = _full_source()
    del src["randomized_timing_p95_total_return"]
    del src["randomized_timing_p95_calmar"]
    overrides = extract_v1_2_metric_overrides(src)

    v1_1_row = {"ticker": "TOY", "status": "OK", "v1_1_verdict": "V1_1_NO_GO"}
    row = build_v1_2_report_row(v1_1_row, **overrides)
    assert row["timing_edge_label"] == "TIMING_EDGE_INSUFFICIENT_DATA"
    # exposure side has full data -> classifiable (not insufficient)
    assert row["exposure_edge_label"] != "EXPOSURE_EDGE_INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# 18. Adapter with full overrides can classify timing edge
# ---------------------------------------------------------------------------

def test_adapter_with_full_overrides_can_classify_timing_edge():
    # strategy beats p95 on both -> PASS
    src = _full_source()
    src["strategy_total_return"] = 0.99
    src["strategy_calmar"] = 9.9
    src["randomized_timing_p95_total_return"] = 0.10
    src["randomized_timing_p95_calmar"] = 0.20
    overrides = extract_v1_2_metric_overrides(src)

    v1_1_row = {"ticker": "TOY", "status": "OK", "v1_1_verdict": "V1_1_NO_GO"}
    row = build_v1_2_report_row(v1_1_row, **overrides)
    assert row["timing_edge_label"] == "TIMING_EDGE_PASS"
    # v1.1 verdict still preserved, no upgrade
    assert row["v1_1_verdict_preserved"] == "V1_1_NO_GO"


# ---------------------------------------------------------------------------
# 19. Adapter with missing total return -> EXPOSURE_EDGE_INSUFFICIENT_DATA
# ---------------------------------------------------------------------------

def test_adapter_with_missing_total_return_produces_exposure_insufficient_data():
    src = _full_source()
    del src["strategy_total_return"]
    overrides = extract_v1_2_metric_overrides(src)

    v1_1_row = {"ticker": "TOY", "status": "OK", "v1_1_verdict": "V1_1_NO_GO"}
    row = build_v1_2_report_row(v1_1_row, **overrides)
    assert row["exposure_edge_label"] == "EXPOSURE_EDGE_INSUFFICIENT_DATA"
    # timing also needs strategy_total_return -> also insufficient
    assert row["timing_edge_label"] == "TIMING_EDGE_INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# 20. Metric sources never create LIVE-GO or RESEARCH-GO
# ---------------------------------------------------------------------------

def test_no_live_go_or_research_go_created_by_metric_sources():
    overrides = extract_v1_2_metric_overrides(_full_source())
    merged = merge_v1_2_metric_overrides(
        {"ticker": "TOY", "status": "OK", "v1_1_verdict": "V1_1_NO_GO"},
        overrides,
    )
    for value in merged.values():
        s = str(value)
        assert "LIVE-GO" not in s and "LIVE_GO" not in s
        assert "RESEARCH-GO" not in s and "RESEARCH_GO" not in s

    # And via the adapter end-to-end
    row = build_v1_2_report_row(
        {"ticker": "TOY", "status": "OK", "v1_1_verdict": "V1_1_NO_GO"},
        **overrides,
    )
    assert row["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY"
    for value in row.values():
        s = str(value)
        assert "LIVE-GO" not in s and "LIVE_GO" not in s
    # RESEARCH appears only as preserved v1.1 verdict, never as a v1.2 label
    assert "RESEARCH" not in str(row["v1_2_diagnostic_label"]).upper()
    assert "RESEARCH" not in str(row["exposure_edge_label"]).upper()
    assert "RESEARCH" not in str(row["timing_edge_label"]).upper()
