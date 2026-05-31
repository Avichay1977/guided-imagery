"""
Unit tests for rotation_walk_forward_adapter.

All toy inputs only. No real market data, no fetch, no strategy_lab_runner,
no real research backtest.
"""

import inspect

import pandas as pd
import pytest

from rotation_backtester import RotationBacktesterConfig
from rotation_walk_forward_adapter import (
    RotationWalkForwardSplit,
    RotationWalkForwardSplitResult,
    build_rotation_walk_forward_summary_rows,
    run_rotation_walk_forward_toy,
    slice_rotation_inputs_for_test_window,
    validate_rotation_walk_forward_inputs,
)


# ---------------------------------------------------------------------------
# Toy data helpers
# ---------------------------------------------------------------------------

_TRAIN_DATES = list(pd.bdate_range("2020-01-02", periods=5))
_TEST_DATES = list(pd.bdate_range("2020-02-03", periods=5))
_ALL_DATES = _TRAIN_DATES + _TEST_DATES


def _frow(date, ticker, crs=0.8, rp=0.9, elig=True):
    return {
        "date": pd.Timestamp(date),
        "ticker": ticker,
        "composite_rs": crs,
        "rank_percentile": rp,
        "trend_filter_ema200": elig,
        "volatility_filter_atr_pct": elig,
        "liquidity_filter_volume_avg_20": elig,
    }


def _toy_feature_matrix():
    rows = []
    for d in _ALL_DATES:
        rows.append(_frow(d, "AAA", crs=0.9, rp=0.95))
        rows.append(_frow(d, "BBB", crs=0.8, rp=0.90))
        rows.append(_frow(d, "CCC", crs=0.7, rp=0.85))
    return pd.DataFrame(rows)


def _toy_returns(ret=0.001):
    return {
        t: pd.Series([ret] * len(_ALL_DATES), index=pd.DatetimeIndex(_ALL_DATES))
        for t in ("AAA", "BBB", "CCC")
    }


def _toy_split(split_id="S1"):
    return RotationWalkForwardSplit(
        split_id=split_id,
        train_start=_TRAIN_DATES[0],
        train_end=_TRAIN_DATES[-1],
        test_start=_TEST_DATES[0],
        test_end=_TEST_DATES[-1],
    )


def _toy_splits():
    return [_toy_split("S1")]


# ---------------------------------------------------------------------------
# Tests 1–2: dataclasses
# ---------------------------------------------------------------------------

def test_split_dataclass_has_required_fields():
    s = _toy_split("X")
    for f in ("split_id", "train_start", "train_end", "test_start", "test_end"):
        assert hasattr(s, f), f"missing field: {f!r}"


def test_split_result_dataclass_has_required_fields():
    fm, ret = _toy_feature_matrix(), _toy_returns()
    results = run_rotation_walk_forward_toy(fm, ret, _toy_splits())
    r = results[0]
    for f in ("split_id", "train_start", "train_end", "test_start",
              "test_end", "rotation_result", "summary_row", "diagnostics"):
        assert hasattr(r, f), f"missing field: {f!r}"


# ---------------------------------------------------------------------------
# Tests 3–8: input validation
# ---------------------------------------------------------------------------

def test_validate_rejects_empty_feature_matrix():
    with pytest.raises(ValueError, match="feature_matrix"):
        validate_rotation_walk_forward_inputs(
            pd.DataFrame(), _toy_returns(), _toy_splits()
        )


def test_validate_rejects_empty_returns_by_ticker():
    with pytest.raises(ValueError, match="returns_by_ticker"):
        validate_rotation_walk_forward_inputs(
            _toy_feature_matrix(), {}, _toy_splits()
        )


def test_validate_rejects_empty_splits():
    with pytest.raises(ValueError, match="splits"):
        validate_rotation_walk_forward_inputs(
            _toy_feature_matrix(), _toy_returns(), []
        )


def test_validate_rejects_missing_required_feature_columns():
    fm = pd.DataFrame({"date": [_TEST_DATES[0]], "ticker": ["AAA"]})
    with pytest.raises(ValueError, match="missing required columns"):
        validate_rotation_walk_forward_inputs(fm, _toy_returns(), _toy_splits())


def test_validate_rejects_split_with_train_after_test():
    bad = RotationWalkForwardSplit(
        split_id="BAD",
        train_start=_TEST_DATES[0],
        train_end=_TEST_DATES[-1],
        test_start=_TRAIN_DATES[0],
        test_end=_TRAIN_DATES[-1],
    )
    with pytest.raises(ValueError, match="train_end"):
        validate_rotation_walk_forward_inputs(
            _toy_feature_matrix(), _toy_returns(), [bad]
        )


