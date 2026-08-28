"""
Unit tests for rotation_benchmark_b1.

Deterministic toy price series only. No real market data. No data fetch.
No strategy_lab_runner.
"""

import inspect

import numpy as np
import pandas as pd
import pytest

import rotation_benchmark_b1 as _b1mod
from rotation_benchmark_b1 import (
    B1BuyHoldBenchmarkConfig,
    B1BuyHoldBenchmarkResult,
    calculate_b1_buy_hold_benchmark,
    calculate_b1_for_universe,
    validate_b1_price_data,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FROZEN_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMD", "META",
    "AMZN", "GOOGL", "TSLA", "NFLX", "AVGO",
    "CRM", "ORCL", "INTC", "CSCO", "IBM",
]


def _toy_close(start="2020-01-02", n=10, start_price=100.0, daily_growth=0.01):
    dates = pd.bdate_range(start, periods=n)
    prices = start_price * (1.0 + daily_growth) ** np.arange(n)
    return pd.Series(prices, index=dates, name="close")


def _toy_df(start="2020-01-02", n=10, start_price=100.0, daily_growth=0.01):
    s = _toy_close(start, n, start_price, daily_growth)
    return pd.DataFrame({"close": s.values}, index=s.index)


def _toy_universe(start="2020-01-02", n=10):
    return {t: _toy_df(start=start, n=n) for t in _FROZEN_UNIVERSE}


# ---------------------------------------------------------------------------
# Tests 1–4: module + dataclass shape + forbidden imports
# ---------------------------------------------------------------------------

def test_config_defaults_match_spec():
    c = B1BuyHoldBenchmarkConfig()
    assert c.initial_value == pytest.approx(1.0)
    assert c.annualization_days == 252
    assert c.benchmark_label == "B1_RAW_BUY_HOLD_PRIMARY_V1_1"
    assert c.report_only is False


def test_result_dataclass_has_required_fields():
    r = calculate_b1_buy_hold_benchmark(_toy_close())
    for f in ("equity_curve", "daily_returns", "total_return",
              "max_drawdown", "calmar", "diagnostics"):
        assert hasattr(r, f), f"missing field: {f!r}"
    assert isinstance(r, B1BuyHoldBenchmarkResult)


def test_module_does_not_import_yfinance():
    src = inspect.getsource(_b1mod)
    assert "yfinance" not in src
    assert "import yfinance" not in src
    assert "from yfinance" not in src


def test_module_does_not_import_strategy_lab_runner():
    src = inspect.getsource(_b1mod)
    assert "strategy_lab_runner" not in src


# ---------------------------------------------------------------------------
# Tests 5–9: validation rejections
# ---------------------------------------------------------------------------

def test_validation_rejects_empty_input():
    with pytest.raises(ValueError):
        validate_b1_price_data(pd.Series([], dtype=float))
    with pytest.raises(ValueError):
        validate_b1_price_data(pd.DataFrame())
    with pytest.raises(ValueError):
        validate_b1_price_data(None)


def test_validation_rejects_missing_close():
    df = pd.DataFrame({"open": [100.0, 101.0]}, index=pd.bdate_range("2020-01-02", periods=2))
    with pytest.raises(ValueError, match="close"):
        validate_b1_price_data(df)


def test_validation_rejects_nan_close():
    s = _toy_close(n=5).copy()
    s.iloc[2] = float("nan")
    with pytest.raises(ValueError, match="NaN"):
        validate_b1_price_data(s)


def test_validation_rejects_inf_close():
    s = _toy_close(n=5).copy()
    s.iloc[1] = float("inf")
    with pytest.raises(ValueError, match="inf"):
        validate_b1_price_data(s)


def test_validation_rejects_non_positive_close():
    s = _toy_close(n=5).copy()
    s.iloc[3] = 0.0
    with pytest.raises(ValueError, match="non-positive"):
        validate_b1_price_data(s)
    s2 = _toy_close(n=5).copy()
    s2.iloc[3] = -10.0
    with pytest.raises(ValueError, match="non-positive"):
        validate_b1_price_data(s2)


# ---------------------------------------------------------------------------
# Tests 10–13: equity curve, total_return, no rebalance / no cash
# ---------------------------------------------------------------------------

def test_buy_hold_equity_starts_at_initial_value():
    r = calculate_b1_buy_hold_benchmark(_toy_close(), config=B1BuyHoldBenchmarkConfig(initial_value=1000.0))
    assert float(r.equity_curve.iloc[0]) == pytest.approx(1000.0)


def test_buy_hold_total_return_matches_simple_close_series():
    s = _toy_close(n=5, start_price=100.0, daily_growth=0.10)
    r = calculate_b1_buy_hold_benchmark(s)
    expected_total = float(s.iloc[-1] / s.iloc[0] - 1.0)
    assert r.total_return == pytest.approx(expected_total)


