"""
Tests for RandomizedTimingBenchmarkEngine and randomized_benchmark_runner.

Synthetic price series used for engine tests.
Real AAPL data used for integration test (test 9).
"""

import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from randomized_benchmark import (
    RandomizedBenchmarkConfig,
    RandomizedTimingBenchmarkEngine,
)
from randomized_benchmark_runner import run_randomized_benchmark


DATA_DIR = Path(__file__).parent.parent / "data"
AAPL_CSV = DATA_DIR / "AAPL_2020-01-01_2024-12-31.csv"

INITIAL_CASH = 100_000.0


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_df(n: int = 500, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n, freq="B")
    prices = 100.0 * np.cumprod(1 + rng.normal(0.0002, 0.012, n))
    return pd.DataFrame({"close": prices}, index=dates)


def _make_trades(df: pd.DataFrame, n: int = 8, seed: int = 7) -> list[dict]:
    rng = np.random.default_rng(seed)
    N = len(df)
    trades = []
    ptr = 10
    for _ in range(n):
        if ptr >= N - 20:
            break
        entry_i = ptr
        hp = int(rng.integers(5, 20))
        exit_i = min(entry_i + hp, N - 1)
        ep = float(df["close"].iloc[entry_i])
        xp = float(df["close"].iloc[exit_i])
        trades.append({
            "entry_time": df.index[entry_i],
            "exit_time": df.index[exit_i],
            "entry_price": ep,
            "exit_price": xp,
            "stop_price": ep * 0.95,
            "take_profit_price": ep * 1.15,
            "shares": 100.0,
            "pnl": (xp - ep) * 100.0,
            "exit_reason": "take_profit" if xp > ep else "stop_loss",
            "confluence_score": 5,
        })
        ptr = exit_i + 5

    return trades


def _strategy_metrics(total_return: float = 15.0, calmar: float = 0.5) -> dict:
    return {
        "total_return_pct": total_return,
        "calmar_ratio": calmar,
        "max_drawdown_pct": 10.0,
        "cagr_pct": 3.0,
        "sharpe_ratio": 0.8,
        "profit_factor": 1.5,
        "expectancy_per_trade_r": 0.3,
    }


# ---------------------------------------------------------------------------
# 1. Rejects insufficient trades
# ---------------------------------------------------------------------------

def test_randomized_benchmark_rejects_insufficient_trades():
    engine = RandomizedTimingBenchmarkEngine(
        RandomizedBenchmarkConfig(min_required_trades=5)
    )
    df = _make_df()
    trades = _make_trades(df, n=3)  # < 5

    result = engine.evaluate(df, trades, INITIAL_CASH, _strategy_metrics())

    assert result["status"] == "INSUFFICIENT_TRADES_FOR_RANDOMIZATION"
    assert result["randomized_timing_pass"] is False
    assert any("INSUFFICIENT_TRADES" in r for r in result["failure_reasons"])
    assert result["n_simulations_completed"] == 0


# ---------------------------------------------------------------------------
# 2. Generates the requested number of simulations
# ---------------------------------------------------------------------------

def test_randomized_benchmark_generates_requested_simulations():
    cfg = RandomizedBenchmarkConfig(n_simulations=50, min_required_trades=5)
    engine = RandomizedTimingBenchmarkEngine(cfg)
    df = _make_df(n=300)
    trades = _make_trades(df, n=6)

    result = engine.evaluate(df, trades, INITIAL_CASH, _strategy_metrics())

    assert result["n_simulations"] == 50
    # With 300 bars and 6 trades of ~10 days, non-overlapping schedules should succeed
    assert result["n_simulations_completed"] >= 40, (
        f"Expected at least 40 valid sims, got {result['n_simulations_completed']}"
    )


# ---------------------------------------------------------------------------
# 3. Records real_total_trades correctly
# ---------------------------------------------------------------------------

def test_randomized_benchmark_preserves_trade_count():
    engine = RandomizedTimingBenchmarkEngine(
        RandomizedBenchmarkConfig(n_simulations=20)
    )
    df = _make_df(n=400)
    trades = _make_trades(df, n=8)

    result = engine.evaluate(df, trades, INITIAL_CASH, _strategy_metrics())

    assert result["real_total_trades"] == len(trades), (
        f"Expected {len(trades)} real trades, got {result['real_total_trades']}"
    )


# ---------------------------------------------------------------------------
# 4. Preserves holding periods (feature doesn't crash, produces valid output)
# ---------------------------------------------------------------------------

def test_randomized_benchmark_preserves_holding_periods():
    cfg_on = RandomizedBenchmarkConfig(n_simulations=30, preserve_holding_periods=True)
    cfg_off = RandomizedBenchmarkConfig(n_simulations=30, preserve_holding_periods=False)

    df = _make_df(n=400)
    trades = _make_trades(df, n=7)
    sm = _strategy_metrics()

    result_on = RandomizedTimingBenchmarkEngine(cfg_on).evaluate(df, trades, INITIAL_CASH, sm)
    result_off = RandomizedTimingBenchmarkEngine(cfg_off).evaluate(df, trades, INITIAL_CASH, sm)

    # Both should produce valid output with required keys
    required = {
        "status", "real_total_trades", "n_simulations_completed",
        "random_p75_calmar", "randomized_timing_pass",
    }
    assert required.issubset(result_on.keys())
    assert required.issubset(result_off.keys())
    assert result_on["n_simulations_completed"] >= 20
    assert result_off["n_simulations_completed"] >= 20


# ---------------------------------------------------------------------------
# 5. Seed produces reproducible results
# ---------------------------------------------------------------------------

