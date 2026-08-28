"""
Research orchestrator for RelativeStrengthRotation_v1.

Chains all pipeline components in one callable sequence:
  CSV data → feature matrix → walk-forward splits →
  [backtester + B1 + B2 + p95] → v1.2 row → CSV report

This module:
  - Never emits live or research verdict tokens.
  - Never authorizes a research run by itself.
  - Marks every output with research_authorized=False until an explicit
    separate gate (RDR-002 + orchestrator authorization) is granted.
  - Never modifies frozen strategy parameters.
  - Never fetches market data.
  - Never calls strategy_lab_runner.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from rotation_backtester import RotationBacktester, RotationBacktesterConfig
from rotation_benchmark_b1 import (
    B1BuyHoldBenchmarkConfig,
    B1BuyHoldBenchmarkResult,
    calculate_b1_buy_hold_benchmark,
)
from rotation_benchmark_b2 import calculate_equal_weight_universe_benchmark
from rotation_feature_matrix import (
    RotationFeatureConfig,
    add_cross_sectional_ranks,
    build_equal_weight_buy_hold_index,
    build_rotation_feature_matrix,
)
from rotation_random_selection_comparator import (
    RandomSelectionComparatorConfig,
    calculate_randomized_selection_p95,
)
from rotation_v1_2_toy_csv_report import (
    build_rotation_toy_report_rows,
    write_rotation_v1_2_toy_csv_report,
)
from rotation_walk_forward_adapter import (
    RotationWalkForwardSplit,
    slice_rotation_inputs_for_test_window,
)


# ---------------------------------------------------------------------------
# Frozen universe (verbatim from spec)
# ---------------------------------------------------------------------------

FROZEN_UNIVERSE: list[str] = [
    "AAPL", "MSFT", "NVDA", "AMD", "META", "AMZN", "GOOGL",
    "TSLA", "NFLX", "AVGO", "CRM", "ORCL", "INTC", "CSCO", "IBM",
]

# Frozen split spec (verbatim from RESEARCH_SPLIT_SPEC_RELATIVE_STRENGTH_ROTATION_V1.md)
SPLIT_SPEC_VERSION: str = "RSR_V1_SPLIT_SPEC_v1"
TRAIN_YEARS: int = 3
TEST_YEARS: int = 1
STEP_YEARS: int = 1
WINDOW_START: str = "2015-01-01"
WINDOW_END: str = "2024-12-31"


# ---------------------------------------------------------------------------
# Config / Result
# ---------------------------------------------------------------------------

@dataclass
class OrchestratorConfig:
    data_dir: str = "data"
    output_dir: str = "research_outputs/relative_strength_rotation_v1"
    universe: list[str] = field(default_factory=lambda: list(FROZEN_UNIVERSE))
    window_start: str = WINDOW_START
    window_end: str = WINDOW_END
    train_years: int = TRAIN_YEARS
    test_years: int = TEST_YEARS
    step_years: int = STEP_YEARS
    n_random_simulations: int = 1000
    random_seed: int = 42
    report_filename: str = "rotation_v1_2_walkforward_report.csv"


@dataclass
class OrchestratorSplitResult:
    split: RotationWalkForwardSplit
    strategy_result: Any
    b1_result: Any
    b2_result: Any
    p95_result: Any
    summary_row: dict
    diagnostics: dict = field(default_factory=dict)


@dataclass
class OrchestratorRunResult:
    split_results: list[OrchestratorSplitResult]
    report_path: Optional[Path]
    diagnostics: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_universe_csvs(
    data_dir: str | Path,
    universe: list[str],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, pd.DataFrame]:
    """
    Load ticker CSVs from data_dir into {ticker: DataFrame}.

    Each DataFrame has a DatetimeIndex (timestamp column) and lowercase columns.
    Applies optional start/end date filter. Raises FileNotFoundError if a ticker
    CSV is missing. Raises ValueError if a ticker has no data in the date window.
    Does not fill, forward-fill, back-fill, or interpolate.
    """
    data_dir = Path(data_dir)
    universe_data: dict[str, pd.DataFrame] = {}

    for ticker in universe:
        # Prefer the canonical 2015-01-01_2024-12-31 file; fall back to any match
        candidates = sorted(data_dir.glob(f"{ticker}_*.csv"))
        if not candidates:
            candidates = [
                f for f in data_dir.iterdir()
                if f.suffix.lower() == ".csv"
                and f.stem.upper().startswith(ticker.upper() + "_")
            ]
        if not candidates:
            raise FileNotFoundError(
                f"No CSV found for ticker {ticker!r} in {data_dir}"
            )

        path = candidates[0]
        for c in candidates:
            if f"{ticker}_2015-01-01_2024-12-31" in c.name:
                path = c
                break

        df = pd.read_csv(path, index_col="timestamp", parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        df = df.sort_index()

        if start_date is not None:
            df = df[df.index >= pd.Timestamp(start_date)]
        if end_date is not None:
            df = df[df.index <= pd.Timestamp(end_date)]

        if df.empty:
            raise ValueError(
                f"No data for {ticker!r} in window [{start_date}, {end_date}]"
            )

        universe_data[ticker] = df

    return universe_data


# ---------------------------------------------------------------------------
# Walk-forward split generation
# ---------------------------------------------------------------------------

def generate_walk_forward_splits(
    window_start: str = WINDOW_START,
    window_end: str = WINDOW_END,
    train_years: int = TRAIN_YEARS,
    test_years: int = TEST_YEARS,
    step_years: int = STEP_YEARS,
) -> list[RotationWalkForwardSplit]:
    """
    Generate walk-forward splits per the frozen split spec.

    Produces sliding windows with:
      train window : train_years long
      test window  : test_years long (immediately follows train)
      step         : step_years (both windows advance by step_years each iteration)

    Returns a list of RotationWalkForwardSplit in chronological order.
    Raises ValueError if no splits fit in the window.
    """
    start = pd.Timestamp(window_start)
    end = pd.Timestamp(window_end)

    if start >= end:
        raise ValueError(f"window_start ({window_start}) must be before window_end ({window_end})")
    if train_years < 1 or test_years < 1 or step_years < 1:
        raise ValueError("train_years, test_years, step_years must all be >= 1")

    splits: list[RotationWalkForwardSplit] = []
    current_train_start = start
    split_num = 1

    while True:
        # Train window ends exactly train_years after its start (last day inclusive)
        train_end = (
            current_train_start + pd.DateOffset(years=train_years) - pd.Timedelta(days=1)
        )
        test_start = train_end + pd.Timedelta(days=1)
        test_end = test_start + pd.DateOffset(years=test_years) - pd.Timedelta(days=1)

        # Stop if test window runs past the available window
        if test_end > end:
            break

        splits.append(
            RotationWalkForwardSplit(
                split_id=f"WF-{split_num:02d}",
                train_start=current_train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
        )

        current_train_start = current_train_start + pd.DateOffset(years=step_years)
        split_num += 1

    if not splits:
        raise ValueError(
            f"No valid splits fit in [{window_start}, {window_end}] "
            f"with train={train_years}y, test={test_years}y, step={step_years}y."
        )

    return splits


# ---------------------------------------------------------------------------
# Returns builder
# ---------------------------------------------------------------------------

def build_returns_by_ticker(
    universe_data: dict[str, pd.DataFrame],
) -> dict[str, pd.Series]:
    """
    Compute daily close-to-close simple returns per ticker.

    Returns a dict {ticker: pd.Series}. The first bar gets return=0.0.
    NaN propagated from raw data is left as-is (not filled).
    """
    returns: dict[str, pd.Series] = {}
    for ticker, df in universe_data.items():
        close = df["close"].sort_index()
        ret = close.pct_change()
        if len(ret) > 0:
            ret.iloc[0] = 0.0
        ret.name = ticker
        returns[ticker] = ret
    return returns


# ---------------------------------------------------------------------------
# Eligible-by-date extractor
# ---------------------------------------------------------------------------

def extract_eligible_by_date(
    feature_matrix: pd.DataFrame,
    rebalance_dates: list[pd.Timestamp],
) -> dict[pd.Timestamp, list[str]]:
    """
    Extract {Timestamp: [eligible_tickers]} from feature matrix for each rebalance date.

    A ticker is eligible on a given rebalance date when is_rotation_eligible == True.
    Returns an empty list for dates where no tickers are eligible.
    """
    fm = feature_matrix.copy()
    fm["date"] = pd.to_datetime(fm["date"])
    result: dict[pd.Timestamp, list[str]] = {}
    for rd in rebalance_dates:
        ts = pd.Timestamp(rd)
        mask = (fm["date"] == ts) & (fm["is_rotation_eligible"].astype(bool))
        result[ts] = fm.loc[mask, "ticker"].tolist()
    return result


# ---------------------------------------------------------------------------
# Aggregate B1 computation
# ---------------------------------------------------------------------------

def compute_aggregate_b1(
    universe_data: dict[str, pd.DataFrame],
    test_start: Any,
    test_end: Any,
    universe: list[str],
    config: Optional[B1BuyHoldBenchmarkConfig] = None,
) -> B1BuyHoldBenchmarkResult:
    """
    Compute an aggregate B1 (equal-weight buy-and-hold) for the test window.

    Builds the equal-weight buy-and-hold index across the universe and applies
    calculate_b1_buy_hold_benchmark to it. Represents the passive baseline:
    "buy all 15 tickers equally at test start, hold until test end."

    Raises ValueError if no data is available in the test window.
    """
    cfg = config or B1BuyHoldBenchmarkConfig()
    ts_start = pd.Timestamp(test_start)
    ts_end = pd.Timestamp(test_end)

    test_data: dict[str, pd.DataFrame] = {}
    for ticker in universe:
        if ticker not in universe_data:
            continue
        df = universe_data[ticker]
        mask = (df.index >= ts_start) & (df.index <= ts_end)
        sliced = df.loc[mask]
        if not sliced.empty:
            test_data[ticker] = sliced

    if not test_data:
        raise ValueError(
            f"No test data for any ticker in [{test_start}, {test_end}]"
        )

    bh_index = build_equal_weight_buy_hold_index(test_data)
    return calculate_b1_buy_hold_benchmark(bh_index, config=cfg)


# ---------------------------------------------------------------------------
# Single-split runner
# ---------------------------------------------------------------------------

def run_single_split(
    split: RotationWalkForwardSplit,
    universe_data: dict[str, pd.DataFrame],
    feature_matrix: pd.DataFrame,
    returns_by_ticker: dict[str, pd.Series],
    backtester_config: Optional[RotationBacktesterConfig] = None,
    p95_config: Optional[RandomSelectionComparatorConfig] = None,
    universe: Optional[list[str]] = None,
) -> OrchestratorSplitResult:
    """
    Run all pipeline components for a single walk-forward split.

    Steps for the TEST WINDOW only:
      1. Slice feature_matrix and returns to test window.
      2. Run RotationBacktester on test-window data.
      3. Compute aggregate B1 (equal-weight buy-and-hold).
      4. Compute B2 (monthly-rebalanced equal-weight universe).
      5. Compute p95 randomized-selection comparator.
      6. Build v1.2 summary row.

    The train window is NEVER used for trading decisions — only for feature warmup
    (which is already embedded in the full feature_matrix).
    """
    bt_cfg = backtester_config or RotationBacktesterConfig()
    p95_cfg = p95_config or RandomSelectionComparatorConfig()
    effective_universe: list[str] = universe if universe is not None else list(FROZEN_UNIVERSE)

    # 1. Slice to test window
    sliced = slice_rotation_inputs_for_test_window(
        feature_matrix, returns_by_ticker, split
    )
    sliced_fm = sliced["feature_matrix"]
    sliced_returns = sliced["returns_by_ticker"]

    # 2. Rotation backtester (test window)
    bt = RotationBacktester(config=bt_cfg)
    strategy_result = bt.run(sliced)

    # 3. Aggregate B1 (equal-weight buy-and-hold, test window)
    b1_result = compute_aggregate_b1(
        universe_data,
        test_start=split.test_start,
        test_end=split.test_end,
        universe=effective_universe,
    )

    # 4. B2 — monthly-rebalanced equal-weight universe (test window)
    test_start_ts = pd.Timestamp(split.test_start)
    test_end_ts = pd.Timestamp(split.test_end)
    b2_universe_data: dict[str, pd.DataFrame] = {}
    for ticker in effective_universe:
        if ticker not in universe_data:
            continue
        df = universe_data[ticker]
        mask = (df.index >= test_start_ts) & (df.index <= test_end_ts)
        sliced_df = df.loc[mask]
        if not sliced_df.empty:
            b2_universe_data[ticker] = sliced_df

    b2_result = calculate_equal_weight_universe_benchmark(
        b2_universe_data,
        universe=effective_universe,
        start_date=split.test_start,
        end_date=split.test_end,
    )

    # 5. p95 randomized-selection comparator (test window)
    # Use the first available ticker's index to derive rebalance dates
    _first_series = next(iter(sliced_returns.values()))
    rebalance_dates = bt.select_rebalance_dates(_first_series.index)
    eligible_by_date = extract_eligible_by_date(sliced_fm, rebalance_dates)

    # Build strategy holdings_by_date (keyed by rebalance dates only)
    strategy_holdings_by_rebalance: dict[pd.Timestamp, list[str]] = {}
    for evt in strategy_result.rebalance_events:
        strategy_holdings_by_rebalance[pd.Timestamp(evt["date"])] = list(
            evt["holdings_after"]
        )

    p95_result = calculate_randomized_selection_p95(
        rebalance_dates=rebalance_dates,
        eligible_by_date=eligible_by_date,
        returns_by_ticker=sliced_returns,
        strategy_holdings_by_date=strategy_holdings_by_rebalance,
        config=p95_cfg,
    )

    # 6. v1.2 summary row
    run_metadata = {
        "symbol": "RelativeStrengthRotation_v1",
        "params": (
            f"top_n=3,weights=0.40/0.40/0.20,hysteresis=0.50,"
            f"split={split.split_id},"
            f"train={pd.Timestamp(split.train_start).date()}/{pd.Timestamp(split.train_end).date()},"
            f"test={pd.Timestamp(split.test_start).date()}/{pd.Timestamp(split.test_end).date()}"
        ),
        "test_window": (
            f"{pd.Timestamp(split.test_start).date()}/"
            f"{pd.Timestamp(split.test_end).date()}"
        ),
        "strategy_exposure_pct": strategy_result.exposure_pct,
        "split_id": split.split_id,
        "split_spec_version": SPLIT_SPEC_VERSION,
        "split_spec_authorized_research": False,
        "split_spec_train_years": TRAIN_YEARS,
        "split_spec_test_years": TEST_YEARS,
        "split_spec_step_years": STEP_YEARS,
        "research_authorized": False,
        "v1_2_diagnostic_label": "PORTFOLIO_DIAGNOSTIC_ONLY",
    }

    run_inputs = [
        {
            "run_metadata": run_metadata,
            "strategy_result": strategy_result,
            "b1_result": b1_result,
            "b2_result": b2_result,
            "random_result": p95_result,
        }
    ]

    rows = build_rotation_toy_report_rows(run_inputs)
    summary_row = rows[0] if rows else {}

    diagnostics = {
        "split_id": split.split_id,
        "mode": "ORCHESTRATOR_WALK_FORWARD_ROTATION",
        "research_authorized": False,
        "market_data_used": True,
        "strategy_lab_runner_used": False,
        "live_go_emitted": False,
        "research_go_emitted": False,
        "test_rows_in_feature_matrix": len(sliced_fm),
        "n_rebalance_dates": len(rebalance_dates),
        "n_eligible_total": sum(len(v) for v in eligible_by_date.values()),
    }

    return OrchestratorSplitResult(
        split=split,
        strategy_result=strategy_result,
        b1_result=b1_result,
        b2_result=b2_result,
        p95_result=p95_result,
        summary_row=summary_row,
        diagnostics=diagnostics,
    )


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def run_full_pipeline(
    config: Optional[OrchestratorConfig] = None,
) -> OrchestratorRunResult:
    """
    Run the full walk-forward research pipeline for RelativeStrengthRotation_v1.

    Steps:
      1. Load all 15 ticker CSVs from config.data_dir.
      2. Build the full feature matrix (2015-2024) with cross-sectional ranks.
      3. Build daily returns per ticker.
      4. Generate 7 walk-forward splits per the frozen spec.
      5. For each split: run backtester + B1 + B2 + p95 + v1.2 row.
      6. Write the CSV report to config.output_dir.

    Returns OrchestratorRunResult with split_results and report_path.

    IMPORTANT: This function does NOT constitute an authorized research run.
    Every output row is marked research_authorized=False. A separate gate
    (RDR-002 + explicit orchestrator authorization) is required before any
    output is treated as research evidence.
    """
    cfg = config or OrchestratorConfig()

    # 1. Load data
    universe_data = load_universe_csvs(
        data_dir=cfg.data_dir,
        universe=cfg.universe,
        start_date=cfg.window_start,
        end_date=cfg.window_end,
    )

    # 2. Build full feature matrix (train+test combined for warmup)
    raw_fm = build_rotation_feature_matrix(universe_data)
    feature_matrix = add_cross_sectional_ranks(raw_fm)

    # 3. Build returns per ticker
    returns_by_ticker = build_returns_by_ticker(universe_data)

    # 4. Generate splits
    splits = generate_walk_forward_splits(
        window_start=cfg.window_start,
        window_end=cfg.window_end,
        train_years=cfg.train_years,
        test_years=cfg.test_years,
        step_years=cfg.step_years,
    )

    backtester_config = RotationBacktesterConfig()
    p95_config = RandomSelectionComparatorConfig(
        n_simulations=cfg.n_random_simulations,
        random_seed=cfg.random_seed,
    )

    # 5. Run each split
    split_results: list[OrchestratorSplitResult] = []
    for split in splits:
        result = run_single_split(
            split=split,
            universe_data=universe_data,
            feature_matrix=feature_matrix,
            returns_by_ticker=returns_by_ticker,
            backtester_config=backtester_config,
            p95_config=p95_config,
            universe=cfg.universe,
        )
        split_results.append(result)

    # 6. Write CSV report
    output_dir = Path(cfg.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / cfg.report_filename

    all_rows = [sr.summary_row for sr in split_results if sr.summary_row]
    written_path: Optional[Path] = None
    if all_rows:
        written_path = write_rotation_v1_2_toy_csv_report(all_rows, report_path)

    run_diagnostics = {
        "mode": "ORCHESTRATOR_FULL_PIPELINE",
        "research_authorized": False,
        "split_spec_version": SPLIT_SPEC_VERSION,
        "split_spec_authorized_research": False,
        "split_spec_train_years": TRAIN_YEARS,
        "split_spec_test_years": TEST_YEARS,
        "split_spec_step_years": STEP_YEARS,
        "n_splits": len(split_results),
        "live_go_emitted": False,
        "research_go_emitted": False,
        "strategy_lab_runner_used": False,
        "v1_1_verdict_impact": "NONE",
    }

    return OrchestratorRunResult(
        split_results=split_results,
        report_path=written_path,
        diagnostics=run_diagnostics,
    )


__all__ = [
    "FROZEN_UNIVERSE",
    "SPLIT_SPEC_VERSION",
    "OrchestratorConfig",
    "OrchestratorSplitResult",
    "OrchestratorRunResult",
    "load_universe_csvs",
    "generate_walk_forward_splits",
    "build_returns_by_ticker",
    "extract_eligible_by_date",
    "compute_aggregate_b1",
    "run_single_split",
    "run_full_pipeline",
]
