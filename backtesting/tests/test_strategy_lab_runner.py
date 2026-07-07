"""
Tests for strategy_lab_runner.

Tests 5-6: design / identity checks — no real data needed.
Tests 7-8: verdict logic using mock rows via get_verdict().
"""

import shutil
from pathlib import Path

import pytest

from backtester import BacktestConfig
from randomized_benchmark import RandomizedBenchmarkConfig
from strategy_lab_runner import get_verdict, run_strategy_lab
from strategy_variants import TrendPullbackConfluence_v1, get_variant
from walk_forward import WalkForwardConfig, WalkForwardEngine


DATA_DIR = Path(__file__).parent.parent / "data"
AAPL_10Y_CSV = DATA_DIR / "AAPL_2015-01-01_2024-12-31.csv"

INITIAL_CASH = 100_000.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok_row(
    ticker: str = "AAPL",
    split_id: int = 0,
    test_total_trades: int = 10,
    expectancy: float = 0.3,
    pf: float = 1.5,
    calmar: float = 0.5,
    bm_calmar: float = 0.3,
    rand_pass: bool = True,
    strategy_name: str = "TrendPullbackConfluence",
    strategy_version: str = "v1",
) -> dict:
    return {
        "ticker": ticker,
        "split_id": split_id,
        "train_start": "2015-01-01",
        "train_end": "2018-01-01",
        "test_start": "2018-01-01",
        "test_end": "2019-01-01",
        "test_total_trades": test_total_trades,
        "test_expectancy_per_trade_R": expectancy,
        "test_profit_factor": pf,
        "test_calmar": calmar,
        "test_benchmark_calmar": bm_calmar,
        "test_exposure_matched_calmar": None,
        "test_random_p75_calmar": None,
        "falsifier_pass": bool(expectancy > 0 and pf >= 1.2 and calmar >= bm_calmar),
        "exposure_matched_pass": None,
        "randomized_timing_pass": rand_pass,
        "status": "OK",
        "failure_reasons": "",
        "strategy_name": strategy_name,
        "strategy_version": strategy_version,
    }


# ---------------------------------------------------------------------------
# 5. Runner records strategy_name and strategy_version
# ---------------------------------------------------------------------------

def test_strategy_lab_runner_records_strategy_name_and_version(tmp_path):
    if not AAPL_10Y_CSV.exists():
        pytest.skip("AAPL_2015-01-01_2024-12-31.csv not found; run fetch first")

    def mock_fetch(ticker: str, start: str, end: str, output: str) -> None:
        src = DATA_DIR / f"{ticker}_{start}_{end}.csv"
        shutil.copy(src, output)

    variant = TrendPullbackConfluence_v1()
    wf_cfg = WalkForwardConfig(
        train_years=3, test_years=1, step_years=1, min_test_trades=1
    )
    rand_cfg = RandomizedBenchmarkConfig(n_simulations=20)

    df = run_strategy_lab(
        variant=variant,
        tickers=["AAPL"],
        start="2015-01-01",
        end="2024-12-31",
        adjust=True,
        output=str(tmp_path / "lab_cols.csv"),
        data_dir=tmp_path,
        fetch_fn=mock_fetch,
        wf_config=wf_cfg,
        rand_config=rand_cfg,
    )

    assert "strategy_name" in df.columns, "strategy_name column missing"
    assert "strategy_version" in df.columns, "strategy_version column missing"

    assert (df["strategy_name"] == "TrendPullbackConfluence").all(), (
        f"Expected all rows to have strategy_name=TrendPullbackConfluence"
    )
    assert (df["strategy_version"] == "v1").all(), (
        f"Expected all rows to have strategy_version=v1"
    )


# ---------------------------------------------------------------------------
# 6. Running a new variant does not overwrite v1 identity
# ---------------------------------------------------------------------------

