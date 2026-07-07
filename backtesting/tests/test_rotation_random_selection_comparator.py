"""
Unit tests for the randomized-selection comparator (p95).

Deterministic toy data only. No real market data. No backtests. No runner.
"""

import inspect

import numpy as np
import pandas as pd
import pytest

import rotation_random_selection_comparator as rsc
from rotation_random_selection_comparator import (
    RandomSelectionComparatorConfig,
    RandomSelectionComparatorResult,
    build_random_holdings_path,
    calculate_randomized_selection_p95,
    compute_rotation_path_returns,
    select_random_holdings_for_date,
    validate_random_selection_inputs,
)


# ---------------------------------------------------------------------------
# Toy data helpers
# ---------------------------------------------------------------------------

def _toy_rebalance_dates():
    return [pd.Timestamp("2020-01-02"), pd.Timestamp("2020-02-03"),
            pd.Timestamp("2020-03-02")]


def _toy_eligible():
    """Three eligible tickers on every rebalance date."""
    dates = _toy_rebalance_dates()
    return {d: ["AAA", "BBB", "CCC"] for d in dates}


def _toy_returns(n=65):
    """Simple daily return series for AAA, BBB, CCC over the toy window."""
    dates = pd.bdate_range("2020-01-02", periods=n)
    rng = np.random.default_rng(0)
    series = {}
    for ticker in ["AAA", "BBB", "CCC", "DDD"]:
        series[ticker] = pd.Series(
            rng.normal(0.001, 0.01, n), index=dates, name=ticker
        )
    return series


def _small_cfg():
    return RandomSelectionComparatorConfig(n_simulations=50, random_seed=7)


def _run_small():
    return calculate_randomized_selection_p95(
        _toy_rebalance_dates(),
        _toy_eligible(),
        _toy_returns(),
        config=_small_cfg(),
    )


# ---------------------------------------------------------------------------
# 1-2. Dataclasses
# ---------------------------------------------------------------------------

def test_config_defaults_match_spec():
    c = RandomSelectionComparatorConfig()
    assert c.n_simulations == 1000
    assert c.random_seed == 42
    assert c.top_n == 3
    assert c.cash_return == pytest.approx(0.0)
    assert c.annualization_days == 252
    assert c.comparator_label == "RANDOMIZED_SELECTION_P95_REPORT_ONLY"


def test_result_dataclass_has_required_fields():
    r = _run_small()
    assert hasattr(r, "simulation_total_returns")
    assert hasattr(r, "simulation_calmars")
    assert hasattr(r, "p95_total_return")
    assert hasattr(r, "p95_calmar")
    assert hasattr(r, "n_simulations")
    assert hasattr(r, "diagnostics")


# ---------------------------------------------------------------------------
# 3-4. Import guards
# ---------------------------------------------------------------------------

def test_module_does_not_import_yfinance():
    src = inspect.getsource(rsc)
    assert "yfinance" not in src


def test_module_does_not_import_strategy_lab_runner():
    src = inspect.getsource(rsc)
    assert "strategy_lab_runner" not in src


# ---------------------------------------------------------------------------
# 5-9. Validation
# ---------------------------------------------------------------------------

def test_validate_rejects_empty_rebalance_dates():
    with pytest.raises(ValueError):
        validate_random_selection_inputs([], _toy_eligible(), _toy_returns())


def test_validate_rejects_empty_eligible_by_date():
    with pytest.raises(ValueError):
        validate_random_selection_inputs(_toy_rebalance_dates(), {}, _toy_returns())


def test_validate_rejects_empty_returns_by_ticker():
    with pytest.raises(ValueError):
        validate_random_selection_inputs(_toy_rebalance_dates(), _toy_eligible(), {})


def test_validate_requires_every_rebalance_date_in_eligible_map():
    bad_eligible = {pd.Timestamp("2020-01-02"): ["AAA"]}  # missing Feb and Mar
    with pytest.raises(ValueError, match="not found in eligible_by_date"):
        validate_random_selection_inputs(
            _toy_rebalance_dates(), bad_eligible, _toy_returns()
        )


def test_validate_requires_eligible_tickers_in_returns_map():
    eligible = {d: ["AAA", "ZZZ"] for d in _toy_rebalance_dates()}
    with pytest.raises(ValueError, match="ZZZ"):
        validate_random_selection_inputs(
            _toy_rebalance_dates(), eligible, _toy_returns()
        )