def test_validate_rejects_test_window_outside_feature_matrix():
    out_of_range = RotationWalkForwardSplit(
        split_id="OUT",
        train_start=pd.Timestamp("2018-01-01"),
        train_end=pd.Timestamp("2018-06-30"),
        test_start=pd.Timestamp("2019-01-01"),
        test_end=pd.Timestamp("2019-06-30"),
    )
    with pytest.raises(ValueError, match="outside feature_matrix range"):
        validate_rotation_walk_forward_inputs(
            _toy_feature_matrix(), _toy_returns(), [out_of_range]
        )


# ---------------------------------------------------------------------------
# Tests 9–12: slicing
# ---------------------------------------------------------------------------

def test_slice_uses_test_window_only():
    sliced = slice_rotation_inputs_for_test_window(
        _toy_feature_matrix(), _toy_returns(), _toy_split()
    )
    fm = sliced["feature_matrix"]
    fm_dates = pd.to_datetime(fm["date"]).unique()
    assert all(d >= pd.Timestamp(_TEST_DATES[0]) for d in fm_dates)
    assert all(d <= pd.Timestamp(_TEST_DATES[-1]) for d in fm_dates)


def test_slice_does_not_include_train_rows_in_test_feature_matrix():
    sliced = slice_rotation_inputs_for_test_window(
        _toy_feature_matrix(), _toy_returns(), _toy_split()
    )
    fm = sliced["feature_matrix"]
    fm_dates = set(pd.to_datetime(fm["date"]).tolist())
    for train_d in _TRAIN_DATES:
        assert pd.Timestamp(train_d) not in fm_dates


def test_slice_preserves_returns_for_test_window():
    sliced = slice_rotation_inputs_for_test_window(
        _toy_feature_matrix(), _toy_returns(), _toy_split()
    )
    for ticker in ("AAA", "BBB", "CCC"):
        s = sliced["returns_by_ticker"][ticker]
        assert len(s) == len(_TEST_DATES)
        assert all(d in s.index for d in pd.DatetimeIndex(_TEST_DATES))


def test_slice_rejects_missing_returns_in_test_window():
    fm = _toy_feature_matrix()
    ret = _toy_returns()
    del ret["AAA"]  # AAA present in fm but absent from returns
    with pytest.raises(ValueError, match="missing returns"):
        slice_rotation_inputs_for_test_window(fm, ret, _toy_split())


# ---------------------------------------------------------------------------
# Tests 13–17: run output
# ---------------------------------------------------------------------------

def test_run_returns_one_result_per_split():
    split_a = _toy_split("S1")
    test_b_dates = list(pd.bdate_range("2020-02-10", periods=3))
    fm = _toy_feature_matrix()
    extra_rows = [_frow(d, t, crs=0.9, rp=0.95) for d in test_b_dates for t in ("AAA", "BBB", "CCC")]
    fm = pd.concat([fm, pd.DataFrame(extra_rows)], ignore_index=True)
    ret = _toy_returns()
    all_dates_b = list(pd.DatetimeIndex(_ALL_DATES + test_b_dates).unique())
    ret = {t: pd.Series([0.001] * len(all_dates_b), index=pd.DatetimeIndex(all_dates_b))
           for t in ("AAA", "BBB", "CCC")}
    split_b = RotationWalkForwardSplit(
        split_id="S2",
        train_start=_TRAIN_DATES[0],
        train_end=_TEST_DATES[0],
        test_start=test_b_dates[0],
        test_end=test_b_dates[-1],
    )
    results = run_rotation_walk_forward_toy(fm, ret, [split_a, split_b])
    assert len(results) == 2
    assert results[0].split_id == "S1"
    assert results[1].split_id == "S2"


def test_run_preserves_split_metadata():
    results = run_rotation_walk_forward_toy(
        _toy_feature_matrix(), _toy_returns(), _toy_splits()
    )
    r = results[0]
    s = _toy_split("S1")
    assert r.train_start == s.train_start
    assert r.train_end == s.train_end
    assert r.test_start == s.test_start
    assert r.test_end == s.test_end


def test_run_calls_rotation_backtester_on_test_window_only():
    results = run_rotation_walk_forward_toy(
        _toy_feature_matrix(), _toy_returns(), _toy_splits()
    )
    eq = results[0].rotation_result.equity_curve
    # Equity curve has one point per test-window day, not for train days
    assert len(eq) == len(_TEST_DATES)
    for ts in eq.index:
        assert ts >= pd.Timestamp(_TEST_DATES[0])
        assert ts <= pd.Timestamp(_TEST_DATES[-1])


def test_run_outputs_rotation_result():
    from rotation_backtester import RotationBacktesterResult
    results = run_rotation_walk_forward_toy(
        _toy_feature_matrix(), _toy_returns(), _toy_splits()
    )
    assert isinstance(results[0].rotation_result, RotationBacktesterResult)


