"""
B1 raw buy-and-hold benchmark for RelativeStrengthRotation_v1.

B1 is the PRIMARY v1.1 benchmark per the spec: a fully-invested, no-rebalance
buy-and-hold equity curve per ticker. The strategy must beat B1 (raw buy &
hold) on the spec's headline criteria.

This module:
  - Never fetches market data.
  - Never imports market-data libraries.
  - Never imports the timing-strategy lab runner.
  - Never aggregates into the equal-weight B2 benchmark.
  - Never emits live or research verdict tokens.
  - Never replaces B2 (B2 is a separate, report-only diagnostic).

Inputs are price-only (close prices). No forward-fill, back-fill, or
interpolation is performed. Invalid data raises ValueError.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional, Union

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Config / Result
# ---------------------------------------------------------------------------

@dataclass
class B1BuyHoldBenchmarkConfig:
    initial_value: float = 1.0
    annualization_days: int = 252
    benchmark_label: str = "B1_RAW_BUY_HOLD_PRIMARY_V1_1"
    report_only: bool = False


@dataclass
class B1BuyHoldBenchmarkResult:
    equity_curve: pd.Series
    daily_returns: pd.Series
    total_return: float
    max_drawdown: float
    calmar: float
    diagnostics: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_b1_price_data(price_data: Any) -> None:
    """
    Validate price input. Accepts pd.Series of close prices, or pd.DataFrame
    with a 'close' column. Raises ValueError on any structural problem.

    Rejects:
      - None / empty input
      - DataFrame without a 'close' column
      - Non-numeric close
      - NaN close
      - Inf close
      - Zero or negative close
    Does NOT fill, forward-fill, back-fill, or interpolate missing data.
    """
    if price_data is None:
        raise ValueError("price_data must not be None.")

    if isinstance(price_data, pd.DataFrame):
        if price_data.empty:
            raise ValueError("price_data DataFrame is empty.")
        if "close" not in price_data.columns:
            raise ValueError("price_data DataFrame must contain a 'close' column.")
        close = price_data["close"]
    elif isinstance(price_data, pd.Series):
        if price_data.empty:
            raise ValueError("price_data Series is empty.")
        close = price_data
    else:
        raise ValueError(
            f"price_data must be a pd.Series or pd.DataFrame, got "
            f"{type(price_data).__name__!r}."
        )

    numeric = pd.to_numeric(close, errors="coerce")
    if numeric.isna().any():
        raise ValueError("price_data close contains NaN or non-numeric values.")
    arr = numeric.to_numpy(dtype="float64")
    if not np.isfinite(arr).all():
        raise ValueError("price_data close contains inf values.")
    if (arr <= 0.0).any():
        raise ValueError("price_data close contains non-positive values.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_close(price_data: Union[pd.Series, pd.DataFrame]) -> pd.Series:
    if isinstance(price_data, pd.DataFrame):
        s = price_data["close"]
    else:
        s = price_data
    return s.copy()


def _apply_window(
    close: pd.Series,
    start_date: Optional[Any],
    end_date: Optional[Any],
) -> pd.Series:
    if start_date is None and end_date is None:
        return close
    idx = pd.DatetimeIndex(close.index)
    mask = np.ones(len(idx), dtype=bool)
    if start_date is not None:
        mask &= idx >= pd.Timestamp(start_date)
    if end_date is not None:
        mask &= idx <= pd.Timestamp(end_date)
    return close.loc[mask]


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    eq = equity.to_numpy(dtype="float64")
    peak = np.maximum.accumulate(eq)
    with np.errstate(divide="ignore", invalid="ignore"):
        dd = np.where(peak > 0, (peak - eq) / peak, 0.0)
    return float(np.max(dd))


def _calmar(total_return: float, mdd: float, n_periods: int, annualization_days: int) -> float:
    if annualization_days <= 0 or n_periods <= 0:
        return float("nan")
    years = n_periods / annualization_days
    if years <= 0:
        return float("nan")
    annualized = (1.0 + total_return) ** (1.0 / years) - 1.0
    if mdd > 0:
        return float(annualized / abs(mdd))
    return float("inf") if annualized > 0 else 0.0


# ---------------------------------------------------------------------------
# Single-ticker B1
# ---------------------------------------------------------------------------

def calculate_b1_buy_hold_benchmark(
    price_data: Union[pd.Series, pd.DataFrame],
    start_date: Optional[Any] = None,
    end_date: Optional[Any] = None,
    config: Optional[B1BuyHoldBenchmarkConfig] = None,
) -> B1BuyHoldBenchmarkResult:
    """
    Compute B1 (raw buy-and-hold) for a single ticker's close-price series.

    - Uses ONLY 'close' (no OHLC trading logic, no rebalancing, no cash sleeve).
    - Fully invested from first selected bar to last.
    - equity_curve.iloc[0] == config.initial_value.
    - Inputs are not mutated.
    - Window applied via [start_date, end_date]; raises if start_date > end_date.
    """
    validate_b1_price_data(price_data)
    cfg = config or B1BuyHoldBenchmarkConfig()

    if start_date is not None and end_date is not None:
        if pd.Timestamp(start_date) > pd.Timestamp(end_date):
            raise ValueError(
                f"start_date ({start_date}) must be <= end_date ({end_date})."
            )

    close = _extract_close(price_data)
    if not isinstance(close.index, pd.DatetimeIndex):
        close.index = pd.to_datetime(close.index)
    close = _apply_window(close, start_date, end_date)
    if close.empty:
        raise ValueError("price_data is empty after applying start/end window.")

    arr = close.to_numpy(dtype="float64")
    first_price = arr[0]
    equity_values = (arr / first_price) * cfg.initial_value
    equity_curve = pd.Series(
        equity_values, index=close.index, name="equity_curve"
    )

    daily_returns = equity_curve.pct_change().fillna(0.0)
    daily_returns.name = "daily_returns"

    total_return = float(equity_values[-1] / cfg.initial_value - 1.0)
    mdd = _max_drawdown(equity_curve)
    calmar = _calmar(total_return, mdd, len(arr), cfg.annualization_days)

    diagnostics = {
        "benchmark_label": cfg.benchmark_label,
        "report_only": False,
        "v1_1_primary_benchmark": True,
        "v1_1_verdict_impact": "PRIMARY_BENCHMARK_INPUT",
        "start_date": str(close.index[0].date()),
        "end_date": str(close.index[-1].date()),
        "data_points": int(len(arr)),
    }

    return B1BuyHoldBenchmarkResult(
        equity_curve=equity_curve,
        daily_returns=daily_returns,
        total_return=total_return,
        max_drawdown=mdd,
        calmar=calmar,
        diagnostics=diagnostics,
    )


# ---------------------------------------------------------------------------
# Universe B1
# ---------------------------------------------------------------------------

def calculate_b1_for_universe(
    universe_data: dict,
    universe: list[str],
    start_date: Optional[Any] = None,
    end_date: Optional[Any] = None,
    config: Optional[B1BuyHoldBenchmarkConfig] = None,
) -> dict:
    """
    Compute B1 per ticker for every ticker in the frozen universe.

    - Every ticker in `universe` must be present in `universe_data`.
    - Returns dict[ticker -> B1BuyHoldBenchmarkResult].
    - Does NOT aggregate the per-ticker results into a portfolio.
    - Does NOT use equal-weight (B2) logic.
    """
    if not isinstance(universe_data, dict) or not universe_data:
        raise ValueError("universe_data must be a non-empty dict.")
    if not isinstance(universe, list) or not universe:
        raise ValueError("universe must be a non-empty list of tickers.")

    missing = [t for t in universe if t not in universe_data]
    if missing:
        raise ValueError(
            f"universe_data is missing tickers required by the frozen universe: "
            f"{sorted(missing)}"
        )

    results: dict[str, B1BuyHoldBenchmarkResult] = {}
    for ticker in universe:
        results[ticker] = calculate_b1_buy_hold_benchmark(
            universe_data[ticker],
            start_date=start_date,
            end_date=end_date,
            config=config,
        )
    return results


__all__ = [
    "B1BuyHoldBenchmarkConfig",
    "B1BuyHoldBenchmarkResult",
    "validate_b1_price_data",
    "calculate_b1_buy_hold_benchmark",
    "calculate_b1_for_universe",
]