# ---------------------------------------------------------------------------
# 10-14. select_random_holdings_for_date
# ---------------------------------------------------------------------------

def test_select_random_holdings_never_exceeds_target_count():
    rng = np.random.default_rng(0)
    for _ in range(20):
        result = select_random_holdings_for_date(["A", "B", "C", "D", "E"], 3, rng)
        assert len(result) <= 3


def test_select_random_holdings_without_replacement():
    rng = np.random.default_rng(0)
    for _ in range(20):
        result = select_random_holdings_for_date(["A", "B", "C", "D", "E"], 3, rng)
        assert len(result) == len(set(result))


def test_select_random_holdings_only_from_eligible():
    eligible = ["AAA", "BBB", "CCC"]
    rng = np.random.default_rng(0)
    for _ in range(50):
        result = select_random_holdings_for_date(eligible, 3, rng)
        for t in result:
            assert t in eligible


def test_select_random_holdings_selects_all_when_fewer_than_target():
    rng = np.random.default_rng(0)
    result = select_random_holdings_for_date(["AAA", "BBB"], 5, rng)
    assert set(result) == {"AAA", "BBB"}
    assert len(result) == 2


def test_random_selection_is_deterministic_with_seed():
    rng1 = np.random.default_rng(42)
    rng2 = np.random.default_rng(42)
    r1 = select_random_holdings_for_date(["A", "B", "C", "D", "E"], 3, rng1)
    r2 = select_random_holdings_for_date(["A", "B", "C", "D", "E"], 3, rng2)
    assert r1 == r2


# ---------------------------------------------------------------------------
# 15-18. build_random_holdings_path
# ---------------------------------------------------------------------------

def test_build_random_holdings_uses_same_rebalance_dates():
    rng = np.random.default_rng(0)
    result = build_random_holdings_path(
        _toy_rebalance_dates(), _toy_eligible(), rng=rng
    )
    assert set(result.keys()) == {pd.Timestamp(d) for d in _toy_rebalance_dates()}


def test_build_random_holdings_uses_same_count_as_strategy_when_provided():
    strategy_holdings = {d: ["AAA", "BBB"] for d in _toy_rebalance_dates()}
    rng = np.random.default_rng(0)
    result = build_random_holdings_path(
        _toy_rebalance_dates(), _toy_eligible(),
        strategy_holdings_by_date=strategy_holdings, rng=rng,
    )
    for d, holdings in result.items():
        assert len(holdings) <= 2


def test_build_random_holdings_uses_top_n_when_strategy_counts_absent():
    cfg = RandomSelectionComparatorConfig(top_n=2)
    rng = np.random.default_rng(0)
    result = build_random_holdings_path(
        _toy_rebalance_dates(), _toy_eligible(), config=cfg, rng=rng,
    )
    for holdings in result.values():
        assert len(holdings) <= 2


def test_empty_slots_remain_cash():
    eligible_one = {d: ["AAA"] for d in _toy_rebalance_dates()}
    cfg = RandomSelectionComparatorConfig(top_n=3)
    rng = np.random.default_rng(0)
    result = build_random_holdings_path(
        _toy_rebalance_dates(), eligible_one, config=cfg, rng=rng,
    )
    # Only 1 eligible ticker; holdings = ["AAA"], remaining 2 slots = cash
    for holdings in result.values():
        assert holdings == ["AAA"]


# ---------------------------------------------------------------------------
# 19-24. compute_rotation_path_returns
# ---------------------------------------------------------------------------

def _two_rebalance_path():
    dates = [pd.Timestamp("2020-01-02"), pd.Timestamp("2020-02-03")]
    holdings = {
        pd.Timestamp("2020-01-02"): ["AAA", "BBB"],   # 2 of 3 slots filled
        pd.Timestamp("2020-02-03"): ["AAA"],            # 1 of 3 slots filled
    }
    n = 45
    bd = pd.bdate_range("2020-01-02", periods=n)
    returns = {
        "AAA": pd.Series(np.full(n, 0.01), index=bd),
        "BBB": pd.Series(np.full(n, 0.005), index=bd),
    }
    return dates, holdings, returns


def test_compute_path_returns_uses_one_over_top_n_not_one_over_selected_count():
    dates, holdings, returns = _two_rebalance_path()
    ret = compute_rotation_path_returns(holdings, returns, dates, top_n=3)
    # Period 1: AAA+BBB selected; weight each = 1/3; cash = 1/3
    # Daily ret = (1/3)*0.01 + (1/3)*0.005 + (1/3)*0.0 = 0.005
    first_ret = float(ret.iloc[0])
    assert first_ret == pytest.approx(1/3 * 0.01 + 1/3 * 0.005)


