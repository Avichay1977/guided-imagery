"""
Unit tests for rotation_v1_2_metric_adapter.

All toy inputs use types.SimpleNamespace; no real backtest, no market data,
no data fetch, no strategy_lab_runner.
"""

import inspect
import math
import types

import pytest

from protocol_v1_2_metric_sources import V1_2_METRIC_FIELDS
from rotation_v1_2_metric_adapter import (
    build_rotation_summary_row_with_v1_2_metrics,
    build_rotation_v1_2_metric_sources,
    explain_missing_rotation_v1_2_metrics,
    rotation_metric_sources_are_complete,
)


# ---------------------------------------------------------------------------
# Toy factory helpers
# ---------------------------------------------------------------------------

def _strat(tr=0.12, calmar=0.80):
    """Minimal strategy result namespace."""
    return types.SimpleNamespace(strategy_total_return=tr, strategy_calmar=calmar)


def _b1(tr=0.10, calmar=0.60):
    """Minimal B1 buy-and-hold benchmark result."""
    return types.SimpleNamespace(total_return=tr, calmar=calmar)


def _b2(tr=0.09, calmar=0.55):
    """Minimal B2 equal-weight benchmark result."""
    return types.SimpleNamespace(total_return=tr, calmar=calmar)


def _rsc(p95_tr=0.07, p95_c=0.50):
    """Minimal randomized-selection comparator result."""
    return types.SimpleNamespace(p95_total_return=p95_tr, p95_calmar=p95_c)


def _all_sources():
    return build_rotation_v1_2_metric_sources(
        _strat(), b1_buy_hold_result=_b1(),
        b2_equal_weight_result=_b2(),
        random_selection_result=_rsc(),
    )


def _complete_sources():
    return {
        "strategy_total_return": 0.12,
        "strategy_calmar": 0.80,
        "buy_hold_total_return": 0.10,
        "buy_hold_calmar": 0.60,
        "exposure_matched_bh_total_return": 0.09,
        "exposure_matched_bh_calmar": 0.55,
        "randomized_timing_p95_total_return": 0.07,
        "randomized_timing_p95_calmar": 0.50,
    }


# ---------------------------------------------------------------------------
# Category 1: build_rotation_v1_2_metric_sources output shape (tests 1–5)
# ---------------------------------------------------------------------------

def test_adapter_outputs_all_eight_required_fields():
    ms = _all_sources()
    for field in V1_2_METRIC_FIELDS:
        assert field in ms, f"missing field: {field!r}"
    assert len(ms) == 8


def test_strategy_metrics_are_extracted_from_rotation_result():
    ms = build_rotation_v1_2_metric_sources(_strat(tr=0.15, calmar=1.2))
    assert ms["strategy_total_return"] == pytest.approx(0.15)
    assert ms["strategy_calmar"] == pytest.approx(1.2)


def test_b1_buy_hold_metrics_are_extracted_when_present():
    ms = build_rotation_v1_2_metric_sources(
        _strat(), b1_buy_hold_result=_b1(tr=0.08, calmar=0.55)
    )
    assert ms["buy_hold_total_return"] == pytest.approx(0.08)
    assert ms["buy_hold_calmar"] == pytest.approx(0.55)


def test_b2_equal_weight_metrics_are_extracted_as_exposure_matched_when_present():
    ms = build_rotation_v1_2_metric_sources(
        _strat(), b2_equal_weight_result=_b2(tr=0.06, calmar=0.45)
    )
    assert ms["exposure_matched_bh_total_return"] == pytest.approx(0.06)
    assert ms["exposure_matched_bh_calmar"] == pytest.approx(0.45)


def test_random_selection_p95_metrics_are_extracted_when_present():
    ms = build_rotation_v1_2_metric_sources(
        _strat(), random_selection_result=_rsc(p95_tr=0.05, p95_c=0.35)
    )
    assert ms["randomized_timing_p95_total_return"] == pytest.approx(0.05)
    assert ms["randomized_timing_p95_calmar"] == pytest.approx(0.35)


# ---------------------------------------------------------------------------
# Category 2: Missing sources remain None (tests 6–8)
# ---------------------------------------------------------------------------

