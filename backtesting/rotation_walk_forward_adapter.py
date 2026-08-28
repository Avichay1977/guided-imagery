"""
Rotation walk-forward adapter — toy / precomputed integration only.

Drives RotationBacktester.run() over a list of train/test splits using
PRECOMPUTED feature matrices and return series. Per-split, only the
test-window rows are passed to the backtester (the train window is never
consulted at decision time).

This module:
  - Never fetches market data.
  - Never computes OHLCV features.
  - Never calls strategy_lab_runner.
  - Never runs a real research backtest.
  - Never modifies Protocol v1.1 / v1.2 gates.
  - Never emits live or research verdict tokens.
  - Never overwrites a v1.1 NO-GO verdict.

Mode marker (diagnostics): TOY_WALK_FORWARD_ROTATION_ADAPTER
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from rotation_backtester import (
    RotationBacktester,
    RotationBacktesterConfig,
    RotationBacktesterResult,
    _REQUIRED_FEATURE_COLS,
)
from rotation_v1_2_metric_adapter import build_rotation_summary_row_with_v1_2_metrics


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RotationWalkForwardSplit:
    split_id: str
    train_start: Any
    train_end: Any
    test_start: Any
    test_end: Any


@dataclass
class RotationWalkForwardSplitResult:
    split_id: str
    train_start: Any
    train_end: Any
    test_start: Any
    test_end: Any
    rotation_result: RotationBacktesterResult
    summary_row: dict
    diagnostics: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Toy diagnostics
# ---------------------------------------------------------------------------

_TOY_WALK_FORWARD_DIAGNOSTICS: dict[str, Any] = {
    "mode": "TOY_WALK_FORWARD_ROTATION_ADAPTER",
    "research_valid": False,
    "market_data_used": False,
    "strategy_lab_runner_used": False,
    "live_go_emitted": False,
    "research_go_emitted": False,
    "v1_1_verdict_impact": "NONE",
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_rotation_walk_forward_inputs(
    feature_matrix,
    returns_by_ticker,
    splits,
) -> bool:
    """
    Validate walk-forward inputs structurally. Raises ValueError on any issue.

    Checks:
      - feature_matrix is non-empty DataFrame with required rotation columns
      - returns_by_ticker is non-empty dict[str, pd.Series]
      - splits is non-empty list of RotationWalkForwardSplit
      - every split has train_end < test_start (no leakage)
      - every split's test window overlaps the feature_matrix date range
    """
    if not isinstance(feature_matrix, pd.DataFrame) or feature_matrix.empty:
        raise ValueError("feature_matrix must be a non-empty DataFrame.")

    missing = _REQUIRED_FEATURE_COLS - set(feature_matrix.columns)
    if missing:
        raise ValueError(
            f"feature_matrix missing required columns: {sorted(missing)}"
        )

    if not isinstance(returns_by_ticker, dict) or not returns_by_ticker:
        raise ValueError("returns_by_ticker must be a non-empty dict.")
    for t, s in returns_by_ticker.items():
        if not isinstance(s, pd.Series):
            raise ValueError(f"returns_by_ticker[{t!r}] must be a pd.Series.")

    if not isinstance(splits, list) or not splits:
        raise ValueError("splits must be a non-empty list.")

    fm_dates = pd.to_datetime(feature_matrix["date"])
    fm_min, fm_max = fm_dates.min(), fm_dates.max()

    for i, split in enumerate(splits):
        if not isinstance(split, RotationWalkForwardSplit):
            raise ValueError(
                f"splits[{i}] must be a RotationWalkForwardSplit instance."
            )
        train_end = pd.Timestamp(split.train_end)
        test_start = pd.Timestamp(split.test_start)
        test_end = pd.Timestamp(split.test_end)
        if not (train_end < test_start):
            raise ValueError(
                f"splits[{i}] ({split.split_id!r}): train_end ({train_end}) "
                f"must be strictly before test_start ({test_start})."
            )
        if test_end < test_start:
            raise ValueError(
                f"splits[{i}] ({split.split_id!r}): test_end ({test_end}) "
                f"must be on or after test_start ({test_start})."
            )
        if test_end < fm_min or test_start > fm_max:
            raise ValueError(
                f"splits[{i}] ({split.split_id!r}): test window "
                f"[{test_start}, {test_end}] is outside feature_matrix range "
                f"[{fm_min}, {fm_max}]."
            )

    return True


# ---------------------------------------------------------------------------
# Slicing
# ---------------------------------------------------------------------------

def slice_rotation_inputs_for_test_window(
    feature_matrix,
    returns_by_ticker,
    split: RotationWalkForwardSplit,
) -> dict:
    """
    Return a fresh universe_data dict containing ONLY the test-window rows.

    - feature_matrix is filtered to test_start <= date <= test_end.
    - returns_by_ticker is sliced to the same range; missing returns for
      tickers that appear in the sliced feature_matrix raise ValueError.
    - Train rows are NEVER included in the sliced feature_matrix.
    - Inputs are not mutated; returned slices are copies.
    """
    test_start = pd.Timestamp(split.test_start)
    test_end = pd.Timestamp(split.test_end)

    fm = feature_matrix.copy()
    fm["date"] = pd.to_datetime(fm["date"])
    mask = (fm["date"] >= test_start) & (fm["date"] <= test_end)
    sliced_fm = fm.loc[mask].reset_index(drop=True)

    sliced_returns: dict[str, pd.Series] = {}
    for ticker, series in returns_by_ticker.items():
        idx = pd.DatetimeIndex(series.index)
        win = series.loc[(idx >= test_start) & (idx <= test_end)].copy()
        sliced_returns[ticker] = win

    tickers_in_fm = set(sliced_fm["ticker"].tolist()) if not sliced_fm.empty else set()
    for t in tickers_in_fm:
        if t not in sliced_returns or len(sliced_returns[t]) == 0:
            raise ValueError(
                f"Ticker {t!r} present in feature_matrix test window but "
                f"missing returns for split {split.split_id!r}."
            )

    return {
        "feature_matrix": sliced_fm,
        "returns_by_ticker": sliced_returns,
    }


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------

def run_rotation_walk_forward_toy(
    feature_matrix,
    returns_by_ticker,
    splits,
    strategy=None,
    config: Optional[RotationBacktesterConfig] = None,
) -> list[RotationWalkForwardSplitResult]:
    """
    Run RotationBacktester.run() per split using only the test window.

    Returns a list of RotationWalkForwardSplitResult, one per split, in
    input order. Each split is independent (no state carries over).
    Inputs are not mutated.
    """
    validate_rotation_walk_forward_inputs(feature_matrix, returns_by_ticker, splits)

    backtester = RotationBacktester(config or RotationBacktesterConfig())
    results: list[RotationWalkForwardSplitResult] = []

    for split in splits:
        sliced = slice_rotation_inputs_for_test_window(
            feature_matrix, returns_by_ticker, split
        )
        rot_result = backtester.run(sliced, strategy=strategy)

        # Strategy-level identification for downstream v1.2 adapters
        strategy_name = "RelativeStrengthRotation"
        strategy_version = "v1"
        if strategy is not None:
            strategy_name = getattr(strategy, "strategy_name", strategy_name)
            strategy_version = getattr(strategy, "strategy_version", strategy_version)

        # Wrap RotationBacktesterResult so the v1.2 metric adapter can read
        # canonical attribute names (strategy_total_return, strategy_calmar).
        # The wrapper is a thin view; the underlying result is unchanged.
        wf_strategy_view = _StrategyView(
            strategy_total_return=rot_result.strategy_total_return,
            strategy_calmar=rot_result.strategy_calmar,
        )

        base_row = {
            "split_id": split.split_id,
            "train_start": split.train_start,
            "train_end": split.train_end,
            "test_start": split.test_start,
            "test_end": split.test_end,
            "test_window": f"{split.test_start}–{split.test_end}",
            "strategy_name": strategy_name,
            "strategy_version": strategy_version,
            "protocol_version": "v1.2",
            "status": "TOY_WALK_FORWARD_ONLY",
            "v1_1_verdict_preserved": "V1_1_NO_GO",
            "v1_1_verdict_impact": "NONE",
            "strategy_exposure_pct": rot_result.exposure_pct,
        }

        summary_row = build_rotation_summary_row_with_v1_2_metrics(
            base_row, wf_strategy_view
        )

        diagnostics = dict(_TOY_WALK_FORWARD_DIAGNOSTICS)
        diagnostics["split_id"] = split.split_id

        results.append(
            RotationWalkForwardSplitResult(
                split_id=split.split_id,
                train_start=split.train_start,
                train_end=split.train_end,
                test_start=split.test_start,
                test_end=split.test_end,
                rotation_result=rot_result,
                summary_row=summary_row,
                diagnostics=diagnostics,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Summary-row collection
# ---------------------------------------------------------------------------

def build_rotation_walk_forward_summary_rows(
    split_results: list[RotationWalkForwardSplitResult],
) -> list[dict]:
    """
    Return one summary dict per split, suitable as input to the v1.2 report
    generator and toy CSV writer. Each row is a fresh copy.
    """
    return [dict(sr.summary_row) for sr in split_results]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

@dataclass
class _StrategyView:
    """Thin attribute carrier so the v1.2 metric adapter can read canonical names."""
    strategy_total_return: Optional[float]
    strategy_calmar: Optional[float]


__all__ = [
    "RotationWalkForwardSplit",
    "RotationWalkForwardSplitResult",
    "validate_rotation_walk_forward_inputs",
    "slice_rotation_inputs_for_test_window",
    "run_rotation_walk_forward_toy",
    "build_rotation_walk_forward_summary_rows",
]
