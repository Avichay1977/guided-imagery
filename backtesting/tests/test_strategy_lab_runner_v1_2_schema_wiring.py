"""
strategy_lab_runner v1.2 schema wiring tests.

Tests the enrich_lab_row() integration point that future runners use to
attach v1.2 metric source fields to summary rows.

Deterministic toy dicts only. No market data, no backtests, no full runner
execution.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from protocol_v1_2_metric_sources import (
    V1_2_METRIC_FIELDS,
    extract_v1_2_metric_overrides,
)
from protocol_v1_2_reporting import build_v1_2_report_row
from strategy_lab_runner import enrich_lab_row


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _v1_1_lab_row(**overrides) -> dict:
    """Minimal strategy_lab split-level row (v1.1 runner output shape)."""
    base = dict(
        split_id=0,
        ticker="TOY",
        strategy_name="TrendPullbackConfluence",
        strategy_version="v1",
        test_start="2020-01-01",
        test_end="2021-01-01",
        test_total_trades=12,
        test_calmar=0.80,
        test_benchmark_calmar=0.90,
        test_exposure_matched_calmar=0.60,
        test_random_p75_calmar=0.70,   # legacy p75 — must never become p95
        status="OK",
        failure_reasons="",
        v1_1_verdict="V1_1_NO_GO",
    )
    base.update(overrides)
    return base


def _full_metric_source() -> dict:
    """Source dict with all eight v1.2 canonical metric fields present."""
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
# 1. All v1.2 metric fields present in enriched row
# ---------------------------------------------------------------------------

def test_runner_summary_row_can_include_all_v1_2_metric_fields():
    result = enrich_lab_row(_v1_1_lab_row(), [_full_metric_source()])
    for field in V1_2_METRIC_FIELDS:
        assert field in result, f"v1.2 metric field '{field}' missing"


# ---------------------------------------------------------------------------
# 2. Existing v1.1 status preserved
# ---------------------------------------------------------------------------

def test_runner_summary_row_preserves_existing_v1_1_status():
    base = _v1_1_lab_row(status="OK", failure_reasons="CALMAR_BELOW_BENCHMARK")
    result = enrich_lab_row(base, [_full_metric_source()])
    assert result["status"] == "OK"
    assert result["failure_reasons"] == "CALMAR_BELOW_BENCHMARK"


# ---------------------------------------------------------------------------
# 3. Existing v1.1 research verdict preserved without creating a new one
# ---------------------------------------------------------------------------

def test_runner_summary_row_preserves_existing_final_research_verdict():
    base = _v1_1_lab_row(v1_1_verdict="V1_1_RESEARCH_GO")
    result = enrich_lab_row(base, [_full_metric_source()])
    assert result["v1_1_verdict"] == "V1_1_RESEARCH_GO"
    # enrich_lab_row must NOT add any v1.2 diagnostic label
    assert "v1_2_diagnostic_label" not in result
    assert "exposure_edge_label" not in result


# ---------------------------------------------------------------------------
# 4. Base row not mutated
# ---------------------------------------------------------------------------

def test_runner_summary_row_does_not_mutate_base_row():
    base = _v1_1_lab_row()
    original_keys = set(base.keys())
    original_values = dict(base)

    enrich_lab_row(base, [_full_metric_source()])

    assert set(base.keys()) == original_keys
    for k, v in original_values.items():
        assert base[k] == v


# ---------------------------------------------------------------------------
# 5. Missing metrics are None
# ---------------------------------------------------------------------------

def test_runner_summary_row_missing_metrics_are_none():
    result_empty = enrich_lab_row(_v1_1_lab_row(), [])
    result_none = enrich_lab_row(_v1_1_lab_row())
    for field in V1_2_METRIC_FIELDS:
        assert result_empty[field] is None
        assert result_none[field] is None


# ---------------------------------------------------------------------------
# 6. Extracts strategy_total_return
# ---------------------------------------------------------------------------

def test_runner_summary_row_extracts_strategy_total_return_when_available():
    result = enrich_lab_row(_v1_1_lab_row(), [{"strategy_total_return": 0.33}])
    assert result["strategy_total_return"] == 0.33


# ---------------------------------------------------------------------------
# 7. Extracts strategy_calmar
# ---------------------------------------------------------------------------

def test_runner_summary_row_extracts_strategy_calmar_when_available():
    result = enrich_lab_row(_v1_1_lab_row(), [{"strategy_calmar": 1.5}])
    assert result["strategy_calmar"] == 1.5


# ---------------------------------------------------------------------------
# 8. Extracts buy_hold metrics
# ---------------------------------------------------------------------------

def test_runner_summary_row_extracts_buy_hold_metrics_when_available():
    src = {"buy_hold_total_return": 0.55, "buy_hold_calmar": 0.95}
    result = enrich_lab_row(_v1_1_lab_row(), [src])
    assert result["buy_hold_total_return"] == 0.55
    assert result["buy_hold_calmar"] == 0.95


# ---------------------------------------------------------------------------
# 9. Extracts exposure-matched metrics
# ---------------------------------------------------------------------------

def test_runner_summary_row_extracts_exposure_matched_metrics_when_available():
    src = {
        "exposure_matched_bh_total_return": 0.21,
        "exposure_matched_bh_calmar": 0.61,
    }
    result = enrich_lab_row(_v1_1_lab_row(), [src])
    assert result["exposure_matched_bh_total_return"] == 0.21
    assert result["exposure_matched_bh_calmar"] == 0.61


# ---------------------------------------------------------------------------
# 10. Extracts randomized p95 metrics
# ---------------------------------------------------------------------------

def test_runner_summary_row_extracts_randomized_p95_metrics_when_available():
    src = {
        "randomized_timing_p95_total_return": 0.25,
        "randomized_timing_p95_calmar": 0.70,
    }
    result = enrich_lab_row(_v1_1_lab_row(), [src])
    assert result["randomized_timing_p95_total_return"] == 0.25
    assert result["randomized_timing_p95_calmar"] == 0.70


# ---------------------------------------------------------------------------
# 11. p75 not aliased to p95
# ---------------------------------------------------------------------------

def test_runner_summary_row_does_not_alias_p75_to_p95():
    src = {
        "randomized_timing_p75_total_return": 0.99,
        "randomized_timing_p75_calmar": 0.99,
    }
    result = enrich_lab_row(_v1_1_lab_row(), [src])
    assert result["randomized_timing_p95_total_return"] is None
    assert result["randomized_timing_p95_calmar"] is None


# ---------------------------------------------------------------------------
# 12. Legacy p75 column in base row preserved unchanged
# ---------------------------------------------------------------------------

def test_runner_summary_row_preserves_legacy_p75_columns():
    base = _v1_1_lab_row(test_random_p75_calmar=0.70)
    result = enrich_lab_row(base, [_full_metric_source()])
    assert result["test_random_p75_calmar"] == 0.70
    # Distinct from the v1.2 p95 field
    assert "randomized_timing_p95_calmar" in result
    assert result["randomized_timing_p95_calmar"] == 0.70  # came from source, not from p75


# ---------------------------------------------------------------------------
# 13. Does not create RESEARCH-GO
# ---------------------------------------------------------------------------

def test_runner_summary_row_does_not_create_research_go():
    result = enrich_lab_row(_v1_1_lab_row(v1_1_verdict="V1_1_NO_GO"), [_full_metric_source()])
    for value in result.values():
        assert "RESEARCH-GO" not in str(value) and "RESEARCH_GO" not in str(value), (
            f"RESEARCH-GO found in enriched row: {value!r}"
        )
    assert "v1_2_diagnostic_label" not in result


# ---------------------------------------------------------------------------
# 14. Does not emit LIVE-GO
# ---------------------------------------------------------------------------

def test_runner_summary_row_does_not_emit_live_go():
    result = enrich_lab_row(_v1_1_lab_row(), [_full_metric_source()])
    for value in result.values():
        assert "LIVE-GO" not in str(value) and "LIVE_GO" not in str(value)


# ---------------------------------------------------------------------------
# 15. Enriched row feeds v1.2 reporting adapter
# ---------------------------------------------------------------------------

def test_runner_summary_row_can_feed_v1_2_reporting_adapter():
    enriched = enrich_lab_row(_v1_1_lab_row(), [_full_metric_source()])
    overrides = extract_v1_2_metric_overrides(enriched)
    report = build_v1_2_report_row(enriched, **overrides)

    assert report["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY"
    assert report["protocol_version"] == "v1.2"
    assert report["v1_1_verdict_preserved"] == "V1_1_NO_GO"


# ---------------------------------------------------------------------------
# 16. Full metrics -> exposure edge classifiable (PASS or FAIL, not INSUFFICIENT)
# ---------------------------------------------------------------------------

def test_runner_summary_row_with_full_metrics_can_generate_exposure_edge_label():
    # strategy clearly beats exposure-matched comparator on both criteria
    src = {
        "strategy_total_return": 0.99,
        "strategy_calmar": 9.9,
        "buy_hold_total_return": 0.50,
        "buy_hold_calmar": 0.90,
        "exposure_matched_bh_total_return": 0.10,
        "exposure_matched_bh_calmar": 0.20,
        "randomized_timing_p95_total_return": 0.05,
        "randomized_timing_p95_calmar": 0.10,
    }
    enriched = enrich_lab_row(_v1_1_lab_row(), [src])
    overrides = extract_v1_2_metric_overrides(enriched)
    report = build_v1_2_report_row(enriched, **overrides)

    assert report["exposure_edge_label"] == "EXPOSURE_EDGE_PASS"
    assert report["timing_edge_label"] == "TIMING_EDGE_PASS"
    # v1.1 NO-GO never upgraded
    assert report["v1_1_verdict_preserved"] == "V1_1_NO_GO"


# ---------------------------------------------------------------------------
# 17. Missing p95 -> TIMING_EDGE_INSUFFICIENT_DATA
# ---------------------------------------------------------------------------

def test_runner_summary_row_with_missing_p95_generates_timing_insufficient_data():
    src = {
        "strategy_total_return": 0.30,
        "strategy_calmar": 0.80,
        "buy_hold_total_return": 0.50,
        "buy_hold_calmar": 0.90,
        "exposure_matched_bh_total_return": 0.10,
        "exposure_matched_bh_calmar": 0.40,
        # p95 intentionally absent
    }
    enriched = enrich_lab_row(_v1_1_lab_row(), [src])
    overrides = extract_v1_2_metric_overrides(enriched)
    report = build_v1_2_report_row(enriched, **overrides)

    assert report["timing_edge_label"] == "TIMING_EDGE_INSUFFICIENT_DATA"
    assert report["exposure_edge_label"] != "EXPOSURE_EDGE_INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# 18. Missing total return -> EXPOSURE_EDGE_INSUFFICIENT_DATA
# ---------------------------------------------------------------------------

def test_runner_summary_row_with_missing_total_return_generates_exposure_insufficient_data():
    src = {
        # strategy_total_return intentionally absent
        "strategy_calmar": 0.80,
        "buy_hold_calmar": 0.90,
        "exposure_matched_bh_calmar": 0.60,
        "randomized_timing_p95_total_return": 0.25,
        "randomized_timing_p95_calmar": 0.70,
    }
    enriched = enrich_lab_row(_v1_1_lab_row(), [src])
    overrides = extract_v1_2_metric_overrides(enriched)
    report = build_v1_2_report_row(enriched, **overrides)

    assert report["exposure_edge_label"] == "EXPOSURE_EDGE_INSUFFICIENT_DATA"
    assert report["timing_edge_label"] == "TIMING_EDGE_INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# 19. failure_reasons not overwritten
# ---------------------------------------------------------------------------

def test_runner_summary_row_failure_reasons_not_overwritten():
    base = _v1_1_lab_row(failure_reasons="CALMAR_BELOW_BENCHMARK")
    malicious_src = dict(_full_metric_source())
    malicious_src["failure_reasons"] = "SHOULD_NOT_APPEAR"
    result = enrich_lab_row(base, [malicious_src])
    assert result["failure_reasons"] == "CALMAR_BELOW_BENCHMARK"


# ---------------------------------------------------------------------------
# 20. Deterministic
# ---------------------------------------------------------------------------

def test_runner_summary_row_is_deterministic():
    base = _v1_1_lab_row()
    src = [_full_metric_source()]
    r1 = enrich_lab_row(base, src)
    r2 = enrich_lab_row(base, src)
    assert r1 == r2
    # base row untouched
    assert "strategy_total_return" not in base