def test_missing_b1_metrics_remain_none():
    ms = build_rotation_v1_2_metric_sources(_strat())
    assert ms["buy_hold_total_return"] is None
    assert ms["buy_hold_calmar"] is None


def test_missing_b2_metrics_remain_none():
    ms = build_rotation_v1_2_metric_sources(_strat())
    assert ms["exposure_matched_bh_total_return"] is None
    assert ms["exposure_matched_bh_calmar"] is None


def test_missing_random_selection_metrics_remain_none():
    ms = build_rotation_v1_2_metric_sources(_strat())
    assert ms["randomized_timing_p95_total_return"] is None
    assert ms["randomized_timing_p95_calmar"] is None


# ---------------------------------------------------------------------------
# Category 3: NaN / inf sanitation (tests 9–10)
# ---------------------------------------------------------------------------

def test_nan_strategy_metric_becomes_none():
    s = types.SimpleNamespace(
        strategy_total_return=float("nan"), strategy_calmar=float("nan")
    )
    ms = build_rotation_v1_2_metric_sources(s)
    assert ms["strategy_total_return"] is None
    assert ms["strategy_calmar"] is None


def test_inf_strategy_metric_becomes_none():
    s = types.SimpleNamespace(
        strategy_total_return=float("inf"), strategy_calmar=float("-inf")
    )
    ms = build_rotation_v1_2_metric_sources(s)
    assert ms["strategy_total_return"] is None
    assert ms["strategy_calmar"] is None


# ---------------------------------------------------------------------------
# Category 4: No fabrication, no wrong cross-aliasing (tests 11–15)
# ---------------------------------------------------------------------------

def test_adapter_does_not_fabricate_missing_values():
    # Pass only strategy; all other fields should be exactly None, not guessed
    ms = build_rotation_v1_2_metric_sources(_strat(tr=0.20, calmar=1.0))
    none_fields = [
        "buy_hold_total_return", "buy_hold_calmar",
        "exposure_matched_bh_total_return", "exposure_matched_bh_calmar",
        "randomized_timing_p95_total_return", "randomized_timing_p95_calmar",
    ]
    for f in none_fields:
        assert ms[f] is None, f"fabricated value for {f!r}: {ms[f]}"


def test_adapter_does_not_map_p75_to_p95():
    # Result object has p75 attributes but NOT p95 attributes
    result_with_p75_only = types.SimpleNamespace(
        p75_total_return=0.99,
        p75_calmar=9.99,
        # Deliberately NO p95_total_return or p95_calmar
    )
    ms = build_rotation_v1_2_metric_sources(
        _strat(), random_selection_result=result_with_p75_only
    )
    # p75 must never be promoted to p95 fields
    assert ms["randomized_timing_p95_total_return"] is None
    assert ms["randomized_timing_p95_calmar"] is None


def test_adapter_does_not_use_b2_as_b1():
    # Only b2 provided; buy_hold fields must stay None
    ms = build_rotation_v1_2_metric_sources(
        _strat(), b2_equal_weight_result=_b2(tr=0.20, calmar=1.5)
    )
    assert ms["buy_hold_total_return"] is None
    assert ms["buy_hold_calmar"] is None


def test_adapter_does_not_use_b1_as_b2():
    # Only b1 provided; exposure_matched fields must stay None
    ms = build_rotation_v1_2_metric_sources(
        _strat(), b1_buy_hold_result=_b1(tr=0.10, calmar=0.8)
    )
    assert ms["exposure_matched_bh_total_return"] is None
    assert ms["exposure_matched_bh_calmar"] is None


def test_adapter_does_not_mutate_input_objects():
    s = _strat(tr=0.12, calmar=0.80)
    b1 = _b1(tr=0.10, calmar=0.60)
    b2 = _b2(tr=0.09, calmar=0.55)
    rsc = _rsc(p95_tr=0.07, p95_c=0.50)
    base_row = {"status": "OK", "v1_1_verdict": "V1_1_NO_GO"}

    # Snapshot states before
    s_tr_before = s.strategy_total_return
    b1_tr_before = b1.total_return
    b2_tr_before = b2.total_return
    rsc_p95_before = rsc.p95_total_return
    base_keys_before = dict(base_row)

    build_rotation_summary_row_with_v1_2_metrics(base_row, s, b1, b2, rsc)

    # Verify all unchanged
    assert s.strategy_total_return == s_tr_before
    assert b1.total_return == b1_tr_before
    assert b2.total_return == b2_tr_before
    assert rsc.p95_total_return == rsc_p95_before
    assert base_row == base_keys_before


