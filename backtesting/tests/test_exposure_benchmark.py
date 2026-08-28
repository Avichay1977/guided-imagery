"""
Tests for ExposureMatchedBenchmarkEngine and multi_ticker_runner integration.

All computation tests use synthetic price series.
Integration test (test 7) uses pre-downloaded AAPL data.
"""

import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from exposure_benchmark import ExposureMatchedBenchmarkEngine, compute_exposure_pct


DATA_DIR = Path(__file__).parent.parent / "data"
AAPL_CSV = DATA_DIR / "AAPL_2020-01-01_2024-12-31.csv"

INITIAL_CASH = 10_000.0


def _close(values: list[float]) -> pd.Series:
    dates = pd.bdate_range("2020-01-02", periods=len(values), freq="B")
    return pd.Series(values, index=dates)


# ---------------------------------------------------------------------------
# 1. Exposure fraction is stored correctly
# ---------------------------------------------------------------------------

def test_exposure_fraction_calculation():
    engine = ExposureMatchedBenchmarkEngine()
    close = _close([100, 101, 102, 103, 104])
    result = engine.calculate([], close, INITIAL_CASH, 25.0)
    assert result["exposure_fraction"] == 0.25


# ---------------------------------------------------------------------------
# 2. Zero exposure → flat equity = initial_cash throughout
# ---------------------------------------------------------------------------

def test_zero_exposure_returns_flat_equity():
    engine = ExposureMatchedBenchmarkEngine()
    close = _close([100, 110, 90, 120, 80])
    result = engine.calculate([], close, INITIAL_CASH, 0.0)
    eq = result["exposure_matched_equity_curve"]
    assert all(abs(v - INITIAL_CASH) < 1e-6 for v in eq), (
        f"Expected flat equity at {INITIAL_CASH}, got {eq}"
    )


# ---------------------------------------------------------------------------
# 3. Full exposure (100%) total return matches buy-and-hold
# ---------------------------------------------------------------------------

def test_full_exposure_matches_buy_and_hold_returns():
    engine = ExposureMatchedBenchmarkEngine()
    prices = [100, 105, 102, 110, 115]
    close = _close(prices)
    result = engine.calculate([], close, INITIAL_CASH, 100.0)

    bh_return = (prices[-1] / prices[0] - 1) * 100
    em_return = result["exposure_matched_total_return_pct"]
    assert abs(em_return - bh_return) < 0.01, (
        f"EM return {em_return} should match B&H return {bh_return}"
    )


# ---------------------------------------------------------------------------
# 4. Half exposure → each daily return is half of 100% daily return
# ---------------------------------------------------------------------------

def test_half_exposure_has_half_daily_returns():
    engine = ExposureMatchedBenchmarkEngine()
    prices = [100, 102, 99, 105, 108]
    close = _close(prices)

    r100 = engine.calculate([], close, INITIAL_CASH, 100.0)
    r50 = engine.calculate([], close, INITIAL_CASH, 50.0)

    eq100 = pd.Series(r100["exposure_matched_equity_curve"])
    eq50 = pd.Series(r50["exposure_matched_equity_curve"])

    rets100 = eq100.pct_change().dropna().values
    rets50 = eq50.pct_change().dropna().values

    assert len(rets100) == len(rets50)
    for r50_val, r100_val in zip(rets50, rets100):
        assert abs(r50_val - 0.5 * r100_val) < 1e-10, (
            f"50% daily return {r50_val} ≠ 0.5 × {r100_val}"
        )


# ---------------------------------------------------------------------------
# 5. Output dict contains all required keys
# ---------------------------------------------------------------------------

def test_exposure_matched_metrics_include_required_keys():
    engine = ExposureMatchedBenchmarkEngine()
    close = _close([100, 105, 103, 108])
    result = engine.calculate([], close, INITIAL_CASH, 30.0)

    required = {
        "exposure_fraction",
        "exposure_matched_total_return_pct",
        "exposure_matched_cagr_pct",
        "exposure_matched_max_drawdown_pct",
        "exposure_matched_sharpe",
        "exposure_matched_calmar",
        "exposure_matched_equity_curve",
        "exposure_matched_drawdown_curve",
    }
    missing = required - set(result.keys())
    assert not missing, f"Missing keys: {missing}"


# ---------------------------------------------------------------------------
# 6. Calmar = CAGR / max_drawdown (fractions)
# ---------------------------------------------------------------------------

def test_exposure_matched_calmar_calculation():
    engine = ExposureMatchedBenchmarkEngine()
    # Drawdown then recovery: peak=105, trough=95 → ~9.5% drawdown
    close = _close([100, 105, 95, 100, 110])
    result = engine.calculate([], close, INITIAL_CASH, 100.0)

    cagr_frac = result["exposure_matched_cagr_pct"] / 100.0
    mdd_frac = result["exposure_matched_max_drawdown_pct"] / 100.0

    if mdd_frac > 0:
        expected_calmar = cagr_frac / mdd_frac
        # Use relative tolerance: rounding of cagr_pct and mdd_pct to 2dp
        # causes small absolute error that scales with calmar magnitude
        rel_err = abs(result["exposure_matched_calmar"] - expected_calmar) / max(abs(expected_calmar), 1e-9)
        assert rel_err < 0.001, (
            f"calmar {result['exposure_matched_calmar']} differs from expected "
            f"{expected_calmar} by {rel_err*100:.4f}%"
        )
    else:
        assert result["exposure_matched_calmar"] in (0.0, float("inf"))


# ---------------------------------------------------------------------------
# 7. multi_ticker_runner TickerResult includes exposure-matched fields
# ---------------------------------------------------------------------------

def test_multi_ticker_runner_includes_exposure_matched_fields(tmp_path):
    if not AAPL_CSV.exists():
        pytest.skip("AAPL_2020-01-01_2024-12-31.csv not found in data/; run fetch first")

    from multi_ticker_runner import MultiTickerRunner

    def mock_fetch(ticker: str, start: str, end: str, output: str) -> None:
        src = DATA_DIR / f"{ticker}_{start}_{end}.csv"
        shutil.copy(src, output)

    runner = MultiTickerRunner(fetch_fn=mock_fetch)
    result = runner.run_ticker("AAPL", "2020-01-01", "2024-12-31", True, tmp_path)

    assert hasattr(result, "exposure_time_pct"), "missing exposure_time_pct"
    assert hasattr(result, "exposure_matched_cagr_pct"), "missing exposure_matched_cagr_pct"
    assert hasattr(result, "exposure_matched_max_drawdown_pct"), "missing exposure_matched_max_drawdown_pct"
    assert hasattr(result, "exposure_matched_calmar"), "missing exposure_matched_calmar"
    assert hasattr(result, "strategy_vs_exposure_matched_calmar_delta"), "missing delta"
    assert result.exposure_time_pct >= 0.0
    assert result.exposure_matched_calmar >= 0.0