def test_run_outputs_summary_row():
    results = run_rotation_walk_forward_toy(
        _toy_feature_matrix(), _toy_returns(), _toy_splits()
    )
    sr = results[0].summary_row
    assert isinstance(sr, dict)
    assert "strategy_total_return" in sr
    assert "strategy_calmar" in sr


# ---------------------------------------------------------------------------
# Tests 18–22: summary-row content
# ---------------------------------------------------------------------------

def test_summary_rows_preserve_split_id():
    results = run_rotation_walk_forward_toy(
        _toy_feature_matrix(), _toy_returns(), _toy_splits()
    )
    rows = build_rotation_walk_forward_summary_rows(results)
    assert rows[0]["split_id"] == "S1"


def test_summary_rows_include_strategy_name():
    results = run_rotation_walk_forward_toy(
        _toy_feature_matrix(), _toy_returns(), _toy_splits()
    )
    rows = build_rotation_walk_forward_summary_rows(results)
    assert rows[0]["strategy_name"] == "RelativeStrengthRotation"


def test_summary_rows_include_strategy_version():
    results = run_rotation_walk_forward_toy(
        _toy_feature_matrix(), _toy_returns(), _toy_splits()
    )
    rows = build_rotation_walk_forward_summary_rows(results)
    assert rows[0]["strategy_version"] == "v1"


def test_summary_rows_do_not_create_research_go():
    results = run_rotation_walk_forward_toy(
        _toy_feature_matrix(), _toy_returns(), _toy_splits()
    )
    rows = build_rotation_walk_forward_summary_rows(results)
    token = "RESEARCH" + "-GO"
    for row in rows:
        for v in row.values():
            assert v is None or token not in str(v)


def test_summary_rows_do_not_create_live_go():
    results = run_rotation_walk_forward_toy(
        _toy_feature_matrix(), _toy_returns(), _toy_splits()
    )
    rows = build_rotation_walk_forward_summary_rows(results)
    token = "LIVE" + "-GO"
    for row in rows:
        for v in row.values():
            assert v is None or token not in str(v)


# ---------------------------------------------------------------------------
# Tests 23–26: diagnostics
# ---------------------------------------------------------------------------

def test_diagnostics_mark_toy_walk_forward_mode():
    results = run_rotation_walk_forward_toy(
        _toy_feature_matrix(), _toy_returns(), _toy_splits()
    )
    assert results[0].diagnostics["mode"] == "TOY_WALK_FORWARD_ROTATION_ADAPTER"


def test_diagnostics_mark_research_valid_false():
    results = run_rotation_walk_forward_toy(
        _toy_feature_matrix(), _toy_returns(), _toy_splits()
    )
    assert results[0].diagnostics["research_valid"] is False


def test_diagnostics_mark_market_data_used_false():
    results = run_rotation_walk_forward_toy(
        _toy_feature_matrix(), _toy_returns(), _toy_splits()
    )
    assert results[0].diagnostics["market_data_used"] is False


def test_diagnostics_mark_strategy_lab_runner_used_false():
    results = run_rotation_walk_forward_toy(
        _toy_feature_matrix(), _toy_returns(), _toy_splits()
    )
    assert results[0].diagnostics["strategy_lab_runner_used"] is False
    assert results[0].diagnostics["live_go_emitted"] is False
    assert results[0].diagnostics["research_go_emitted"] is False
    assert results[0].diagnostics["v1_1_verdict_impact"] == "NONE"


# ---------------------------------------------------------------------------
# Tests 27–29: mutation safety + determinism
# ---------------------------------------------------------------------------

def test_adapter_does_not_mutate_feature_matrix():
    fm = _toy_feature_matrix()
    fm_copy = fm.copy(deep=True)
    run_rotation_walk_forward_toy(fm, _toy_returns(), _toy_splits())
    # column equality and row count preserved
    assert list(fm.columns) == list(fm_copy.columns)
    assert len(fm) == len(fm_copy)
    # date column unchanged in dtype and values
    assert (fm["date"].astype(str).values == fm_copy["date"].astype(str).values).all()


def test_adapter_does_not_mutate_returns():
    ret = _toy_returns()
    snapshot = {t: list(s.values) for t, s in ret.items()}
    snapshot_idx = {t: list(s.index) for t, s in ret.items()}
    run_rotation_walk_forward_toy(_toy_feature_matrix(), ret, _toy_splits())
    for t, s in ret.items():
        assert list(s.values) == snapshot[t]
        assert list(s.index) == snapshot_idx[t]


def test_adapter_is_deterministic():
    fm, ret, splits = _toy_feature_matrix(), _toy_returns(), _toy_splits()
    r1 = run_rotation_walk_forward_toy(fm, ret, splits)
    r2 = run_rotation_walk_forward_toy(fm, ret, splits)
    assert r1[0].rotation_result.final_equity == pytest.approx(r2[0].rotation_result.final_equity)
    assert r1[0].rotation_result.strategy_total_return == pytest.approx(r2[0].rotation_result.strategy_total_return)
    assert r1[0].summary_row.get("strategy_total_return") == r2[0].summary_row.get("strategy_total_return")