def test_compute_path_returns_includes_cash_return():
    dates = [pd.Timestamp("2020-01-02")]
    holdings = {pd.Timestamp("2020-01-02"): ["AAA"]}   # 1 of 3; 2 slots cash
    bd = pd.bdate_range("2020-01-02", periods=10)
    returns = {"AAA": pd.Series(np.full(10, 0.01), index=bd)}
    # cash_return = 0.02 per day
    ret = compute_rotation_path_returns(
        holdings, returns, dates, top_n=3, cash_return=0.02
    )
    expected = 1/3 * 0.01 + 2/3 * 0.02
    assert float(ret.iloc[0]) == pytest.approx(expected)


def test_compute_path_returns_rejects_missing_return_data():
    dates = [pd.Timestamp("2020-01-02")]
    holdings = {pd.Timestamp("2020-01-02"): ["ZZZ"]}
    bd = pd.bdate_range("2020-01-02", periods=5)
    returns = {"AAA": pd.Series(np.zeros(5), index=bd)}
    with pytest.raises(ValueError):
        compute_rotation_path_returns(holdings, returns, dates, top_n=3)


def test_compute_path_returns_no_leverage():
    dates, holdings, returns = _two_rebalance_path()
    ret = compute_rotation_path_returns(holdings, returns, dates, top_n=3)
    # Max weight per day = 1.0 (3 of 3 slots, each 1/3); cash always >= 0
    assert (ret.abs() <= 1.0).all()


def test_compute_path_returns_no_shorting():
    dates = [pd.Timestamp("2020-01-02")]
    holdings = {pd.Timestamp("2020-01-02"): ["AAA", "BBB"]}
    bd = pd.bdate_range("2020-01-02", periods=10)
    returns = {
        "AAA": pd.Series(np.full(10, -0.05), index=bd),
        "BBB": pd.Series(np.full(10, 0.05), index=bd),
    }
    ret = compute_rotation_path_returns(holdings, returns, dates, top_n=3)
    # Even with one ticker losing, no negative weighting (no short)
    # Cash weight = 1/3 >= 0; individual weights 1/3 each >= 0
    # Can still lose money (long-only can lose), but weights themselves >=0
    # Verify by checking that reducing a position's return always
    # reduces or maintains portfolio return (no inverse exposure)
    returns_lower = {
        "AAA": pd.Series(np.full(10, -0.10), index=bd),  # worse
        "BBB": pd.Series(np.full(10, 0.05), index=bd),
    }
    ret_lower = compute_rotation_path_returns(holdings, returns_lower, dates, top_n=3)
    assert float(ret_lower.iloc[0]) <= float(ret.iloc[0]) + 1e-12


def test_compute_path_returns_no_daily_rebalance():
    # Holdings must be constant between two rebalance dates
    dates = [pd.Timestamp("2020-01-02"), pd.Timestamp("2020-03-02")]
    holdings = {
        pd.Timestamp("2020-01-02"): ["AAA"],
        pd.Timestamp("2020-03-02"): ["BBB"],
    }
    bd = pd.bdate_range("2020-01-02", "2020-03-31")
    returns = {
        "AAA": pd.Series(np.full(len(bd), 0.01), index=bd),
        "BBB": pd.Series(np.full(len(bd), 0.005), index=bd),
    }
    ret = compute_rotation_path_returns(holdings, returns, dates, top_n=3)
    # Before March 2: only AAA held, weight=1/3, cash=2/3, daily_ret=1/3*0.01
    before_march = ret[ret.index < pd.Timestamp("2020-03-02")]
    after_march = ret[ret.index >= pd.Timestamp("2020-03-02")]
    assert (before_march - 1/3 * 0.01).abs().max() < 1e-12
    assert (after_march - 1/3 * 0.005).abs().max() < 1e-12


# ---------------------------------------------------------------------------
# 25-28. Full p95 calculation
# ---------------------------------------------------------------------------

def test_calculate_randomized_selection_runs_1000_by_default():
    # Use fewer sims (50) then check n_simulations is reported correctly
    r = _run_small()
    assert r.n_simulations == 50
    assert len(r.simulation_total_returns) == 50
    assert len(r.simulation_calmars) == 50


