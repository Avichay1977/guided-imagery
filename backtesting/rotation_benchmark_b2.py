"""
Equal-weight universe benchmark B2 for RelativeStrengthRotation_v1.

B2 is a REPORT-ONLY diagnostic benchmark (spec §6 / §15):
  - monthly-rebalanced equal-weight portfolio across the fixed 15-ticker universe
  - same OOS window as the strategy
  - never used to upgrade or downgrade the v1.1 verdict
  - never replaces B1 (raw Buy & Hold per ticker)
  - v1_1_verdict_impact = "NONE"

No market-data-fetch library imported. No Backtester imported.
No live or research verdict tokens emitted anywhere.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Config / Result
# ---------------------------------------------------------------------------

@dataclass
class EqualWeightBenchmarkConfig:
    initial_value: float = 1.0
    rebalance_frequency: str = "monthly"
    require_full_universe: bool = True
    annualization_days: int = 252
    benchmark_label: str = "B2_EQUAL_WEIGHT_UNIVERSE_REPORT_ONLY"


@dataclass
class EqualWeightBenchmarkResult:
    equity_curve: pd.Series
    daily_returns: pd.Series
    weights_by_date: pd.DataFrame
    holdings_by_date: pd.DataFrame
    total_return: float
    max_drawdown: float
    calmar: float
    diagnostics: dict


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_benchmark_universe_data(
    universe_data,
    universe: Optional[list[str]] = None,
) -> None:
    """
    Validate structure of universe_data. Raises ValueError on any problem.

    Checks:
      - non-empty dict
      - every ticker's DataFrame has a finite numeric 'close' column
      - if universe is provided, every ticker in universe must be present
    Does NOT fill, forward-fill, back-fill, or repair missing data in any form.
    """
    if not isinstance(universe_data, dict) or not universe_data:
        raise ValueError("universe_data must be a non-empty dict of ticker -> DataFrame.")

    for ticker, df in universe_data.items():
        if not isinstance(df, pd.DataFrame):
            raise ValueError(f"universe_data[{ticker!r}] must be a DataFrame.")
        if "close" not in df.columns:
            raise ValueError(f"universe_data[{ticker!r}] missing 'close' column.")
        close = pd.to_numeric(df["close"], errors="coerce")
        if close.isna().any():
            raise ValueError(
                f"universe_data[{ticker!r}]['close'] contains NaN or non-numeric values."
            )
        if not np.isfinite(close.to_numpy(dtype="float64")).all():
            raise ValueError(
                f"universe_data[{ticker!r}]['close'] contains inf values."
            )

    if universe is not None:
        missing = [t for t in universe if t not in universe_data]
        if missing:
            raise ValueError(
                f"universe_data is missing required tickers: {missing}"
            )


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def select_monthly_rebalance_dates(dates) -> list[pd.Timestamp]:
    """
    Return the first available trading date of each calendar month.

    Accepts any iterable of date-likes. Output is sorted ascending, one
    Timestamp per (year, month).
    """
    timestamps = sorted(pd.Timestamp(d) for d in dates)
    seen: set[tuple[int, int]] = set()
    result: list[pd.Timestamp] = []
    for ts in timestamps:
        key = (ts.year, ts.month)
        if key not in seen:
            seen.add(key)
            result.append(ts)
    return result


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def calculate_total_return(equity_curve) -> float:
    """(final / initial) - 1.  Returns nan for empty or zero-start curves."""
    vals = list(equity_curve)
    if len(vals) < 2 or vals[0] == 0:
        return float("nan")
    return float(vals[-1]) / float(vals[0]) - 1.0


def calculate_max_drawdown(equity_curve) -> float:
    """Max peak-to-trough drawdown as a positive fraction (0.20 = 20% drawdown).
    Returns 0.0 for empty / single-element curves."""
    vals = np.array(list(equity_curve), dtype="float64")
    if len(vals) < 2:
        return 0.0
    peak = vals[0]
    max_dd = 0.0
    for v in vals:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
    return float(max_dd)


def calculate_calmar(equity_curve, annualization_days: int = 252) -> float:
    """
    Annualized return / max drawdown.

    Returns nan when max_drawdown == 0 (avoids division by zero; a flat curve
    produces no useful Calmar). annualization_days is taken from the curve
    length if no external value is passed.
    """
    vals = np.array(list(equity_curve), dtype="float64")
    n = len(vals)
    if n < 2 or vals[0] == 0:
        return float("nan")
    total_ret = float(vals[-1]) / float(vals[0]) - 1.0
    years = (n - 1) / annualization_days
    if years <= 0:
        return float("nan")
    annualized = (1.0 + total_ret) ** (1.0 / years) - 1.0
    mdd = calculate_max_drawdown(vals)
    if mdd == 0.0:
        return float("nan")
    return annualized / mdd


# ---------------------------------------------------------------------------
# Core benchmark
# ---------------------------------------------------------------------------

def calculate_equal_weight_universe_benchmark(
    universe_data: "dict[str, pd.DataFrame]",
    universe: Optional[list[str]] = None,
    start_date=None,
    end_date=None,
    config: Optional[EqualWeightBenchmarkConfig] = None,
) -> EqualWeightBenchmarkResult:
    """
    Compute the monthly-rebalanced equal-weight universe benchmark (B2).

    B2 is REPORT ONLY and has no effect on v1.1 or v1.2 verdicts.

    Algorithm:
      1. Align all tickers on a common date index (inner join of close series).
      2. Optionally trim to [start_date, end_date].
      3. Identify monthly rebalance dates (first trading day of each month).
      4. At each rebalance date, allocate equal target value per ticker and
         compute shares = target_value / close_at_rebalance_date.
      5. Between rebalances, let shares drift with prices.
      6. Equity at each date = sum(shares_t * close_t).

    No daily rebalancing occurs between monthly rebalance points.
    Input DataFrames are NOT modified.
    No fill of any kind is applied — invalid data raises ValueError.
    """
    cfg = config or EqualWeightBenchmarkConfig()

    validate_benchmark_universe_data(universe_data, universe)

    # Work with the requested subset (or all tickers if universe not given)
    tickers = universe if universe is not None else sorted(universe_data)

    # Build aligned close frame — no fill, no interpolation
    closes: dict[str, pd.Series] = {}
    for t in tickers:
        if t not in universe_data:
            raise ValueError(f"Ticker {t!r} not found in universe_data.")
        closes[t] = universe_data[t]["close"].copy()

    close_frame = pd.DataFrame(closes).sort_index()

    # Apply date window
    if start_date is not None and end_date is not None:
        s = pd.Timestamp(start_date)
        e = pd.Timestamp(end_date)
        if s > e:
            raise ValueError(
                f"start_date ({s}) must not be after end_date ({e})."
            )
        close_frame = close_frame.loc[s:e]
    elif start_date is not None:
        close_frame = close_frame.loc[pd.Timestamp(start_date):]
    elif end_date is not None:
        close_frame = close_frame.loc[:pd.Timestamp(end_date)]

    if close_frame.empty:
        raise ValueError("No data in the requested date window.")

    if close_frame.isna().any(axis=None).any() if hasattr(close_frame.isna().any(axis=None), 'any') else close_frame.isna().any().any():
        raise ValueError("close_frame contains NaN after windowing; cannot compute B2.")

    dates = close_frame.index
    rebalance_dates = set(select_monthly_rebalance_dates(dates))
    n_tickers = len(tickers)
    target_weight = 1.0 / n_tickers

    # Simulate month-by-month drift
    nav = cfg.initial_value
    shares: dict[str, float] = {}  # ticker -> shares held

    equity_vals: list[float] = []
    weights_rows: list[dict] = []
    holdings_rows: list[dict] = []

    for date in dates:
        row_close = close_frame.loc[date]

        if date in rebalance_dates or not shares:
            # Compute current portfolio value before rebalance
            if shares:
                nav = sum(shares[t] * float(row_close[t]) for t in tickers)
            else:
                nav = cfg.initial_value

            # Equal target per ticker
            target_value = nav * target_weight
            shares = {
                t: target_value / float(row_close[t])
                for t in tickers
            }

        # Mark-to-market
        portfolio_value = sum(shares[t] * float(row_close[t]) for t in tickers)
        equity_vals.append(portfolio_value)

        # Record weights (share_value / portfolio_value)
        w_row = {"date": date}
        h_row = {"date": date}
        for t in tickers:
            w_row[t] = shares[t] * float(row_close[t]) / portfolio_value
            h_row[t] = shares[t]
        weights_rows.append(w_row)
        holdings_rows.append(h_row)

    equity_curve = pd.Series(equity_vals, index=dates, name="B2_equity")
    daily_returns = equity_curve.pct_change().fillna(0.0)
    daily_returns.name = "B2_daily_returns"

    weights_df = pd.DataFrame(weights_rows).set_index("date")
    holdings_df = pd.DataFrame(holdings_rows).set_index("date")

    tr = calculate_total_return(equity_curve)
    mdd = calculate_max_drawdown(equity_curve)
    calmar = calculate_calmar(equity_curve, cfg.annualization_days)

    diagnostics = {
        "benchmark_label": cfg.benchmark_label,
        "ticker_count": n_tickers,
        "rebalance_count": len([d for d in dates if d in rebalance_dates]),
        "start_date": str(dates[0].date()),
        "end_date": str(dates[-1].date()),
        "report_only": True,
        "v1_1_verdict_impact": "NONE",
    }

    return EqualWeightBenchmarkResult(
        equity_curve=equity_curve,
        daily_returns=daily_returns,
        weights_by_date=weights_df,
        holdings_by_date=holdings_df,
        total_return=tr,
        max_drawdown=mdd,
        calmar=calmar,
        diagnostics=diagnostics,
    )
