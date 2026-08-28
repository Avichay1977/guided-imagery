"""
Tests for WalkForwardEngine and walk_forward_runner.

Tests 1-2 and 5-10 use only synthetic data / mock rows.
Tests 3, 4, 9 require real AAPL data and are skipped if the CSV is absent.
"""

import shutil
from pathlib import Path

import pandas as pd
import pytest

from backtester import BacktestConfig
from data_loader import DataLoader
from features import FeatureEngine
from randomized_benchmark import RandomizedBenchmarkConfig
from walk_forward import WalkForwardConfig, WalkForwardEngine
from walk_forward_runner import run_walk_forward


DATA_DIR = Path(__file__).parent.parent / "data"
AAPL_5Y_CSV = DATA_DIR / "AAPL_2020-01-01_2024-12-31.csv"
AAPL_10Y_CSV = DATA_DIR / "AAPL_2015-01-01_2024-12-31.csv"

INITIAL_CASH = 100_000.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok_row(
    ticker: str = "AAPL",
    split_id: int = 0,
    test_total_trades: int = 10,
    test_expectancy_per_trade_R: float = 0.3,
    test_profit_factor: float = 1.5,
    test_calmar: float = 0.5,
    test_benchmark_calmar: float = 0.3,
    randomized_timing_pass: bool = True,
    falsifier_pass: bool = True,
) -> dict:
    return {
        "ticker": ticker,
        "split_id": split_id,
        "train_start": "2015-01-01",
        "train_end": "2018-01-01",
        "test_start": "2018-01-01",
        "test_end": "2019-01-01",
        "test_total_trades": test_total_trades,
        "test_expectancy_per_trade_R": test_expectancy_per_trade_R,
        "test_profit_factor": test_profit_factor,
        "test_calmar": test_calmar,
        "test_benchmark_calmar": test_benchmark_calmar,
        "test_exposure_matched_calmar": None,
        "test_random_p75_calmar": None,
        "falsifier_pass": falsifier_pass,
        "exposure_matched_pass": None,
        "randomized_timing_pass": randomized_timing_pass,
        "status": "OK",
        "failure_reasons": "",
    }


# ---------------------------------------------------------------------------
# 1. Generates expected splits
# ---------------------------------------------------------------------------

def test_walk_forward_generates_expected_splits():
    cfg = WalkForwardConfig(train_years=3, test_years=1, step_years=1)
    engine = WalkForwardEngine(cfg)

    splits = engine.generate_splits("2015-01-01", "2024-12-31")

    # With 10-year window, train=3+test=1=4 year minimum, step=1:
    # splits at test 2018, 2019, 2020, 2021, 2022, 2023 → 6 splits
    assert len(splits) >= 5, f"Expected at least 5 splits, got {len(splits)}"
    assert len(splits) <= 8, f"Expected at most 8 splits, got {len(splits)}"

    # First split correctness
    s0 = splits[0]
    assert s0["split_id"] == 0
    assert s0["train_start"] == "2015-01-01"
    assert s0["train_end"] == "2018-01-01"
    assert s0["test_start"] == "2018-01-01"
    assert s0["test_end"] == "2019-01-01"

    # IDs are sequential
    for i, s in enumerate(splits):
        assert s["split_id"] == i

    # Consecutive splits differ by step_years=1 year
    for i in range(1, len(splits)):
        prev_ts = pd.Timestamp(splits[i - 1]["train_start"])
        curr_ts = pd.Timestamp(splits[i]["train_start"])
        expected = prev_ts + pd.DateOffset(years=1)
        assert curr_ts == expected, (
            f"Split {i} train_start {curr_ts} != expected {expected}"
        )

    # All test windows end on or before the specified end date
    end_dt = pd.Timestamp("2024-12-31")
    for s in splits:
        assert pd.Timestamp(s["test_end"]) <= end_dt + pd.DateOffset(days=1)


# ---------------------------------------------------------------------------
# 2. Does not optimize parameters
# ---------------------------------------------------------------------------