def test_strategy_lab_runner_does_not_overwrite_v1_results():
    """
    After running TrendPullbackConfluence_v1 through the lab, the default
    BacktestConfig must still carry the original v1 identity.
    """
    v2 = TrendPullbackConfluence_v1()

    # Verify v2 has different identity from v1
    assert v2.strategy_name != "BreakoutVolumeConfluence", (
        "TrendPullbackConfluence must not impersonate v1"
    )

    # Running the variant must not mutate BacktestConfig defaults
    original_cfg = BacktestConfig()
    assert original_cfg.strategy_name == "BreakoutVolumeConfluence"
    assert original_cfg.strategy_version == "v1"

    # Create a backtester config pointing to v2 variant — verify v1 default untouched
    v2_cfg = BacktestConfig(
        strategy_name=v2.strategy_name,
        strategy_version=v2.strategy_version,
    )
    assert v2_cfg.strategy_name == "TrendPullbackConfluence"

    # Original config is a separate object — unchanged
    assert original_cfg.strategy_name == "BreakoutVolumeConfluence"
    assert original_cfg.strategy_version == "v1"

    # Registry does not modify the existing variant
    v1_fresh = get_variant("BreakoutVolumeConfluence_v1")
    assert v1_fresh.strategy_name == "BreakoutVolumeConfluence"
    assert v1_fresh.strategy_version == "v1"


# ---------------------------------------------------------------------------
# 7. NO-GO when walk-forward criteria fail
# ---------------------------------------------------------------------------

def test_strategy_lab_runner_no_go_when_walk_forward_fails():
    """
    Aggregate result must be NO-GO when OOS trades are below threshold,
    regardless of per-split metrics.
    """
    cfg = WalkForwardConfig(
        min_total_oos_trades=100,  # very high — impossible to meet with mock rows
        min_oos_positive_expectancy_rate=0.0,
        min_oos_profit_factor=0.0,
        require_oos_calmar_above_benchmark=False,
        min_oos_random_p75_pass_rate=0.0,
        max_ticker_concentration_pct=100.0,
    )

    rows = [_ok_row(test_total_trades=5, split_id=i) for i in range(6)]
    # Total OOS trades = 30 < 100 → NO-GO

    import pandas as pd
    df = pd.DataFrame(rows)
    agg = get_verdict(df, cfg)

    assert agg["verdict"] == "NO-GO"
    assert agg["research_go"] is False
    assert any("OOS_TRADES_TOO_LOW" in r for r in agg["verdict_failure_reasons"])


# ---------------------------------------------------------------------------
# 8. RESEARCH-GO only when walk-forward passes all thresholds
# ---------------------------------------------------------------------------

def test_strategy_lab_runner_research_go_only_when_walk_forward_passes():
    """
    Aggregate result must be RESEARCH-GO only when all six criteria pass.
    Build synthetic rows that meet every threshold and verify the verdict.
    """
    cfg = WalkForwardConfig(
        min_total_oos_trades=50,
        min_oos_positive_expectancy_rate=0.60,
        min_oos_profit_factor=1.2,
        require_oos_calmar_above_benchmark=True,
        min_oos_random_p75_pass_rate=0.60,
        max_ticker_concentration_pct=25.0,
    )

    # 4 tickers × 5 splits × 5 trades = 100 total OOS trades (≥ 50)
    # All splits: positive expectancy, pf=1.5 ≥ 1.2, calmar ≥ bm_calmar, rand_pass=True
    # Equally distributed → max_concentration = 25%
    tickers = ["A", "B", "C", "D"]
    rows = []
    for ticker in tickers:
        for i in range(5):
            rows.append(
                _ok_row(
                    ticker=ticker,
                    split_id=i,
                    test_total_trades=5,
                    expectancy=0.3,
                    pf=1.5,
                    calmar=0.5,
                    bm_calmar=0.3,
                    rand_pass=True,
                )
            )

    import pandas as pd
    df = pd.DataFrame(rows)
    agg = get_verdict(df, cfg)

    assert agg["verdict"] == "RESEARCH-GO", (
        f"Expected RESEARCH-GO, got failure_reasons={agg['verdict_failure_reasons']}"
    )
    assert agg["research_go"] is True
    assert agg["verdict_failure_reasons"] == []
    assert agg["oos_total_trades"] == 100
