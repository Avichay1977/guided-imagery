"""
Tests for RegimeAnalysisEngine and regime_runner.run_regime_analysis.

All tests use synthetic equity series or pre-downloaded CSV files.
No dummy OHLCV data is created.
"""

import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from regime_analysis import RegimeAnalysisEngine
from regime_runner import run_regime_analysis


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent / "data"
AAPL_CSV = DATA_DIR / "AAPL_2020-01-01_2024-12-31.csv"


def _series(year: int, values: list[float]) -> pd.Series:
    """Create a pd.Series with a DatetimeIndex for the given year."""
    dates = pd.bdate_range(f"{year}-01-01", periods=len(values), freq="B")
    return pd.Series(values, index=dates)


def _multi_year_series(year_values: dict[int, list[float]]) -> pd.Series:
    """Concatenate per-year value lists into a single date-indexed Series."""
    parts = [_series(yr, vals) for yr, vals in sorted(year_values.items())]
    combined = pd.concat(parts)
    return combined[~combined.index.duplicated(keep="first")]


def _make_trade(entry_ts, exit_ts, pnl: float) -> dict:
    return {
        "entry_time": pd.Timestamp(entry_ts),
        "exit_time": pd.Timestamp(exit_ts),
        "entry_price": 100.0,
        "exit_price": 100.0 + pnl,
        "stop_price": 95.0,
        "take_profit_price": 115.0,
        "shares": 1.0,
        "pnl": pnl,
        "exit_reason": "take_profit" if pnl > 0 else "stop_loss",
        "confluence_score": 5,
    }


# ---------------------------------------------------------------------------
# 1. Groups by year
# ---------------------------------------------------------------------------

def test_regime_analysis_groups_by_year():
    engine = RegimeAnalysisEngine()
    strat = _multi_year_series({
        2020: [100.0] * 200,
        2021: [100.0] * 250,
        2022: [100.0] * 250,
    })
    bench = strat.copy()

    result = engine.analyze_by_year(strat, bench, trades=[])

    assert set(result["years"].keys()) == {2020, 2021, 2022}


# ---------------------------------------------------------------------------
# 2. Yearly return calculation
# ---------------------------------------------------------------------------

def test_yearly_return_calculation():
    engine = RegimeAnalysisEngine()
    # 2020: equity grows from 100 to 120 → +20%
    values = np.linspace(100, 120, 100).tolist()
    strat = _series(2020, values)
    bench = _series(2020, [100.0] * 100)

    result = engine.analyze_by_year(strat, bench, trades=[])

    yr = result["years"][2020]
    assert abs(yr["strategy_return_pct"] - 20.0) < 0.1


# ---------------------------------------------------------------------------
# 3. Yearly max drawdown calculation
# ---------------------------------------------------------------------------

def test_yearly_max_drawdown_calculation():
    engine = RegimeAnalysisEngine()
    # Peak at 110, drops to 88 → drawdown = (110 - 88) / 110 ≈ 20%
    values = [100.0, 105.0, 110.0, 95.0, 88.0, 92.0, 100.0]
    strat = _series(2020, values)
    bench = _series(2020, [100.0] * len(values))

    result = engine.analyze_by_year(strat, bench, trades=[])

    yr = result["years"][2020]
    expected_mdd = (110.0 - 88.0) / 110.0 * 100  # ≈ 20%
    assert abs(yr["strategy_max_drawdown_pct"] - expected_mdd) < 0.5


# ---------------------------------------------------------------------------
# 4. Trade distribution by year
# ---------------------------------------------------------------------------

def test_trade_distribution_by_year():
    engine = RegimeAnalysisEngine()
    strat = _multi_year_series({
        2020: [100.0] * 200,
        2021: [100.0] * 250,
    })
    bench = strat.copy()

    trades = (
        [_make_trade("2020-02-01", "2020-02-05", 50.0)] * 5
        + [_make_trade("2021-03-01", "2021-03-05", -20.0)] * 3
    )

    result = engine.analyze_by_year(strat, bench, trades=trades)

    assert result["years"][2020]["trade_count"] == 5
    assert result["years"][2021]["trade_count"] == 3