def test_walk_forward_does_not_optimize_parameters():
    bt_cfg = BacktestConfig(min_confluence_score=5, atr_stop_multiplier=2.0)
    engine = WalkForwardEngine(backtester_config=bt_cfg)

    splits = engine.generate_splits("2018-01-01", "2024-12-31")

    # Config must be unchanged regardless of splits
    assert engine.backtester_config.min_confluence_score == 5
    assert engine.backtester_config.atr_stop_multiplier == 2.0

    # Engine must not have any fitted-parameter attributes
    assert not hasattr(engine, "_fitted_params"), (
        "Engine must not store fitted parameters"
    )
    assert not hasattr(engine, "_optimized_config"), (
        "Engine must not store optimized config"
    )

    # Split dicts must not contain parameter overrides
    for split in splits:
        assert "min_confluence_score" not in split
        assert "atr_stop_multiplier" not in split
        assert "backtester_config" not in split


# ---------------------------------------------------------------------------
# 3. Marks insufficient trade splits
# ---------------------------------------------------------------------------

def test_walk_forward_marks_insufficient_trade_splits():
    if not AAPL_5Y_CSV.exists():
        pytest.skip("AAPL_2020-01-01_2024-12-31.csv not found; run fetch first")

    loader = DataLoader(use_adjusted_close=True)
    df = loader.load_from_csv(AAPL_5Y_CSV)
    df = FeatureEngine().generate_shifted_features(df, drop_warmup=False)

    # Force all splits to fail the trade threshold
    cfg = WalkForwardConfig(
        train_years=3,
        test_years=1,
        step_years=1,
        min_test_trades=9999,
    )
    engine = WalkForwardEngine(cfg)

    rows = engine.evaluate_ticker(df, "AAPL", "2020-01-01", "2024-12-31")

    # At least one split must exist
    assert len(rows) >= 1, "Expected at least 1 split"

    statuses = {r["status"] for r in rows}
    assert "INSUFFICIENT_TEST_TRADES" in statuses or "INSUFFICIENT_TEST_DATA" in statuses, (
        f"Expected insufficient status, got {statuses}"
    )

    # No row with insufficient trades should be marked passing
    for r in rows:
        if r["status"] in ("INSUFFICIENT_TEST_TRADES", "INSUFFICIENT_TEST_DATA"):
            assert r["falsifier_pass"] is False
            assert r["randomized_timing_pass"] is False


# ---------------------------------------------------------------------------
# 4. Records OOS metrics in per-split rows
# ---------------------------------------------------------------------------

def test_walk_forward_records_oos_metrics():
    if not AAPL_10Y_CSV.exists():
        pytest.skip("AAPL_2015-01-01_2024-12-31.csv not found; run fetch first")

    loader = DataLoader(use_adjusted_close=True)
    df = loader.load_from_csv(AAPL_10Y_CSV)
    df = FeatureEngine().generate_shifted_features(df, drop_warmup=False)

    cfg = WalkForwardConfig(
        train_years=3, test_years=1, step_years=1, min_test_trades=1
    )
    engine = WalkForwardEngine(
        cfg, random_config=RandomizedBenchmarkConfig(n_simulations=50)
    )

    rows = engine.evaluate_ticker(df, "AAPL", "2015-01-01", "2024-12-31")

    required_keys = {
        "ticker", "split_id", "train_start", "train_end",
        "test_start", "test_end", "test_total_trades",
        "test_expectancy_per_trade_R", "test_profit_factor",
        "test_calmar", "test_benchmark_calmar",
        "test_exposure_matched_calmar", "test_random_p75_calmar",
        "falsifier_pass", "exposure_matched_pass",
        "randomized_timing_pass", "status", "failure_reasons",
    }

    for row in rows:
        missing = required_keys - set(row.keys())
        assert not missing, f"Split {row.get('split_id')} missing keys: {missing}"

    ok_rows = [r for r in rows if r["status"] == "OK"]
    assert len(ok_rows) >= 1, "Expected at least 1 OK split"

    for r in ok_rows:
        assert r["test_total_trades"] >= 1
        assert r["test_calmar"] is not None
        assert r["test_benchmark_calmar"] is not None
        assert isinstance(r["falsifier_pass"], bool)
        assert isinstance(r["randomized_timing_pass"], bool)


