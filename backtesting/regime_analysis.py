"""
Regime Analysis Engine v1

Diagnostic only. No parameter optimization. No strategy changes.
Analyzes per-calendar-year performance of strategy vs benchmark
to understand WHERE and WHY calmar criterion fails.
"""

from typing import Union

import numpy as np
import pandas as pd


class RegimeAnalysisEngine:
    """
    Groups equity curve and trades by calendar year.
    Computes per-year metrics and emits diagnostic warnings.

    Warnings emitted:
      NO_TRADES               — year with zero trades entered
      UNDEREXPOSED_IN_BULL_YEAR — benchmark positive, exposure < threshold
      CALMAR_BELOW_BENCHMARK  — strategy calmar < benchmark calmar for the year
    """

    def __init__(self, underexposed_threshold_pct: float = 20.0) -> None:
        self.underexposed_threshold_pct = underexposed_threshold_pct

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_by_year(
        self,
        equity_curve: Union[list, pd.DataFrame, pd.Series],
        benchmark_equity_curve: Union[list, pd.DataFrame, pd.Series],
        trades: list[dict],
    ) -> dict:
        """
        Parameters
        ----------
        equity_curve : pd.Series (DatetimeIndex → equity value), OR
                       list[dict] with keys "date", "value", OR
                       pd.DataFrame with "date" and "value" columns
        benchmark_equity_curve : same shape as equity_curve
        trades : list of trade dicts; each must have:
                 entry_time (pd.Timestamp or date-like),
                 exit_time  (pd.Timestamp or date-like),
                 pnl        (float)

        Returns
        -------
        dict with keys:
          "years"        : {year_int: {per-year metrics + "warnings": list[str]}}
          "all_warnings" : list[str]  (flat list of every warning, all years)
        """
        strat = self._to_series(equity_curve)
        bench = self._to_series(benchmark_equity_curve)

        position_dates = self._build_position_dates(trades)

        all_years = sorted(
            set(strat.index.year.tolist()) | set(bench.index.year.tolist())
        )

        year_results: dict = {}
        all_warnings: list[str] = []

        for year in all_years:
            strat_yr = strat[strat.index.year == year]
            bench_yr = bench[bench.index.year == year]
            year_trades = [t for t in trades if self._entry_year(t) == year]

            s_ret = self._compute_return(strat_yr)
            s_mdd = self._compute_max_drawdown(strat_yr)
            s_calmar = self._compute_calmar(s_ret, s_mdd)

            b_ret = self._compute_return(bench_yr)
            b_mdd = self._compute_max_drawdown(bench_yr)
            b_calmar = self._compute_calmar(b_ret, b_mdd)

            trade_count = len(year_trades)
            wins = [t for t in year_trades if t["pnl"] > 0]
            losses = [t for t in year_trades if t["pnl"] <= 0]
            win_count = len(wins)
            loss_count = len(losses)
            win_rate = win_count / trade_count * 100 if trade_count > 0 else 0.0
            total_pnl = sum(t["pnl"] for t in year_trades)
            avg_pnl = total_pnl / trade_count if trade_count > 0 else 0.0

            year_trading_days = set(strat_yr.index.normalize())
            in_position = len(year_trading_days & position_dates)
            exposure_pct = (
                in_position / len(year_trading_days) * 100
                if year_trading_days
                else 0.0
            )

            year_warnings: list[str] = []

            if trade_count == 0:
                w = f"NO_TRADES: {year}"
                year_warnings.append(w)
                all_warnings.append(w)

            if b_ret > 0 and exposure_pct < self.underexposed_threshold_pct:
                w = (
                    f"UNDEREXPOSED_IN_BULL_YEAR: {year} "
                    f"(exposure={exposure_pct:.1f}%, benchmark_return={b_ret:.1f}%)"
                )
                year_warnings.append(w)
                all_warnings.append(w)

            if s_calmar < b_calmar:
                w = (
                    f"CALMAR_BELOW_BENCHMARK: "
                    f"strategy={s_calmar:.3f} < benchmark={b_calmar:.3f} in {year}"
                )
                year_warnings.append(w)
                all_warnings.append(w)

            year_results[year] = {
                "strategy_return_pct": round(s_ret, 2),
                "benchmark_return_pct": round(b_ret, 2),
                "strategy_max_drawdown_pct": round(s_mdd * 100, 2),
                "benchmark_max_drawdown_pct": round(b_mdd * 100, 2),
                "strategy_calmar": round(s_calmar, 3),
                "benchmark_calmar": round(b_calmar, 3),
                "trade_count": trade_count,
                "win_count": win_count,
                "loss_count": loss_count,
                "win_rate_pct": round(win_rate, 1),
                "total_pnl": round(total_pnl, 2),
                "avg_pnl": round(avg_pnl, 2),
                "exposure_pct": round(exposure_pct, 1),
                "warnings": year_warnings,
            }

        return {"years": year_results, "all_warnings": all_warnings}

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------

    def _to_series(self, curve) -> pd.Series:
        if isinstance(curve, pd.Series):
            return curve
        if isinstance(curve, pd.DataFrame):
            if "value" not in curve.columns:
                raise ValueError("DataFrame equity_curve must have a 'value' column")
            date_col = "date" if "date" in curve.columns else curve.columns[0]
            return pd.Series(
                curve["value"].values,
                index=pd.to_datetime(curve[date_col]),
            )
        if isinstance(curve, list):
            if not curve:
                return pd.Series(dtype=float)
            if not isinstance(curve[0], dict):
                raise ValueError("list equity_curve must contain dicts with 'date' and 'value'")
            dates = pd.to_datetime([d["date"] for d in curve])
            values = [d["value"] for d in curve]
            return pd.Series(values, index=dates)
        raise TypeError(f"Unsupported equity_curve type: {type(curve)}")

    # ------------------------------------------------------------------
    # Position-exposure helpers
    # ------------------------------------------------------------------

    def _build_position_dates(self, trades: list[dict]) -> set:
        position_dates: set = set()
        for trade in trades:
            entry = pd.Timestamp(trade["entry_time"]).normalize()
            exit_ = pd.Timestamp(trade["exit_time"]).normalize()
            for ts in pd.date_range(entry, exit_, freq="D"):
                position_dates.add(ts)
        return position_dates

    @staticmethod
    def _entry_year(trade: dict) -> int:
        return pd.Timestamp(trade["entry_time"]).year

    # ------------------------------------------------------------------
    # Metric helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_return(series: pd.Series) -> float:
        if len(series) < 2:
            return 0.0
        start, end = float(series.iloc[0]), float(series.iloc[-1])
        if start <= 0:
            return 0.0
        return (end / start - 1) * 100

    @staticmethod
    def _compute_max_drawdown(series: pd.Series) -> float:
        if len(series) < 2:
            return 0.0
        arr = np.array(series.values, dtype=float)
        peak = np.maximum.accumulate(arr)
        with np.errstate(divide="ignore", invalid="ignore"):
            dd = np.where(peak > 0, (peak - arr) / peak, 0.0)
        return float(dd.max())

    @staticmethod
    def _compute_calmar(return_pct: float, max_drawdown: float) -> float:
        annual_return = return_pct / 100.0
        if max_drawdown <= 0:
            return float("inf") if annual_return > 0 else 0.0
        return annual_return / max_drawdown