def test_randomized_benchmark_uses_seed_for_reproducibility():
    cfg = RandomizedBenchmarkConfig(n_simulations=100, random_seed=99)
    df = _make_df()
    trades = _make_trades(df, n=7)
    sm = _strategy_metrics()

    r1 = RandomizedTimingBenchmarkEngine(cfg).evaluate(df, trades, INITIAL_CASH, sm)
    r2 = RandomizedTimingBenchmarkEngine(cfg).evaluate(df, trades, INITIAL_CASH, sm)

    assert r1["random_p75_calmar"] == r2["random_p75_calmar"], "Same seed → same p75"
    assert r1["random_median_total_return_pct"] == r2["random_median_total_return_pct"]


# ---------------------------------------------------------------------------
# 6. Percentiles are monotone: median ≤ p75 ≤ p90
# ---------------------------------------------------------------------------

def test_randomized_benchmark_calculates_percentiles():
    engine = RandomizedTimingBenchmarkEngine(
        RandomizedBenchmarkConfig(n_simulations=200)
    )
    df = _make_df(n=500)
    trades = _make_trades(df, n=7)

    result = engine.evaluate(df, trades, INITIAL_CASH, _strategy_metrics())

    assert result["random_median_total_return_pct"] is not None
    assert result["random_p75_total_return_pct"] is not None
    assert result["random_p90_total_return_pct"] is not None

    assert result["random_median_total_return_pct"] <= result["random_p75_total_return_pct"], (
        "median ≤ p75 for return"
    )
    assert result["random_p75_total_return_pct"] <= result["random_p90_total_return_pct"], (
        "p75 ≤ p90 for return"
    )
    assert result["random_median_calmar"] <= result["random_p75_calmar"], (
        "median ≤ p75 for calmar"
    )


# ---------------------------------------------------------------------------
# 7. Pass logic: pass only when real > p75 for BOTH return and calmar
# ---------------------------------------------------------------------------

def test_randomized_benchmark_passes_only_above_p75_return_and_calmar():
    engine = RandomizedTimingBenchmarkEngine(
        RandomizedBenchmarkConfig(n_simulations=300)
    )
    df = _make_df(n=500)
    trades = _make_trades(df, n=7)

    # Scenario A: strategy metrics far above any plausible random distribution → PASS
    high_sm = _strategy_metrics(total_return=99999.0, calmar=99999.0)
    result_pass = engine.evaluate(df, trades, INITIAL_CASH, high_sm)
    assert result_pass["randomized_timing_pass"] is True, (
        f"Expected PASS, got failure_reasons={result_pass['failure_reasons']}"
    )

    # Scenario B: strategy calmar near zero → calmar check fails → FAIL
    low_sm = _strategy_metrics(total_return=99999.0, calmar=0.0001)
    result_fail = engine.evaluate(df, trades, INITIAL_CASH, low_sm)
    assert result_fail["randomized_timing_pass"] is False
    assert any("CALMAR_NOT_ABOVE_P75_RANDOM" in r for r in result_fail["failure_reasons"]), (
        f"Expected calmar failure reason, got {result_fail['failure_reasons']}"
    )


# ---------------------------------------------------------------------------
# 8. Runner records errors per ticker without crashing
# ---------------------------------------------------------------------------

def test_randomized_runner_records_errors_without_crashing(tmp_path):
    def bad_fetch(ticker: str, start: str, end: str, output: str) -> None:
        raise RuntimeError(f"Network unavailable for {ticker}")

    cfg = RandomizedBenchmarkConfig(n_simulations=10)
    df_out = run_randomized_benchmark(
        tickers=["FAKE1", "FAKE2"],
        start="2020-01-01",
        end="2024-12-31",
        adjust=False,
        output=str(tmp_path / "rand_err.csv"),
        data_dir=tmp_path,
        fetch_fn=bad_fetch,
        random_config=cfg,
    )

    assert len(df_out) == 2
    assert (df_out["status"] == "ERROR").all()
    assert (df_out["randomized_timing_pass"] == False).all()


# ---------------------------------------------------------------------------
# 9. Runner CSV contains all required columns
# ---------------------------------------------------------------------------

def test_randomized_summary_contains_required_columns(tmp_path):
    if not AAPL_CSV.exists():
        pytest.skip("AAPL_2020-01-01_2024-12-31.csv not found in data/; run fetch first")

    def mock_fetch(ticker: str, start: str, end: str, output: str) -> None:
        src = DATA_DIR / f"{ticker}_{start}_{end}.csv"
        shutil.copy(src, output)

    cfg = RandomizedBenchmarkConfig(n_simulations=50)
    df = run_randomized_benchmark(
        tickers=["AAPL"],
        start="2020-01-01",
        end="2024-12-31",
        adjust=True,
        output=str(tmp_path / "rand_cols.csv"),
        data_dir=tmp_path,
        fetch_fn=mock_fetch,
        random_config=cfg,
    )

    required = {
        "ticker", "status",
        "real_total_trades", "n_simulations",
        "real_total_return_pct",
        "random_median_total_return_pct", "random_p75_total_return_pct",
        "random_p90_total_return_pct",
        "real_calmar", "random_median_calmar", "random_p75_calmar",
        "random_p90_calmar",
        "real_max_drawdown_pct", "random_median_max_drawdown_pct",
        "timing_edge_percentile_return", "timing_edge_percentile_calmar",
        "beats_random_median_return", "beats_random_p75_return",
        "beats_random_median_calmar", "beats_random_p75_calmar",
        "randomized_timing_pass", "failure_reasons",
    }
    missing = required - set(df.columns)
    assert not missing, f"Missing columns: {missing}"
    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "AAPL"