# ---------------------------------------------------------------------------
# 5. NO-GO when OOS trades too low
# ---------------------------------------------------------------------------

def test_walk_forward_no_go_when_oos_trades_too_low():
    cfg = WalkForwardConfig(min_total_oos_trades=50)
    engine = WalkForwardEngine(cfg)

    rows = [
        _ok_row(test_total_trades=3, split_id=i) for i in range(5)
    ]
    # Total = 15 < 50

    agg = engine.aggregate(rows)

    assert agg["research_go"] is False
    assert agg["verdict"] == "NO-GO"
    assert any("OOS_TRADES_TOO_LOW" in r for r in agg["verdict_failure_reasons"])


# ---------------------------------------------------------------------------
# 6. NO-GO when positive expectancy rate too low
# ---------------------------------------------------------------------------

def test_walk_forward_no_go_when_positive_expectancy_rate_too_low():
    cfg = WalkForwardConfig(
        min_total_oos_trades=5,
        min_oos_positive_expectancy_rate=0.60,
        min_oos_profit_factor=0.0,       # disable
        require_oos_calmar_above_benchmark=False,
        min_oos_random_p75_pass_rate=0.0, # disable
    )
    engine = WalkForwardEngine(cfg)

    rows = [
        _ok_row(test_expectancy_per_trade_R=-0.1, test_total_trades=5, split_id=i)
        for i in range(6)
    ]
    # 0/6 positive → rate = 0.0 < 0.60

    agg = engine.aggregate(rows)

    assert agg["research_go"] is False
    assert any(
        "OOS_POSITIVE_EXPECTANCY_RATE_TOO_LOW" in r
        for r in agg["verdict_failure_reasons"]
    )


# ---------------------------------------------------------------------------
# 7. NO-GO when randomized timing pass rate too low
# ---------------------------------------------------------------------------

def test_walk_forward_no_go_when_randomized_pass_rate_too_low():
    cfg = WalkForwardConfig(
        min_total_oos_trades=5,
        min_oos_positive_expectancy_rate=0.0,  # disable
        min_oos_profit_factor=0.0,              # disable
        require_oos_calmar_above_benchmark=False,
        min_oos_random_p75_pass_rate=0.60,
    )
    engine = WalkForwardEngine(cfg)

    rows = [
        _ok_row(randomized_timing_pass=False, test_total_trades=5, split_id=i)
        for i in range(6)
    ]
    # 0/6 pass → rate = 0.0 < 0.60

    agg = engine.aggregate(rows)

    assert agg["research_go"] is False
    assert any(
        "OOS_RANDOMIZED_TIMING_PASS_RATE_TOO_LOW" in r
        for r in agg["verdict_failure_reasons"]
    )


# ---------------------------------------------------------------------------
# 8. RESEARCH-GO when all thresholds pass
# ---------------------------------------------------------------------------