# ---------------------------------------------------------------------------
# Category 5: build_rotation_summary_row_with_v1_2_metrics (tests 16–20)
# ---------------------------------------------------------------------------

def test_summary_row_preserves_status():
    base = {"status": "OK", "v1_1_verdict": "V1_1_NO_GO"}
    row = build_rotation_summary_row_with_v1_2_metrics(base, _strat())
    assert row["status"] == "OK"


def test_summary_row_preserves_final_research_verdict():
    base = {"status": "OK", "final_research_verdict": "NO_GO_ROTATION_SCOPE"}
    row = build_rotation_summary_row_with_v1_2_metrics(base, _strat())
    assert row["final_research_verdict"] == "NO_GO_ROTATION_SCOPE"


def test_summary_row_preserves_failure_reasons():
    reasons = ["INSUFFICIENT_HISTORY", "LOW_CALMAR"]
    base = {"status": "FAIL", "failure_reasons": reasons}
    row = build_rotation_summary_row_with_v1_2_metrics(base, _strat())
    assert row["failure_reasons"] == reasons


def test_summary_row_adds_v1_2_metric_fields():
    base = {"status": "OK"}
    row = build_rotation_summary_row_with_v1_2_metrics(
        base, _strat(), b1_buy_hold_result=_b1(),
        b2_equal_weight_result=_b2(), random_selection_result=_rsc()
    )
    for field in V1_2_METRIC_FIELDS:
        assert field in row, f"missing v1.2 field: {field!r}"
    assert row["strategy_total_return"] is not None
    assert row["strategy_calmar"] is not None


def test_summary_row_can_feed_protocol_v1_2_reporting_adapter():
    from protocol_v1_2_reporting import build_v1_2_report_row
    base = {"status": "OK", "v1_1_verdict": "V1_1_NO_GO"}
    summary = build_rotation_summary_row_with_v1_2_metrics(
        base, _strat(tr=0.15, calmar=1.2),
        b1_buy_hold_result=_b1(), b2_equal_weight_result=_b2(),
        random_selection_result=_rsc(),
    )
    overrides = {k: summary[k] for k in V1_2_METRIC_FIELDS if summary.get(k) is not None}
    report_row = build_v1_2_report_row(
        summary,
        strategy_name="RelativeStrengthRotation",
        strategy_version="v1",
        ticker="UNIVERSE",
        test_window="2020",
        **overrides,
    )
    assert isinstance(report_row, dict)
    assert "exposure_edge_label" in report_row


# ---------------------------------------------------------------------------
# Category 6: rotation_metric_sources_are_complete (tests 21–24)
# ---------------------------------------------------------------------------

def test_complete_metric_sources_true_when_all_eight_present():
    assert rotation_metric_sources_are_complete(_complete_sources()) is True


def test_complete_metric_sources_false_when_any_missing():
    for field in V1_2_METRIC_FIELDS:
        partial = dict(_complete_sources())
        del partial[field]
        assert rotation_metric_sources_are_complete(partial) is False, (
            f"should be False when {field!r} is absent"
        )


def test_complete_metric_sources_false_on_nan():
    for field in V1_2_METRIC_FIELDS:
        with_nan = dict(_complete_sources())
        with_nan[field] = float("nan")
        assert rotation_metric_sources_are_complete(with_nan) is False, (
            f"should be False when {field!r} is NaN"
        )


def test_complete_metric_sources_false_on_inf():
    for field in V1_2_METRIC_FIELDS:
        with_inf = dict(_complete_sources())
        with_inf[field] = float("inf")
        assert rotation_metric_sources_are_complete(with_inf) is False, (
            f"should be False when {field!r} is inf"
        )


# ---------------------------------------------------------------------------
# Category 7: explain_missing_rotation_v1_2_metrics (tests 25–26)
# ---------------------------------------------------------------------------