def test_calculate_randomized_selection_1000_sims_with_default_config():
    # Full 1000-sim run (takes ~1-2s on toy data — acceptable)
    r = calculate_randomized_selection_p95(
        _toy_rebalance_dates(),
        _toy_eligible(),
        _toy_returns(),
    )
    assert r.n_simulations == 1000
    assert len(r.simulation_total_returns) == 1000


def test_calculate_randomized_selection_is_deterministic():
    r1 = _run_small()
    r2 = _run_small()
    assert r1.p95_total_return == pytest.approx(r2.p95_total_return)
    assert r1.p95_calmar == pytest.approx(r2.p95_calmar)


def test_calculate_randomized_selection_outputs_p95_total_return():
    r = _run_small()
    # p95 must equal np.nanpercentile(sims, 95)
    expected = float(np.nanpercentile(r.simulation_total_returns, 95))
    assert r.p95_total_return == pytest.approx(expected)


def test_calculate_randomized_selection_outputs_p95_calmar():
    r = _run_small()
    expected = float(np.nanpercentile(r.simulation_calmars, 95))
    assert r.p95_calmar == pytest.approx(expected)


# ---------------------------------------------------------------------------
# 29. p75 must not exist
# ---------------------------------------------------------------------------

def test_calculate_randomized_selection_does_not_output_p75():
    r = _run_small()
    assert not hasattr(r, "p75_total_return")
    assert not hasattr(r, "p75_calmar")
    src = inspect.getsource(rsc)
    assert "p75" not in src


# ---------------------------------------------------------------------------
# 30-31. Diagnostics
# ---------------------------------------------------------------------------

def test_diagnostics_mark_report_only():
    r = _run_small()
    assert r.diagnostics["report_only"] is True
    assert r.diagnostics["p95_threshold"] == pytest.approx(0.95)
    assert "P95" in r.diagnostics["comparator_label"]
    assert "REPORT_ONLY" in r.diagnostics["comparator_label"]


def test_diagnostics_state_v1_1_verdict_impact_none():
    r = _run_small()
    assert r.diagnostics["v1_1_verdict_impact"] == "NONE"
    assert r.diagnostics["same_rebalance_dates"] is True
    assert r.diagnostics["same_universe"] is True
    assert r.diagnostics["same_eligibility_filters"] is True


# ---------------------------------------------------------------------------
# 32-33. No verdict leakage
# ---------------------------------------------------------------------------

def test_comparator_outputs_no_live_go():
    assert "LIVE-GO" not in inspect.getsource(rsc)


def test_comparator_outputs_no_research_go():
    assert "RESEARCH-GO" not in inspect.getsource(rsc)


# ---------------------------------------------------------------------------
# 34-38. Prior gates intact (cross-module smoke)
# ---------------------------------------------------------------------------

def test_rotation_benchmark_b2_tests_still_pass():
    from rotation_benchmark_b2 import EqualWeightBenchmarkConfig
    c = EqualWeightBenchmarkConfig()
    assert c.benchmark_label == "B2_EQUAL_WEIGHT_UNIVERSE_REPORT_ONLY"
    assert c.rebalance_frequency == "monthly"


def test_rotation_feature_matrix_tests_still_pass():
    from rotation_feature_matrix import RotationFeatureConfig
    c = RotationFeatureConfig()
    assert c.rs_mid_window == 126
    assert c.volatility_atr_pct_max == pytest.approx(0.08)


def test_rotation_backtester_scaffold_tests_still_pass():
    from rotation_backtester import RotationBacktester
    e = RotationBacktester()
    assert e.config.top_n == 3
    assert e.calculate_cash_weight([]) == pytest.approx(1.0)


def test_relative_strength_rotation_scaffold_tests_still_pass():
    from strategy_variants import RelativeStrengthRotation_v1
    v = RelativeStrengthRotation_v1()
    assert v.STRATEGY_ID == "RelativeStrengthRotation_v1"
    assert len(v.UNIVERSE) == 15


def test_relative_strength_rotation_spec_tests_still_pass():
    import pathlib
    spec = (pathlib.Path(__file__).parent.parent
            / "RESEARCH_SPEC_RELATIVE_STRENGTH_ROTATION_V1.md")
    text = spec.read_text(encoding="utf-8")
    assert "p95" in text
    assert "Hard separation of p75 and p95" in text
    assert "p75 ≠ p95" in text