def test_walk_forward_research_go_when_all_thresholds_pass():
    cfg = WalkForwardConfig(
        min_total_oos_trades=50,
        min_oos_positive_expectancy_rate=0.60,
        min_oos_profit_factor=1.2,
        require_oos_calmar_above_benchmark=True,
        min_oos_random_p75_pass_rate=0.60,
        max_ticker_concentration_pct=25.0,
    )
    engine = WalkForwardEngine(cfg)

    # 20 splits across 4 tickers, each with 5 trades → 100 total OOS trades
    tickers = ["AAPL", "MSFT", "GOOGL", "NVDA"]
    rows = []
    for i, ticker in enumerate(tickers):
        for j in range(5):
            rows.append(
                _ok_row(
                    ticker=ticker,
                    split_id=j,
                    test_total_trades=5,
                    test_expectancy_per_trade_R=0.3,
                    test_profit_factor=1.5,
                    test_calmar=0.5,
                    test_benchmark_calmar=0.3,
                    randomized_timing_pass=True,
                    falsifier_pass=True,
                )
            )

    agg = engine.aggregate(rows)

    assert agg["research_go"] is True, (
        f"Expected RESEARCH-GO, got failure_reasons={agg['verdict_failure_reasons']}"
    )
    assert agg["verdict"] == "RESEARCH-GO"
    assert agg["verdict_failure_reasons"] == []
    assert agg["oos_total_trades"] == 100
    assert agg["oos_positive_expectancy_rate"] == 1.0
    assert agg["oos_calmar_above_benchmark_rate"] == 1.0
    assert agg["oos_randomized_timing_pass_rate"] == 1.0


# ---------------------------------------------------------------------------
# 9. Runner CSV contains all required columns
# ---------------------------------------------------------------------------

def test_walk_forward_summary_contains_required_columns(tmp_path):
    if not AAPL_10Y_CSV.exists():
        pytest.skip("AAPL_2015-01-01_2024-12-31.csv not found; run fetch first")

    def mock_fetch(ticker: str, start: str, end: str, output: str) -> None:
        src = DATA_DIR / f"{ticker}_{start}_{end}.csv"
        shutil.copy(src, output)

    wf_cfg = WalkForwardConfig(
        train_years=3, test_years=1, step_years=1, min_test_trades=1
    )
    rand_cfg = RandomizedBenchmarkConfig(n_simulations=30)

    df = run_walk_forward(
        tickers=["AAPL"],
        start="2015-01-01",
        end="2024-12-31",
        adjust=True,
        output=str(tmp_path / "wf_cols.csv"),
        data_dir=tmp_path,
        fetch_fn=mock_fetch,
        wf_config=wf_cfg,
        random_config=rand_cfg,
    )

    required = {
        "ticker", "split_id", "train_start", "train_end",
        "test_start", "test_end", "test_total_trades",
        "test_expectancy_per_trade_R", "test_profit_factor",
        "test_calmar", "test_benchmark_calmar",
        "test_exposure_matched_calmar", "test_random_p75_calmar",
        "falsifier_pass", "exposure_matched_pass",
        "randomized_timing_pass", "status", "failure_reasons",
    }
    missing = required - set(df.columns)
    assert not missing, f"Missing columns: {missing}"

    assert len(df) >= 1, "Expected at least 1 split row"
    assert (df["ticker"] == "AAPL").all()


# ---------------------------------------------------------------------------
# 10. NO-GO when one ticker dominates OOS trades (concentration > 25%)
# ---------------------------------------------------------------------------

def test_walk_forward_does_not_select_tickers_by_past_results():
    cfg = WalkForwardConfig(
        min_total_oos_trades=5,
        min_oos_positive_expectancy_rate=0.0,
        min_oos_profit_factor=0.0,
        require_oos_calmar_above_benchmark=False,
        min_oos_random_p75_pass_rate=0.0,
        max_ticker_concentration_pct=25.0,
    )
    engine = WalkForwardEngine(cfg)

    # One dominant ticker with 80 trades, three others with 5 each → 90% concentration
    rows = [
        _ok_row(ticker="DOMINANT", test_total_trades=20, split_id=i) for i in range(4)
    ]
    rows += [
        _ok_row(ticker=f"OTHER{i}", test_total_trades=1, split_id=0) for i in range(3)
    ]
    # DOMINANT: 80/83 = 96% > 25%

    agg = engine.aggregate(rows)

    assert agg["research_go"] is False
    assert any(
        "TICKER_CONCENTRATION" in r for r in agg["verdict_failure_reasons"]
    ), f"Expected TICKER_CONCENTRATION, got {agg['verdict_failure_reasons']}"
    assert "DOMINANT" in " ".join(agg["verdict_failure_reasons"])