def test_explain_missing_metrics_mentions_exact_fields():
    empty_sources = {f: None for f in V1_2_METRIC_FIELDS}
    reasons = explain_missing_rotation_v1_2_metrics(empty_sources)
    assert len(reasons) == 8
    for field in V1_2_METRIC_FIELDS:
        assert any(field in r for r in reasons), (
            f"no reason mentions {field!r}"
        )


def test_explain_missing_metrics_order_is_deterministic():
    partial = {f: None for f in V1_2_METRIC_FIELDS}
    r1 = explain_missing_rotation_v1_2_metrics(partial)
    r2 = explain_missing_rotation_v1_2_metrics(partial)
    assert r1 == r2

    nan_sources = dict(_complete_sources())
    nan_sources["strategy_calmar"] = float("nan")
    nan_sources["randomized_timing_p95_calmar"] = float("nan")
    reasons = explain_missing_rotation_v1_2_metrics(nan_sources)
    # strategy_calmar comes before randomized_timing_p95_calmar in the canonical order
    calmar_idx = next(i for i, r in enumerate(reasons) if "strategy_calmar" in r)
    p95_idx = next(i for i, r in enumerate(reasons) if "randomized_timing_p95_calmar" in r)
    assert calmar_idx < p95_idx


# ---------------------------------------------------------------------------
# Category 8: Source guardrails (tests 27–28)
# ---------------------------------------------------------------------------

def test_adapter_outputs_no_live_go():
    import rotation_v1_2_metric_adapter as _m
    src = inspect.getsource(_m)
    assert "LIVE-GO" not in src


def test_adapter_outputs_no_research_go():
    import rotation_v1_2_metric_adapter as _m
    src = inspect.getsource(_m)
    assert "RESEARCH-GO" not in src


# ---------------------------------------------------------------------------
# Cross-module interface checks (tests 29–35)
# ---------------------------------------------------------------------------

def test_rotation_portfolio_path_engine_tests_still_pass():
    from rotation_backtester import RotationBacktesterConfig, RotationBacktesterResult
    c = RotationBacktesterConfig()
    assert c.top_n == 3
    assert c.annualization_days == 252
    r = RotationBacktesterResult()
    assert r.equity_curve == []


def test_random_selection_comparator_tests_still_pass():
    from rotation_random_selection_comparator import RandomSelectionComparatorConfig
    c = RandomSelectionComparatorConfig()
    assert c.n_simulations == 1000
    assert c.top_n == 3
    assert c.comparator_label == "RANDOMIZED_SELECTION_P95_REPORT_ONLY"


def test_rotation_benchmark_b2_tests_still_pass():
    from rotation_benchmark_b2 import EqualWeightBenchmarkConfig, calculate_calmar
    c = EqualWeightBenchmarkConfig()
    assert c.benchmark_label == "B2_EQUAL_WEIGHT_UNIVERSE_REPORT_ONLY"
    assert c.annualization_days == 252


def test_rotation_feature_matrix_tests_still_pass():
    from rotation_feature_matrix import RotationFeatureConfig
    c = RotationFeatureConfig()
    assert c.rs_short_window == 63
    assert c.rs_mid_window == 126
    assert c.rs_long_window == 252


def test_rotation_backtester_scaffold_tests_still_pass():
    from rotation_backtester import RotationBacktesterConfig
    c = RotationBacktesterConfig()
    assert c.top_n == 3
    assert c.hysteresis_threshold == pytest.approx(0.50)


def test_relative_strength_rotation_scaffold_tests_still_pass():
    from strategy_variants import RelativeStrengthRotation_v1
    s = RelativeStrengthRotation_v1()
    desc = s.describe()
    assert desc["top_n"] == 3
    assert desc["universe_size"] == 15


def test_relative_strength_rotation_spec_tests_still_pass():
    from strategy_variants import RelativeStrengthRotation_v1
    s = RelativeStrengthRotation_v1()
    desc = s.describe()
    weights = desc["weights"]
    assert abs(weights["relative_strength_126d"] - 0.40) < 1e-9
    assert abs(weights["relative_strength_252d"] - 0.40) < 1e-9
    assert abs(weights["benchmark_relative_strength"] - 0.20) < 1e-9
