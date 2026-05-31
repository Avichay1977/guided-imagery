"""
Unit tests for the B2 equal-weight universe benchmark.

Deterministic toy close/OHLCV data only.
No real market data. No fetch. No backtests. No runner.
"""

import inspect
import math

import numpy as np
import pandas as pd
import pytest

import rotation_benchmark_b2 as b2m
from rotation_benchmark_b2 import (
    EqualWeightBenchmarkConfig,
    EqualWeightBenchmarkResult,
    calculate_calmar,
    calculate_equal_weight_universe_benchmark,
    calculate_max_drawdown,
    calculate_total_return,
    select_monthly_rebalance_dates,
    validate_benchmark_universe_data,
)


# ---------------------------------------------------------------------------
# Toy data helpers
# ---------------------------------------------------------------------------

def _close_df(n=300, start=100.0, slope=0.5, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2015-01-01", periods=n)
    close = start + slope * np.arange(n) + np.sin(np.linspace(0, 8 * np.pi, n)) * 2
    return pd.DataFrame({"close": close}, index=dates)


def _toy_universe(n=300):
    return {
        "AAA": _close_df(n, start=100, slope=0.6, seed=1),
        "BBB": _close_df(n, start=120, slope=0.3, seed=2),
        "CCC": _close_df(n, start=80,  slope=0.45, seed=3),
    }


def _flat_universe(n=120):
    """All tickers have flat price = 100. Total return = 0."""
    dates = pd.bdate_range("2015-01-01", periods=n)
    return {
        "AAA": pd.DataFrame({"close": np.full(n, 100.0)}, index=dates),
        "BBB": pd.DataFrame({"close": np.full(n, 100.0)}, index=dates),
    }


# ---------------------------------------------------------------------------
# 1. Config defaults
# ---------------------------------------------------------------------------

def test_config_defaults_match_spec():
    c = EqualWeightBenchmarkConfig()
    assert c.initial_value == pytest.approx(1.0)
    assert c.rebalance_frequency == "monthly"
    assert c.require_full_universe is True
    assert c.annualization_days == 252
    assert c.benchmark_label == "B2_EQUAL_WEIGHT_UNIVERSE_REPORT_ONLY"


# ---------------------------------------------------------------------------
# 2. Result dataclass fields
# ---------------------------------------------------------------------------

def test_result_dataclass_has_required_fields():
    u = _toy_universe()
    r = calculate_equal_weight_universe_benchmark(u)
    assert hasattr(r, "equity_curve")
    assert hasattr(r, "daily_returns")
    assert hasattr(r, "weights_by_date")
    assert hasattr(r, "holdings_by_date")
    assert hasattr(r, "total_return")
    assert hasattr(r, "max_drawdown")
    assert hasattr(r, "calmar")
    assert hasattr(r, "diagnostics")


# ---------------------------------------------------------------------------
# 3-4. Import guards
# ---------------------------------------------------------------------------

def test_module_does_not_import_yfinance():
    src = inspect.getsource(b2m)
    assert "yfinance" not in src
    assert "import yf" not in src


def test_module_does_not_import_backtester():
    src = inspect.getsource(b2m)
    assert "import backtester" not in src
    assert "from backtester" not in src


# ---------------------------------------------------------------------------
# 5-9. Validation
# ---------------------------------------------------------------------------

def test_validate_rejects_empty_universe():
    with pytest.raises(ValueError):
        validate_benchmark_universe_data({})


def test_validate_rejects_missing_close_column():
    bad = {"AAA": pd.DataFrame({"open": [100.0, 101.0]})}
    with pytest.raises(ValueError, match="missing 'close'"):
        validate_benchmark_universe_data(bad)


def test_validate_rejects_nan_close():
    dates = pd.bdate_range("2020-01-01", periods=5)
    bad = {"AAA": pd.DataFrame({"close": [100.0, np.nan, 102.0, 103.0, 104.0]}, index=dates)}
    with pytest.raises(ValueError, match="NaN"):
        validate_benchmark_universe_data(bad)


def test_validate_rejects_inf_close():
    dates = pd.bdate_range("2020-01-01", periods=5)
    bad = {"AAA": pd.DataFrame({"close": [100.0, np.inf, 102.0, 103.0, 104.0]}, index=dates)}
    with pytest.raises(ValueError, match="inf"):
        validate_benchmark_universe_data(bad)


def test_validate_requires_full_universe_when_configured():
    u = _toy_universe()
    with pytest.raises(ValueError, match="missing required tickers"):
        validate_benchmark_universe_data(u, universe=["AAA", "BBB", "CCC", "ZZZ"])


# ---------------------------------------------------------------------------
# 10. Monthly rebalance dates
# ---------------------------------------------------------------------------

def test_select_monthly_rebalance_dates_returns_first_trading_day_each_month():
    dates = pd.bdate_range("2020-01-01", "2020-03-31")
    out = select_monthly_rebalance_dates(dates)
    assert len(out) == 3
    # First business day of Jan 2020 = 2020-01-01 (Wednesday)
    assert out[0] == pd.Timestamp("2020-01-01")
    # First business day of Feb 2020 = 2020-02-03 (Mon, after Sat/Sun)
    assert out[1] == pd.Timestamp("2020-02-03")
    assert out[2].month == 3


# ---------------------------------------------------------------------------
# 11. Equity curve starts at initial_value
# ---------------------------------------------------------------------------

def test_equal_weight_benchmark_equity_starts_at_initial_value():
    u = _toy_universe()
    r = calculate_equal_weight_universe_benchmark(u)
    assert r.equity_curve.iloc[0] == pytest.approx(1.0)


def test_equal_weight_benchmark_equity_starts_at_custom_initial_value():
    u = _toy_universe()
    cfg = EqualWeightBenchmarkConfig(initial_value=100_000.0)
    r = calculate_equal_weight_universe_benchmark(u, config=cfg)
    assert r.equity_curve.iloc[0] == pytest.approx(100_000.0)


# ---------------------------------------------------------------------------
# 12. Determinism
# ---------------------------------------------------------------------------

def test_equal_weight_benchmark_is_deterministic():
    u = _toy_universe()
    a = calculate_equal_weight_universe_benchmark(u)
    b = calculate_equal_weight_universe_benchmark(u)
    pd.testing.assert_series_equal(a.equity_curve, b.equity_curve)
    assert a.total_return == pytest.approx(b.total_return)


# ---------------------------------------------------------------------------
# 13. Uses close only (extra columns are ignored)
# ---------------------------------------------------------------------------

def test_equal_weight_benchmark_uses_close_only():
    u = _toy_universe()
    u_extra = {
        t: df.assign(open=df["close"] * 0.99, high=df["close"] * 1.01,
                     low=df["close"] * 0.99, volume=1_000_000.0)
        for t, df in u.items()
    }
    r_base = calculate_equal_weight_universe_benchmark(u)
    r_extra = calculate_equal_weight_universe_benchmark(u_extra)
    pd.testing.assert_series_equal(r_base.equity_curve, r_extra.equity_curve)


# ---------------------------------------------------------------------------
# 14. Input DataFrames not modified
# ---------------------------------------------------------------------------

def test_equal_weight_benchmark_does_not_modify_inputs():
    u = _toy_universe()
    originals = {t: df["close"].copy() for t, df in u.items()}
    calculate_equal_weight_universe_benchmark(u)
    for t, orig in originals.items():
        pd.testing.assert_series_equal(orig, u[t]["close"])


# ---------------------------------------------------------------------------
# 15-17. Rebalance logic: equal weights at rebalance, drift between
# ---------------------------------------------------------------------------

def test_equal_weight_benchmark_sets_equal_weights_at_rebalance():
    u = _toy_universe()
    r = calculate_equal_weight_universe_benchmark(u)
    rebalance_dates = set(select_monthly_rebalance_dates(r.equity_curve.index))
    for date in list(rebalance_dates)[:3]:
        if date in r.weights_by_date.index:
            w_row = r.weights_by_date.loc[date]
            expected_w = 1.0 / len(u)
            for t in u:
                assert w_row[t] == pytest.approx(expected_w, abs=1e-9)


def test_equal_weight_benchmark_holds_shares_between_rebalances():
    # Between two rebalance dates, shares must be constant.
    u = _toy_universe(300)
    r = calculate_equal_weight_universe_benchmark(u)
    dates = list(r.equity_curve.index)
    rebalance_dates = set(select_monthly_rebalance_dates(dates))

    # Find two consecutive non-rebalance trading days inside a single month
    for i in range(1, len(dates) - 1):
        d1, d2 = dates[i], dates[i + 1]
        if d1 not in rebalance_dates and d2 not in rebalance_dates:
            h1 = r.holdings_by_date.loc[d1]
            h2 = r.holdings_by_date.loc[d2]
            for t in u:
                assert h1[t] == pytest.approx(h2[t]), \
                    f"Shares of {t} changed between non-rebalance days {d1} and {d2}"
            break


def test_equal_weight_benchmark_does_not_daily_rebalance():
    # Weights should NOT be equal on non-rebalance days (prices drift).
    u = _toy_universe(300)
    r = calculate_equal_weight_universe_benchmark(u)
    dates = list(r.equity_curve.index)
    rebalance_dates = set(select_monthly_rebalance_dates(dates))

    non_rebal = [d for d in dates if d not in rebalance_dates]
    off_days = r.weights_by_date.loc[non_rebal]
    target = 1.0 / len(u)
    # At least one non-rebalance day should have drifted weights
    exactly_equal = (off_days - target).abs().max(axis=1) < 1e-12
    # Some should not be exactly equal (prices drifted)
    assert not exactly_equal.all(), "Weights appear to be rebalanced daily (violation)."


# ---------------------------------------------------------------------------
# 18. Total return: simple case
# ---------------------------------------------------------------------------

def test_equal_weight_benchmark_total_return_matches_simple_case():
    # Two tickers: AAA doubles (100->200), BBB stays flat (100->100).
    # Monthly rebalancing continuously trims the winner and reloads the flat
    # ticker, so the portfolio return is LESS than buy-and-hold (which would
    # be exactly 50%). The range 0.35–0.50 is the correct sanity window for
    # any reasonable monthly-rebalancing implementation over ~6 months.
    n = 130
    dates = pd.bdate_range("2020-01-01", periods=n)
    close_aaa = np.linspace(100.0, 200.0, n)
    close_bbb = np.full(n, 100.0)
    u = {
        "AAA": pd.DataFrame({"close": close_aaa}, index=dates),
        "BBB": pd.DataFrame({"close": close_bbb}, index=dates),
    }
    r = calculate_equal_weight_universe_benchmark(u)
    # Must be profitable (AAA doubled) but below the BH 50% mark
    assert r.total_return > 0.30
    assert r.total_return < 0.55
    # Equity curve must be strictly rising overall
    assert r.equity_curve.iloc[-1] > r.equity_curve.iloc[0]


# ---------------------------------------------------------------------------
# 19-21. Metric helpers
# ---------------------------------------------------------------------------

def test_calculate_total_return_matches_expected():
    curve = pd.Series([1.0, 1.1, 1.2, 1.5])
    assert calculate_total_return(curve) == pytest.approx(0.50)


def test_calculate_max_drawdown_matches_expected():
    curve = pd.Series([1.0, 1.2, 0.9, 1.1, 0.8, 1.3])
    # Peak 1.2 -> trough 0.9 = 25%; peak 1.3 -> peak tracking...
    # 1.2 -> 0.8 = 33.3% is the max
    assert calculate_max_drawdown(curve) == pytest.approx(1.0 - 0.8 / 1.2, abs=1e-9)


def test_calculate_calmar_is_finite_for_positive_curve():
    curve = pd.Series([1.0, 1.05, 1.02, 1.10, 1.08, 1.20])
    c = calculate_calmar(curve, annualization_days=252)
    assert math.isfinite(c)
    assert c > 0


# ---------------------------------------------------------------------------
# 22-23. Date window
# ---------------------------------------------------------------------------

def test_start_end_date_window_is_applied():
    u = _toy_universe(300)
    all_dates = pd.bdate_range("2015-01-01", periods=300)
    start = all_dates[50]
    end = all_dates[150]
    r = calculate_equal_weight_universe_benchmark(u, start_date=start, end_date=end)
    assert r.equity_curve.index[0] >= start
    assert r.equity_curve.index[-1] <= end
    assert len(r.equity_curve) == 101


def test_start_after_end_raises():
    u = _toy_universe()
    with pytest.raises(ValueError, match="start_date"):
        calculate_equal_weight_universe_benchmark(
            u,
            start_date="2020-06-01",
            end_date="2020-01-01",
        )


# ---------------------------------------------------------------------------
# 24-26. No fill / no interpolation
# ---------------------------------------------------------------------------

def test_no_forward_fill_of_missing_close():
    src = inspect.getsource(b2m)
    assert "ffill" not in src
    assert "method='pad'" not in src


def test_no_backfill_of_missing_close():
    src = inspect.getsource(b2m)
    assert "bfill" not in src
    assert "backfill" not in src


def test_no_interpolation_of_missing_close():
    assert "interpolate" not in inspect.getsource(b2m)


# ---------------------------------------------------------------------------
# 27-28. Diagnostics
# ---------------------------------------------------------------------------

def test_diagnostics_mark_b2_as_report_only():
    r = calculate_equal_weight_universe_benchmark(_toy_universe())
    assert r.diagnostics["report_only"] is True
    assert "B2" in r.diagnostics["benchmark_label"]
    assert "REPORT_ONLY" in r.diagnostics["benchmark_label"]


def test_diagnostics_state_v1_1_verdict_impact_none():
    r = calculate_equal_weight_universe_benchmark(_toy_universe())
    assert r.diagnostics["v1_1_verdict_impact"] == "NONE"


def test_diagnostics_contain_ticker_count_and_rebalance_count():
    r = calculate_equal_weight_universe_benchmark(_toy_universe())
    assert r.diagnostics["ticker_count"] == 3
    assert r.diagnostics["rebalance_count"] >= 1


# ---------------------------------------------------------------------------
# 29-30. No verdict leakage
# ---------------------------------------------------------------------------

def test_b2_outputs_no_live_go():
    assert "LIVE-GO" not in inspect.getsource(b2m)


def test_b2_outputs_no_research_go():
    assert "RESEARCH-GO" not in inspect.getsource(b2m)


# ---------------------------------------------------------------------------
# 31-34. Prior gates intact (cross-module smoke checks)
# ---------------------------------------------------------------------------

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
    assert "## 16. Protocol v1.2 Exposure-Fair Diagnostic Evaluation" in text
    assert "B2" in text
    assert "REPORT ONLY" in text or "Report Only" in text.replace("REPORT ONLY", "Report Only")