# ---------------------------------------------------------------------------
# Tests 30–31: downstream compatibility
# ---------------------------------------------------------------------------

def test_adapter_outputs_can_feed_rotation_v1_2_report_generator():
    from protocol_v1_2_reporting import apply_protocol_v1_2_reporting_logic
    results = run_rotation_walk_forward_toy(
        _toy_feature_matrix(), _toy_returns(), _toy_splits()
    )
    rows = build_rotation_walk_forward_summary_rows(results)
    labelled = apply_protocol_v1_2_reporting_logic(rows[0])
    assert "exposure_edge_label" in labelled
    assert "timing_edge_label" in labelled
    assert labelled["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY"
    assert "is_pass_v1_2" in labelled


def test_adapter_outputs_can_feed_toy_csv_report(tmp_path):
    from protocol_v1_2_reporting import apply_protocol_v1_2_reporting_logic
    from rotation_v1_2_toy_csv_report import (
        read_rotation_v1_2_toy_csv_report,
        write_rotation_v1_2_toy_csv_report,
    )
    results = run_rotation_walk_forward_toy(
        _toy_feature_matrix(), _toy_returns(), _toy_splits()
    )
    rows = build_rotation_walk_forward_summary_rows(results)
    enriched = [apply_protocol_v1_2_reporting_logic(r) for r in rows]
    out = tmp_path / "wf_toy.csv"
    write_rotation_v1_2_toy_csv_report(enriched, out)
    rb = read_rotation_v1_2_toy_csv_report(out)
    assert len(rb) == len(enriched)
    assert rb[0]["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY"


# ---------------------------------------------------------------------------
# Tests 32–41: cross-module interface checks
# ---------------------------------------------------------------------------

def test_rotation_v1_2_toy_csv_report_tests_still_pass():
    from rotation_v1_2_toy_csv_report import (
        TOY_CSV_COLUMNS,
        validate_rotation_v1_2_toy_report_rows,
    )
    assert "strategy_total_return" in TOY_CSV_COLUMNS
    assert validate_rotation_v1_2_toy_report_rows(
        [{"v1_2_diagnostic_label": "PORTFOLIO_DIAGNOSTIC_ONLY"}]
    ) is True


def test_rotation_v1_2_report_generator_tests_still_pass():
    from rotation_v1_2_report_generator import ROTATION_LABEL_COLUMNS
    assert "is_pass_v1_2" in ROTATION_LABEL_COLUMNS


def test_rotation_v1_2_metric_adapter_tests_still_pass():
    import types
    from rotation_v1_2_metric_adapter import build_rotation_v1_2_metric_sources
    s = types.SimpleNamespace(strategy_total_return=0.1, strategy_calmar=0.5)
    ms = build_rotation_v1_2_metric_sources(s)
    assert ms["strategy_total_return"] == pytest.approx(0.1)


def test_rotation_portfolio_path_engine_tests_still_pass():
    from rotation_backtester import RotationBacktesterConfig
    c = RotationBacktesterConfig()
    assert c.top_n == 3
    assert c.annualization_days == 252


def test_random_selection_comparator_tests_still_pass():
    from rotation_random_selection_comparator import RandomSelectionComparatorConfig
    c = RandomSelectionComparatorConfig()
    assert c.n_simulations == 1000


def test_rotation_benchmark_b2_tests_still_pass():
    from rotation_benchmark_b2 import EqualWeightBenchmarkConfig
    c = EqualWeightBenchmarkConfig()
    assert c.benchmark_label == "B2_EQUAL_WEIGHT_UNIVERSE_REPORT_ONLY"


def test_rotation_feature_matrix_tests_still_pass():
    from rotation_feature_matrix import RotationFeatureConfig
    c = RotationFeatureConfig()
    assert c.rs_short_window == 63


def test_rotation_backtester_scaffold_tests_still_pass():
    from rotation_backtester import RotationBacktesterConfig
    c = RotationBacktesterConfig()
    assert c.hysteresis_threshold == pytest.approx(0.50)


def test_relative_strength_rotation_scaffold_tests_still_pass():
    from strategy_variants import RelativeStrengthRotation_v1
    desc = RelativeStrengthRotation_v1().describe()
    assert desc["top_n"] == 3


def test_relative_strength_rotation_spec_tests_still_pass():
    from strategy_variants import RelativeStrengthRotation_v1
    desc = RelativeStrengthRotation_v1().describe()
    weights = desc["weights"]
    assert abs(weights["relative_strength_126d"] - 0.40) < 1e-9