# ---------------------------------------------------------------------------
# 5. Warns when no trades in a year
# ---------------------------------------------------------------------------

def test_warns_when_no_trades_in_year():
    engine = RegimeAnalysisEngine()
    strat = _series(2020, [100.0] * 100)
    bench = _series(2020, [100.0] * 100)

    result = engine.analyze_by_year(strat, bench, trades=[])

    warnings_2020 = result["years"][2020]["warnings"]
    assert any("NO_TRADES" in w and "2020" in w for w in warnings_2020)
    assert any("NO_TRADES" in w for w in result["all_warnings"])


# ---------------------------------------------------------------------------
# 6. Warns when underexposed in a bull year
# ---------------------------------------------------------------------------

def test_warns_underexposed_in_bull_year():
    engine = RegimeAnalysisEngine(underexposed_threshold_pct=20.0)
    # Benchmark returns +30% in 2020; strategy is flat (all cash)
    bench_vals = np.linspace(100, 130, 252).tolist()
    strat_vals = [100.0] * 252
    strat = _series(2020, strat_vals)
    bench = _series(2020, bench_vals)

    # Two trades that only cover Jan 2–3 (2 days exposure out of 252)
    trades = [_make_trade("2020-01-02", "2020-01-03", 10.0)]

    result = engine.analyze_by_year(strat, bench, trades=trades)

    warnings_2020 = result["years"][2020]["warnings"]
    assert any("UNDEREXPOSED_IN_BULL_YEAR" in w for w in warnings_2020), (
        f"Expected UNDEREXPOSED_IN_BULL_YEAR in {warnings_2020}"
    )
    assert result["years"][2020]["exposure_pct"] < 20.0


# ---------------------------------------------------------------------------
# 7. Warns when calmar below benchmark
# ---------------------------------------------------------------------------

def test_warns_when_calmar_below_benchmark():
    engine = RegimeAnalysisEngine()
    # Strategy: +20% but big drawdown (50%) → calmar ≈ 0.40
    s_vals = [100.0, 80.0, 50.0, 70.0, 120.0]
    # Benchmark: +30% with tiny drawdown → calmar >> 1
    b_vals = [100.0, 105.0, 110.0, 120.0, 130.0]

    strat = _series(2020, s_vals)
    bench = _series(2020, b_vals)

    result = engine.analyze_by_year(strat, bench, trades=[])

    yr = result["years"][2020]
    assert yr["strategy_calmar"] < yr["benchmark_calmar"]
    assert any("CALMAR_BELOW_BENCHMARK" in w for w in yr["warnings"])
    assert any("CALMAR_BELOW_BENCHMARK" in w for w in result["all_warnings"])


# ---------------------------------------------------------------------------
# 8. regime_runner outputs required columns
# ---------------------------------------------------------------------------

def test_regime_runner_outputs_required_columns(tmp_path):
    if not AAPL_CSV.exists():
        pytest.skip("AAPL_2020-01-01_2024-12-31.csv not found in data/; run fetch first")

    def mock_fetch(ticker: str, start: str, end: str, output: str) -> None:
        src = DATA_DIR / f"{ticker}_{start}_{end}.csv"
        shutil.copy(src, output)

    df = run_regime_analysis(
        tickers=["AAPL"],
        start="2020-01-01",
        end="2024-12-31",
        adjust=True,
        output=str(tmp_path / "regime_test.csv"),
        data_dir=tmp_path,
        fetch_fn=mock_fetch,
    )

    required = {
        "ticker", "year",
        "strategy_return_pct", "benchmark_return_pct",
        "strategy_max_drawdown_pct", "benchmark_max_drawdown_pct",
        "strategy_calmar", "benchmark_calmar",
        "trade_count", "win_rate_pct", "exposure_pct", "warnings",
    }
    assert required.issubset(set(df.columns)), (
        f"Missing columns: {required - set(df.columns)}"
    )
    assert len(df) > 0
    assert set(df["year"].unique()) == {2020, 2021, 2022, 2023, 2024}
    assert (df["ticker"] == "AAPL").all()
