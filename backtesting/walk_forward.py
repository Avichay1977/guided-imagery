"""
Walk-Forward Diagnostic Engine v1

Diagnostic only. Fixed parameters throughout.
The train window provides date context only; no parameters are fitted on train data.
OOS evaluation runs the full backtesting pipeline on the test window.

Pass criterion (RESEARCH-GO): all six aggregate thresholds must be met.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from backtester import Backtester, BacktestConfig
from exposure_benchmark import ExposureMatchedBenchmarkEngine, compute_exposure_pct
from execution import ExecutionSimulator
from metrics import MetricsEngine, MetricsConfig
from portfolio import PortfolioTracker
from randomized_benchmark import RandomizedBenchmarkConfig, RandomizedTimingBenchmarkEngine


@dataclass
class WalkForwardConfig:
    train_years: int = 3
    test_years: int = 1
    step_years: int = 1
    min_test_trades: int = 5
    min_total_oos_trades: int = 50
    min_oos_positive_expectancy_rate: float = 0.60
    min_oos_profit_factor: float = 1.2
    min_oos_random_p75_pass_rate: float = 0.60
    require_oos_calmar_above_benchmark: bool = True
    max_ticker_concentration_pct: float = 25.0


class WalkForwardEngine:
    """
    Runs an expanding (rolling) walk-forward evaluation using fixed strategy
    parameters. The train window is reported for context; no parameter
    optimization is performed.

    RESEARCH-GO requires all six aggregate thresholds to pass.
    """

    def __init__(
        self,
        config: Optional[WalkForwardConfig] = None,
        backtester_config: Optional[BacktestConfig] = None,
        random_config: Optional[RandomizedBenchmarkConfig] = None,
    ) -> None:
        self.config = config or WalkForwardConfig()
        self.backtester_config = backtester_config or BacktestConfig()
        self.random_config = random_config or RandomizedBenchmarkConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_splits(self, start: str, end: str) -> list[dict]:
        """
        Return list of walk-forward date splits.

        Each split dict contains:
            split_id, train_start, train_end, test_start, test_end
        """
        cfg = self.config
        start_dt = pd.Timestamp(start)
        end_dt = pd.Timestamp(end)
        splits: list[dict] = []
        split_id = 0
        current = start_dt

        while True:
            train_start = current
            train_end = current + pd.DateOffset(years=cfg.train_years)
            test_start = train_end
            test_end = test_start + pd.DateOffset(years=cfg.test_years)

            if test_end > end_dt:
                break

            splits.append({
                "split_id": split_id,
                "train_start": train_start.strftime("%Y-%m-%d"),
                "train_end": train_end.strftime("%Y-%m-%d"),
                "test_start": test_start.strftime("%Y-%m-%d"),
                "test_end": test_end.strftime("%Y-%m-%d"),
            })

            split_id += 1
            current = current + pd.DateOffset(years=cfg.step_years)

        return splits

    def evaluate_ticker(
        self,
        df_full: pd.DataFrame,
        ticker: str,
        start: str,
        end: str,
    ) -> list[dict]:
        """
        Run OOS backtest on each walk-forward split for one ticker.

        df_full must have features already generated (FeatureEngine applied to the
        full date range so that test-window features are warmed up by train data).

        Parameters
        ----------
        df_full : full-history DataFrame with shifted features
        ticker  : ticker label for output rows
        start   : overall start date (used for split generation)
        end     : overall end date (used for split generation)

        Returns
        -------
        list of per-split result dicts
        """
        splits = self.generate_splits(start, end)
        return [self._evaluate_split(df_full, ticker, split) for split in splits]

    def aggregate(self, rows: list[dict]) -> dict:
        """
        Compute overall walk-forward verdict from all per-split rows across
        all tickers.

        Only rows with status == 'OK' contribute to the metrics.
        """
        cfg = self.config
        eligible = [r for r in rows if r.get("status") == "OK"]

        if not eligible:
            return {
                "oos_total_trades": 0,
                "oos_positive_expectancy_rate": 0.0,
                "oos_average_profit_factor": 0.0,
                "oos_calmar_above_benchmark_rate": 0.0,
                "oos_randomized_timing_pass_rate": 0.0,
                "oos_max_ticker_concentration_pct": 0.0,
                "n_eligible_splits": 0,
                "research_go": False,
                "verdict": "NO-GO",
                "verdict_failure_reasons": ["NO_ELIGIBLE_SPLITS"],
            }

        total_oos_trades = sum(r.get("test_total_trades", 0) for r in eligible)

        # Positive expectancy rate
        exp_rows = [r for r in eligible if r.get("test_expectancy_per_trade_R") is not None]
        pos_exp_rate = (
            sum(1 for r in exp_rows if float(r["test_expectancy_per_trade_R"]) > 0) / len(exp_rows)
            if exp_rows else 0.0
        )

        # Average profit factor (cap inf at 10.0 to allow averaging)
        pf_rows = [r for r in eligible if r.get("test_profit_factor") is not None]
        pf_vals = []
        for r in pf_rows:
            v = float(r["test_profit_factor"])
            if np.isfinite(v):
                pf_vals.append(v)
            else:
                pf_vals.append(10.0)
        avg_pf = sum(pf_vals) / len(pf_vals) if pf_vals else 0.0

        # Calmar above benchmark rate
        calmar_rows = [
            r for r in eligible
            if r.get("test_calmar") is not None and r.get("test_benchmark_calmar") is not None
        ]
        calmar_rate = (
            sum(
                1 for r in calmar_rows
                if float(r["test_calmar"]) >= float(r["test_benchmark_calmar"])
            ) / len(calmar_rows)
            if calmar_rows else 0.0
        )

        # Randomized timing pass rate
        rand_rate = (
            sum(1 for r in eligible if r.get("randomized_timing_pass", False)) / len(eligible)
            if eligible else 0.0
        )

        # Ticker concentration
        ticker_trades: dict[str, int] = {}
        for r in eligible:
            t = str(r.get("ticker", ""))
            ticker_trades[t] = ticker_trades.get(t, 0) + int(r.get("test_total_trades", 0))

        if total_oos_trades > 0:
            max_ticker_pct = max(ticker_trades.values()) / total_oos_trades * 100.0
            dominant_ticker = max(ticker_trades, key=ticker_trades.get)
        else:
            max_ticker_pct = 0.0
            dominant_ticker = ""

        # Verdict
        verdict_reasons: list[str] = []

        if total_oos_trades < cfg.min_total_oos_trades:
            verdict_reasons.append(
                f"OOS_TRADES_TOO_LOW: {total_oos_trades} < {cfg.min_total_oos_trades}"
            )
        if pos_exp_rate < cfg.min_oos_positive_expectancy_rate:
            verdict_reasons.append(
                f"OOS_POSITIVE_EXPECTANCY_RATE_TOO_LOW: {pos_exp_rate:.2f} < {cfg.min_oos_positive_expectancy_rate}"
            )
        if avg_pf < cfg.min_oos_profit_factor:
            verdict_reasons.append(
                f"OOS_AVG_PROFIT_FACTOR_TOO_LOW: {avg_pf:.3f} < {cfg.min_oos_profit_factor}"
            )
        if cfg.require_oos_calmar_above_benchmark and calmar_rate < 0.60:
            verdict_reasons.append(
                f"OOS_CALMAR_ABOVE_BENCHMARK_RATE_TOO_LOW: {calmar_rate:.2f} < 0.60"
            )
        if rand_rate < cfg.min_oos_random_p75_pass_rate:
            verdict_reasons.append(
                f"OOS_RANDOMIZED_TIMING_PASS_RATE_TOO_LOW: {rand_rate:.2f} < {cfg.min_oos_random_p75_pass_rate}"
            )
        if max_ticker_pct > cfg.max_ticker_concentration_pct:
            verdict_reasons.append(
                f"TICKER_CONCENTRATION: {dominant_ticker}={max_ticker_pct:.1f}% > {cfg.max_ticker_concentration_pct}%"
            )

        return {
            "oos_total_trades": total_oos_trades,
            "oos_positive_expectancy_rate": round(pos_exp_rate, 3),
            "oos_average_profit_factor": round(avg_pf, 3),
            "oos_calmar_above_benchmark_rate": round(calmar_rate, 3),
            "oos_randomized_timing_pass_rate": round(rand_rate, 3),
            "oos_max_ticker_concentration_pct": round(max_ticker_pct, 1),
            "n_eligible_splits": len(eligible),
            "research_go": len(verdict_reasons) == 0,
            "verdict": "RESEARCH-GO" if len(verdict_reasons) == 0 else "NO-GO",
            "verdict_failure_reasons": verdict_reasons,
        }

    # ------------------------------------------------------------------
    # Private: single-split OOS evaluation
    # ------------------------------------------------------------------

    def _evaluate_split(
        self, df_full: pd.DataFrame, ticker: str, split: dict
    ) -> dict:
        cfg = self.config
        bcfg = self.backtester_config

        test_start = pd.Timestamp(split["test_start"])
        test_end = pd.Timestamp(split["test_end"])

        df_test = df_full[
            (df_full.index >= test_start) & (df_full.index < test_end)
        ].copy()

        if len(df_test) < 20:
            return {
                **split,
                "ticker": ticker,
                "test_total_trades": 0,
                "test_expectancy_per_trade_R": None,
                "test_profit_factor": None,
                "test_calmar": None,
                "test_benchmark_calmar": None,
                "test_exposure_matched_calmar": None,
                "test_random_p75_calmar": None,
                "falsifier_pass": False,
                "exposure_matched_pass": None,
                "randomized_timing_pass": False,
                "status": "INSUFFICIENT_TEST_DATA",
                "failure_reasons": "INSUFFICIENT_TEST_DATA",
            }

        portfolio = PortfolioTracker(initial_cash=bcfg.initial_cash)
        execution = ExecutionSimulator(slippage_pct=0.0005, fixed_fee=2.0)
        bt = Backtester(config=bcfg, portfolio=portfolio, execution=execution).run(df_test)

        trades = bt["trades"]
        n_trades = len(trades)

        me = MetricsEngine(MetricsConfig(periods_per_year=252))
        sm = me.calculate_all(bt["equity_curve"], trades)

        if n_trades < cfg.min_test_trades:
            return {
                **split,
                "ticker": ticker,
                "test_total_trades": n_trades,
                "test_expectancy_per_trade_R": round(float(sm.get("expectancy_per_trade_r") or 0.0), 4),
                "test_profit_factor": round(float(sm.get("profit_factor") or 0.0), 3),
                "test_calmar": None,
                "test_benchmark_calmar": None,
                "test_exposure_matched_calmar": None,
                "test_random_p75_calmar": None,
                "falsifier_pass": False,
                "exposure_matched_pass": None,
                "randomized_timing_pass": False,
                "status": "INSUFFICIENT_TEST_TRADES",
                "failure_reasons": f"INSUFFICIENT_TEST_TRADES: {n_trades} < {cfg.min_test_trades}",
            }

        # Benchmark equity on the test window
        closes = df_test["close"].values
        bm_equity = list(bcfg.initial_cash * closes / closes[0])
        bm_metrics = me.calculate_benchmark(bm_equity)

        # Exposure-matched benchmark
        exp_pct = compute_exposure_pct(trades, df_test)
        em_close_s = pd.Series(closes, index=df_test.index)
        em = ExposureMatchedBenchmarkEngine().calculate(
            strategy_equity_curve=bt["equity_curve"],
            benchmark_close=em_close_s,
            initial_cash=bcfg.initial_cash,
            exposure_time_pct=exp_pct,
        )
        em_calmar = em.get("exposure_matched_calmar")
        if em_calmar == float("inf"):
            em_calmar = None

        # Randomized timing benchmark
        rand_result = RandomizedTimingBenchmarkEngine(self.random_config).evaluate(
            df_test, trades, bcfg.initial_cash, sm
        )

        test_calmar = float(sm.get("calmar_ratio") or 0.0)
        bm_calmar = float(bm_metrics.get("calmar_ratio") or 0.0)
        exp_r = sm.get("expectancy_per_trade_r")
        pf = sm.get("profit_factor")

        # Per-split pass assessment
        falsifier_pass = bool(
            (exp_r is not None and float(exp_r) > 0)
            and (pf is not None and float(pf) >= 1.2)
            and (
                not cfg.require_oos_calmar_above_benchmark
                or test_calmar >= bm_calmar
            )
        )

        em_pass: Optional[bool] = None
        if em_calmar is not None:
            em_pass = bool(test_calmar >= float(em_calmar))

        failure_reasons_list: list[str] = []
        if exp_r is None or float(exp_r) <= 0:
            failure_reasons_list.append(
                f"NEGATIVE_EXPECTANCY: {exp_r}"
            )
        if pf is None or float(pf) < 1.2:
            failure_reasons_list.append(
                f"LOW_PROFIT_FACTOR: {pf}"
            )
        if cfg.require_oos_calmar_above_benchmark and test_calmar < bm_calmar:
            failure_reasons_list.append(
                f"CALMAR_BELOW_BENCHMARK: {test_calmar:.3f} < {bm_calmar:.3f}"
            )

        return {
            **split,
            "ticker": ticker,
            "test_total_trades": n_trades,
            "test_expectancy_per_trade_R": round(float(exp_r or 0.0), 4),
            "test_profit_factor": round(float(pf or 0.0), 3),
            "test_calmar": round(test_calmar, 3),
            "test_benchmark_calmar": round(bm_calmar, 3),
            "test_exposure_matched_calmar": (
                round(float(em_calmar), 3) if em_calmar is not None else None
            ),
            "test_random_p75_calmar": rand_result.get("random_p75_calmar"),
            "falsifier_pass": falsifier_pass,
            "exposure_matched_pass": em_pass,
            "randomized_timing_pass": bool(rand_result.get("randomized_timing_pass", False)),
            "status": "OK",
            "failure_reasons": "; ".join(failure_reasons_list),
        }