def test_no_rebalancing_in_b1():
    # Verify no cash/positions logic: equity curve is exactly (close/close[0]) * init
    s = _toy_close(n=8, start_price=50.0, daily_growth=0.02)
    init = 1000.0
    r = calculate_b1_buy_hold_benchmark(s, config=B1BuyHoldBenchmarkConfig(initial_value=init))
    expected = (s.values / s.values[0]) * init
    np.testing.assert_allclose(r.equity_curve.values, expected, rtol=1e-12)


def test_no_cash_sleeve_in_b1():
    # Cash sleeve would imply equity_curve grows by some cash_return when prices stagnate.
    # Make a flat-price series; with no cash sleeve, equity must remain at initial_value.
    dates = pd.bdate_range("2020-01-02", periods=6)
    flat = pd.Series([100.0] * 6, index=dates)
    r = calculate_b1_buy_hold_benchmark(flat, config=B1BuyHoldBenchmarkConfig(initial_value=1.0))
    assert all(float(v) == pytest.approx(1.0) for v in r.equity_curve)
    assert r.total_return == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests 14–18: window, no fill, no mutation
# ---------------------------------------------------------------------------

def test_start_end_window_applied():
    s = _toy_close(start="2020-01-02", n=20)
    r = calculate_b1_buy_hold_benchmark(
        s, start_date="2020-01-08", end_date="2020-01-14"
    )
    assert r.equity_curve.index[0] >= pd.Timestamp("2020-01-08")
    assert r.equity_curve.index[-1] <= pd.Timestamp("2020-01-14")


def test_start_after_end_raises():
    with pytest.raises(ValueError):
        calculate_b1_buy_hold_benchmark(
            _toy_close(n=20), start_date="2020-01-15", end_date="2020-01-05"
        )


def test_no_forward_fill():
    # If forward-fill were happening, an inserted NaN would be silently filled
    # and the call would succeed. Validation must reject NaN instead.
    s = _toy_close(n=6).copy()
    s.iloc[3] = float("nan")
    with pytest.raises(ValueError):
        calculate_b1_buy_hold_benchmark(s)


def test_no_backfill():
    s = _toy_close(n=6).copy()
    s.iloc[0] = float("nan")
    with pytest.raises(ValueError):
        calculate_b1_buy_hold_benchmark(s)


def test_no_interpolation():
    # Multiple consecutive NaNs are surfaced as invalid, never interpolated.
    s = _toy_close(n=8).copy()
    s.iloc[2] = float("nan")
    s.iloc[3] = float("nan")
    with pytest.raises(ValueError):
        calculate_b1_buy_hold_benchmark(s)


def test_does_not_mutate_input():
    s = _toy_close(n=10)
    s_copy = s.copy()
    calculate_b1_buy_hold_benchmark(s)
    pd.testing.assert_series_equal(s, s_copy)


# ---------------------------------------------------------------------------
# Test 20: diagnostics mark B1 as primary v1.1 benchmark
# ---------------------------------------------------------------------------

def test_diagnostics_mark_b1_as_primary_v1_1_benchmark():
    r = calculate_b1_buy_hold_benchmark(_toy_close())
    d = r.diagnostics
    assert d["benchmark_label"] == "B1_RAW_BUY_HOLD_PRIMARY_V1_1"
    assert d["report_only"] is False
    assert d["v1_1_primary_benchmark"] is True
    assert d["v1_1_verdict_impact"] == "PRIMARY_BENCHMARK_INPUT"
    assert "start_date" in d
    assert "end_date" in d
    assert "data_points" in d
    assert d["data_points"] > 0


# ---------------------------------------------------------------------------
# Tests 21–23: universe-level B1
# ---------------------------------------------------------------------------

def test_calculate_b1_for_universe_requires_all_frozen_tickers():
    ud = _toy_universe()
    del ud["TSLA"]
    with pytest.raises(ValueError, match="missing tickers"):
        calculate_b1_for_universe(ud, _FROZEN_UNIVERSE)


def test_calculate_b1_for_universe_returns_one_result_per_ticker():
    ud = _toy_universe()
    results = calculate_b1_for_universe(ud, _FROZEN_UNIVERSE)
    assert isinstance(results, dict)
    assert set(results.keys()) == set(_FROZEN_UNIVERSE)
    assert len(results) == 15
    for t, r in results.items():
        assert isinstance(r, B1BuyHoldBenchmarkResult), f"{t!r} result wrong type"


def test_b1_does_not_call_b2():
    # rotation_benchmark_b1 module must not import or use the B2 equal-weight
    # logic. Source-level guarantee.
    src = inspect.getsource(_b1mod)
    assert "rotation_benchmark_b2" not in src
    assert "EqualWeightBenchmark" not in src
    assert "calculate_equal_weight" not in src


# ---------------------------------------------------------------------------
# Tests 24–25: no live-go, no research-go anywhere in B1 source
# ---------------------------------------------------------------------------

def test_b1_outputs_no_live_go():
    src = inspect.getsource(_b1mod)
    assert "LIVE-GO" not in src


def test_b1_outputs_no_research_go():
    src = inspect.getsource(_b1mod)
    assert "RESEARCH-GO" not in src
