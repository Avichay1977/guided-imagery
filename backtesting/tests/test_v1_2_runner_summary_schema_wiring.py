"""
v1.2 Runner Summary Schema Wiring tests.

Deterministic toy dicts only. No market data, no backtests, no full runner.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from protocol_v1_2_metric_sources import (
    V1_2_METRIC_FIELDS,
    build_summary_row_with_v1_2_metrics,
    extract_v1_2_metric_overrides,
)
from protocol_v1_2_reporting import build_v1_2_report_row


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _v1_1_split_row(**overrides) -> dict:
    """Minimal v1.1 split-level row (strategy_lab format)."""
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
        test_random_p75_calmar=0.70,   # legacy p75, must never become p95
        status="OK",
        failure_reasons="",
        v1_1_verdict="V1_1_NO_GO",
    )
    base.update(overrides)
    return base


def _full_metric_source() -> dict:
    """Source dict with all eight canonical v1.2 metric fields present."""
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
# 1. All v1.2 metric source fields are added to the output
# ---------------------------------------------------------------------------

def test_summary_schema_adds_all_v1_2_metric_source_fields():
    result = build_summary_row_with_v1_2_metrics(_v1_1_split_row(), [_full_metric_source()])
    for field in V1_2_METRIC_FIELDS:
        assert field in result, f"v1.2 metric field '{field}' missing from output"


# ---------------------------------------------------------------------------
# 2. Existing v1.1 fields are preserved
# ---------------------------------------------------------------------------

def test_summary_schema_preserves_existing_v1_1_fields():
    base = _v1_1_split_row()
    result = build_summary_row_with_v1_2_metrics(base, [_full_metric_source()])
    for key, value in base.items():
        assert key in result, f"v1.1 key '{key}' missing from output"
        assert result[key] == value, f"v1.1 key '{key}' was modified"


# ---------------------------------------------------------------------------
# 3. Input row is not mutated
# ---------------------------------------------------------------------------

def test_summary_schema_does_not_mutate_input_row():
    base = _v1_1_split_row()
    original_keys = set(base.keys())
    original_values = dict(base)

    build_summary_row_with_v1_2_metrics(base, [_full_metric_source()])

    assert set(base.keys()) == original_keys
    for k, v in original_values.items():
        assert base[k] == v


# ---------------------------------------------------------------------------
# 4. v1.1 NO-GO verdict preserved
# ---------------------------------------------------------------------------

def test_summary_schema_preserves_v1_1_no_go_verdict():
    base = _v1_1_split_row(v1_1_verdict="V1_1_NO_GO")
    result = build_summary_row_with_v1_2_metrics(base, [_full_metric_source()])
    assert result["v1_1_verdict"] == "V1_1_NO_GO"


# ---------------------------------------------------------------------------
# 5. v1.1 RESEARCH-GO verdict preserved without creating a new one
# ---------------------------------------------------------------------------

def test_summary_schema_preserves_v1_1_research_go_verdict_without_creating_new_one():
    base = _v1_1_split_row(v1_1_verdict="V1_1_RESEARCH_GO")
    result = build_summary_row_with_v1_2_metrics(base, [_full_metric_source()])
    assert result["v1_1_verdict"] == "V1_1_RESEARCH_GO"
    # No v1.2 diagnostic label of any kind added by this function
    assert "v1_2_diagnostic_label" not in result
    assert "exposure_edge_label" not in result


# ---------------------------------------------------------------------------
# 6. Missing metrics remain None
# ---------------------------------------------------------------------------

def test_summary_schema_missing_metrics_remain_none():
    result = build_summary_row_with_v1_2_metrics(_v1_1_split_row(), [])
    for field in V1_2_METRIC_FIELDS:
        assert result[field] is None, f"expected None for absent field '{field}'"

    result2 = build_summary_row_with_v1_2_metrics(_v1_1_split_row())
    for field in V1_2_METRIC_FIELDS:
        assert result2[field] is None


# ---------------------------------------------------------------------------
# 7-11. Each metric group is extracted from a source dict
# ---------------------------------------------------------------------------

def test_summary_schema_extracts_strategy_total_return_from_source():
    result = build_summary_row_with_v1_2_metrics(
        _v1_1_split_row(),
        [{"strategy_total_return": 0.33}],
    )
    assert result["strategy_total_return"] == 0.33


def test_summary_schema_extracts_strategy_calmar_from_source():
    result = build_summary_row_with_v1_2_metrics(
        _v1_1_split_row(),
        [{"strategy_calmar": 1.5}],
    )
    assert result["strategy_calmar"] == 1.5


def test_summary_schema_extracts_buy_hold_metrics_from_source():
    src = {"buy_hold_total_return": 0.55, "buy_hold_calmar": 0.95}
    result = build_summary_row_with_v1_2_metrics(_v1_1_split_row(), [src])
    assert result["buy_hold_total_return"] == 0.55
    assert result["buy_hold_calmar"] == 0.95


def test_summary_schema_extracts_exposure_matched_metrics_from_source():
    src = {
        "exposure_matched_bh_total_return": 0.21,
        "exposure_matched_bh_calmar": 0.61,
    }
    result = build_summary_row_with_v1_2_metrics(_v1_1_split_row(), [src])
    assert result["exposure_matched_bh_total_return"] == 0.21
    assert result["exposure_matched_bh_calmar"] == 0.61


def test_summary_schema_extracts_randomized_p95_metrics_from_source():
    src = {
        "randomized_timing_p95_total_return": 0.25,
        "randomized_timing_p95_calmar": 0.70,
    }
    result = build_summary_row_with_v1_2_metrics(_v1_1_split_row(), [src])
    assert result["randomized_timing_p95_total_return"] == 0.25
    assert result["randomized_timing_p95_calmar"] == 0.70


# ---------------------------------------------------------------------------
# 12. p75 is NOT aliased to p95
# ---------------------------------------------------------------------------

def test_summary_schema_does_not_alias_p75_to_p95():
    src = {
        "randomized_timing_p75_total_return": 0.99,
        "randomized_timing_p75_calmar": 0.99,
    }
    result = build_summary_row_with_v1_2_metrics(_v1_1_split_row(), [src])
    assert result["randomized_timing_p95_total_return"] is None
    assert result["randomized_timing_p95_calmar"] is None


# ---------------------------------------------------------------------------
# 13. Legacy p75 field in the base row remains unchanged
# ---------------------------------------------------------------------------

def test_summary_schema_keeps_legacy_p75_fields_unchanged():
    base = _v1_1_split_row(test_random_p75_calmar=0.70)
    result = build_summary_row_with_v1_2_metrics(base, [_full_metric_source()])
    assert result["test_random_p75_calmar"] == 0.70
    # And p95 came from the explicit source, not from the p75 field
    assert result["randomized_timing_p95_calmar"] == 0.70  # same value, different field
    # Verify they're distinct fields
    assert "test_random_p75_calmar" in result
    assert "randomized_timing_p95_calmar" in result


# ---------------------------------------------------------------------------
# 14. No LIVE-GO in output
# ---------------------------------------------------------------------------

def test_summary_schema_no_live_go_output():
    result = build_summary_row_with_v1_2_metrics(_v1_1_split_row(), [_full_metric_source()])
    for value in result.values():
        s = str(value)
        assert "LIVE-GO" not in s and "LIVE_GO" not in s


# ---------------------------------------------------------------------------
# 15. Enriched row can feed the v1.2 reporting adapter
# ---------------------------------------------------------------------------

def test_summary_schema_can_feed_v1_2_reporting_adapter():
    enriched = build_summary_row_with_v1_2_metrics(
        _v1_1_split_row(),
        [_full_metric_source()],
    )
    # Extract canonical overrides from the enriched row
    overrides = extract_v1_2_metric_overrides(enriched)
    report_row = build_v1_2_report_row(enriched, **overrides)

    assert report_row["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY"
    assert report_row["protocol_version"] == "v1.2"
    assert report_row["v1_1_verdict_preserved"] == "V1_1_NO_GO"


# ---------------------------------------------------------------------------
# 16. Full metrics enable PASS/FAIL classification end-to-end
# ---------------------------------------------------------------------------

def test_summary_schema_with_full_metrics_allows_exposure_and_timing_classification():
    # strategy clearly beats both comparators
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
    enriched = build_summary_row_with_v1_2_metrics(_v1_1_split_row(), [src])
    overrides = extract_v1_2_metric_overrides(enriched)
    report_row = build_v1_2_report_row(enriched, **overrides)

    assert report_row["exposure_edge_label"] == "EXPOSURE_EDGE_PASS"
    assert report_row["timing_edge_label"] == "TIMING_EDGE_PASS"
    # v1.1 NO-GO is never upgraded
    assert report_row["v1_1_verdict_preserved"] == "V1_1_NO_GO"
    assert report_row["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY"


# ---------------------------------------------------------------------------
# 17. Missing p95 → TIMING_EDGE_INSUFFICIENT_DATA
# ---------------------------------------------------------------------------

def test_summary_schema_with_missing_p95_keeps_timing_insufficient_data():
    src = {
        "strategy_total_return": 0.30,
        "strategy_calmar": 0.80,
        "buy_hold_total_return": 0.50,
        "buy_hold_calmar": 0.90,
        "exposure_matched_bh_total_return": 0.10,
        "exposure_matched_bh_calmar": 0.40,
        # p95 intentionally absent
    }
    enriched = build_summary_row_with_v1_2_metrics(_v1_1_split_row(), [src])
    overrides = extract_v1_2_metric_overrides(enriched)
    report_row = build_v1_2_report_row(enriched, **overrides)

    assert report_row["timing_edge_label"] == "TIMING_EDGE_INSUFFICIENT_DATA"
    # exposure has full data → classifiable
    assert report_row["exposure_edge_label"] != "EXPOSURE_EDGE_INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# 18. Missing total return → EXPOSURE_EDGE_INSUFFICIENT_DATA
# ---------------------------------------------------------------------------

def test_summary_schema_with_missing_total_return_keeps_exposure_insufficient_data():
    src = {
        # strategy_total_return intentionally absent
        "strategy_calmar": 0.80,
        "buy_hold_calmar": 0.90,
        "exposure_matched_bh_calmar": 0.60,
        "randomized_timing_p95_total_return": 0.25,
        "randomized_timing_p95_calmar": 0.70,
    }
    enriched = build_summary_row_with_v1_2_metrics(_v1_1_split_row(), [src])
    overrides = extract_v1_2_metric_overrides(enriched)
    report_row = build_v1_2_report_row(enriched, **overrides)

    assert report_row["exposure_edge_label"] == "EXPOSURE_EDGE_INSUFFICIENT_DATA"
    assert report_row["timing_edge_label"] == "TIMING_EDGE_INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# 19. failure_reasons not overwritten
# ---------------------------------------------------------------------------

def test_summary_schema_failure_reasons_not_overwritten():
    base = _v1_1_split_row(failure_reasons="CALMAR_BELOW_BENCHMARK")
    # Even if a source somehow contains a failure_reasons key, it must not
    # overwrite the v1.1 failure_reasons.
    malicious_src = dict(_full_metric_source())
    malicious_src["failure_reasons"] = "SHOULD_NOT_APPEAR"
    result = build_summary_row_with_v1_2_metrics(base, [malicious_src])
    assert result["failure_reasons"] == "CALMAR_BELOW_BENCHMARK"


# ---------------------------------------------------------------------------
# 20. Deterministic
# ---------------------------------------------------------------------------

def test_summary_schema_is_deterministic():
    base = _v1_1_split_row()
    src = [_full_metric_source()]
    r1 = build_summary_row_with_v1_2_metrics(base, src)
    r2 = build_summary_row_with_v1_2_metrics(base, src)
    assert r1 == r2
    # Base row untouched
    assert "strategy_total_return" not in base
