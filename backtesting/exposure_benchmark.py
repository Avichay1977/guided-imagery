"""
Exposure-Matched Benchmark Engine v1

Diagnostic only. Compares strategy against a benchmark invested at the same
market-exposure fraction as the strategy, not at 100% buy-and-hold.

This supplements — never replaces — the buy-and-hold benchmark.

No leverage. No interest on cash. MVP diagnostic only.
"""

import numpy as np
import pandas as pd


def compute_exposure_pct(trades: list[dict], df: pd.DataFrame) -> float:
    """
    Return the percentage of trading days where a position was open.

    Counts calendar days between each trade's entry and exit, then intersects
    with the actual trading days in df (DatetimeIndex).
    """
    if not trades or df.empty:
        return 0.0

    position_dates: set = set()
    for trade in trades:
        entry = pd.Timestamp(trade["entry_time"]).normalize()
        exit_ = pd.Timestamp(trade["exit_time"]).normalize()
        for ts in pd.date_range(entry, exit_, freq="D"):
            position_dates.add(ts)

    trading_days = set(df.index.normalize())
    in_position = len(trading_days & position_dates)
    return in_position / len(trading_days) * 100 if trading_days else 0.0


class ExposureMatchedBenchmarkEngine:
    """
    Simulates a benchmark that is only invested in the underlying asset for
    the fraction of time equal to the strategy's actual market exposure.

    Formula
    -------
    exposure_fraction = exposure_time_pct / 100
    daily_returns     = benchmark_close.pct_change().fillna(0) * exposure_fraction
    equity            = initial_cash * (1 + daily_returns).cumprod()
    """

    def calculate(
        self,
        strategy_equity_curve,        # list | pd.Series — accepted, not used in formula
        benchmark_close: pd.Series,
        initial_cash: float,
        exposure_time_pct: float,
    ) -> dict:
        """
        Returns
        -------
        dict with keys:
          exposure_fraction
          exposure_matched_total_return_pct
          exposure_matched_cagr_pct
          exposure_matched_max_drawdown_pct
          exposure_matched_sharpe
          exposure_matched_calmar
          exposure_matched_equity_curve   (list[float])
          exposure_matched_drawdown_curve (list[float])
        """
        exposure_fraction = float(exposure_time_pct) / 100.0

        bm_returns = benchmark_close.pct_change().fillna(0.0)
        em_returns = bm_returns * exposure_fraction
        equity = initial_cash * (1.0 + em_returns).cumprod()

        eq = equity.values.astype(float)

        # Total return
        total_return_pct = (eq[-1] / initial_cash - 1.0) * 100.0 if initial_cash > 0 else 0.0

        # CAGR (annualised)
        n_bars = len(eq) - 1
        duration_years = n_bars / 252.0 if n_bars > 0 else 1.0
        cagr = (
            (eq[-1] / initial_cash) ** (1.0 / duration_years) - 1.0
            if initial_cash > 0 and duration_years > 0
            else 0.0
        )
        cagr_pct = cagr * 100.0

        # Max drawdown
        peak = np.maximum.accumulate(eq)
        with np.errstate(divide="ignore", invalid="ignore"):
            dd = np.where(peak > 0, (peak - eq) / peak, 0.0)
        max_dd = float(dd.max())
        max_dd_pct = max_dd * 100.0

        # Sharpe (annualised, rf = 0)
        if len(eq) > 1:
            ret_arr = np.diff(eq) / eq[:-1]
            ret_arr = ret_arr[np.isfinite(ret_arr)]
            sharpe = (
                float(ret_arr.mean() / ret_arr.std() * np.sqrt(252))
                if ret_arr.std() > 0
                else 0.0
            )
        else:
            sharpe = 0.0

        # Calmar
        if max_dd > 0:
            calmar = cagr / max_dd
        elif cagr > 0:
            calmar = float("inf")
        else:
            calmar = 0.0

        return {
            "exposure_fraction": round(exposure_fraction, 4),
            "exposure_matched_total_return_pct": round(total_return_pct, 2),
            "exposure_matched_cagr_pct": round(cagr_pct, 2),
            "exposure_matched_max_drawdown_pct": round(max_dd_pct, 2),
            "exposure_matched_sharpe": round(sharpe, 3),
            "exposure_matched_calmar": round(calmar, 3) if calmar != float("inf") else float("inf"),
            "exposure_matched_equity_curve": equity.tolist(),
            "exposure_matched_drawdown_curve": dd.tolist(),
        }
