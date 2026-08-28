"""
Multi-Ticker Validator v1

Runs the full pipeline (DataLoader → FeatureEngine → Backtester →
MetricsEngine → FalsifierEngine → SignalDiagnostics) across a list of
tickers and applies a portfolio-level research gate.

This is validation only. No parameter optimization. No trading recommendation.
"""

import argparse
import statistics
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable

import pandas as pd

from fetch_yfinance_data import fetch_yfinance_to_csv
from data_loader import DataLoader
from features import FeatureEngine
from backtester import Backtester, BacktestConfig
from portfolio import PortfolioTracker
from execution import ExecutionSimulator
from metrics import MetricsEngine, MetricsConfig
from falsifier import FalsifierEngine, FalsifierConfig
from diagnostics import SignalDiagnostics
from exposure_benchmark import ExposureMatchedBenchmarkEngine, compute_exposure_pct


# ---------------------------------------------------------------------------
# Per-ticker result
# ---------------------------------------------------------------------------

@dataclass
class TickerResult:
    ticker: str = ""
    status: str = "OK"
    error: str = ""
    rows_loaded: int = 0
    rows_after_cleaning: int = 0
    adjusted_ohlc_applied: bool = False
    total_trades: int = 0
    final_equity: float = 0.0
    total_return_pct: float = 0.0
    cagr_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    calmar_ratio: float = 0.0
    profit_factor: float = 0.0
    expectancy_per_trade_R: float = 0.0
    win_rate_pct: float = 0.0
    ambiguous_exits_pct: float = 0.0
    benchmark_cagr_pct: float = 0.0
    benchmark_max_drawdown_pct: float = 0.0
    benchmark_sharpe: float = 0.0
    benchmark_calmar_ratio: float = 0.0
    falsifier_pass: bool = False
    falsifier_failure_reasons: str = ""
    signal_count: int = 0
    rows_reaching_min_score: int = 0
    signal_rate_pct: float = 0.0
    top_bottlenecks: str = ""
    exposure_time_pct: float = 0.0
    exposure_matched_cagr_pct: float = 0.0
    exposure_matched_max_drawdown_pct: float = 0.0
    exposure_matched_calmar: float = 0.0
    strategy_vs_exposure_matched_calmar_delta: float = 0.0


# ---------------------------------------------------------------------------
# Portfolio validator
# ---------------------------------------------------------------------------

class PortfolioValidator:
    """
    Applies 8 research-gate criteria to a list of per-ticker results.
    Verdict is RESEARCH-GO (not LIVE-GO) if all criteria pass.
    """

    def __init__(
        self,
        min_completed: int = 6,
        min_positive_expectancy_pct: float = 60.0,
        min_total_trades: int = 100,
        min_median_trades: float = 10.0,
        min_avg_profit_factor: float = 1.2,
        require_calmar_above_benchmark: bool = True,
        max_single_ticker_trade_pct: float = 40.0,
        max_avg_ambiguous_pct: float = 5.0,
    ) -> None:
        self.min_completed = min_completed
        self.min_positive_expectancy_pct = min_positive_expectancy_pct
        self.min_total_trades = min_total_trades
        self.min_median_trades = min_median_trades
        self.min_avg_profit_factor = min_avg_profit_factor
        self.require_calmar_above_benchmark = require_calmar_above_benchmark
        self.max_single_ticker_trade_pct = max_single_ticker_trade_pct
        self.max_avg_ambiguous_pct = max_avg_ambiguous_pct

    def evaluate(self, results: list) -> dict:
        completed = [r for r in results if r.status == "OK"]
        failed = [r for r in results if r.status != "OK"]
        passing_falsifier = [r for r in completed if r.falsifier_pass]

        n_completed = len(completed)
        total_trades_all = sum(r.total_trades for r in completed)

        failure_reasons: list[str] = []
        checks: dict = {}

        # 1. Minimum completed tickers
        ok1 = n_completed >= self.min_completed
        checks["min_completed_tickers"] = {"pass": ok1, "value": n_completed, "required": self.min_completed}
        if not ok1:
            failure_reasons.append(f"INSUFFICIENT_COMPLETED: {n_completed} < {self.min_completed}")

        # 2. ≥60% of completed have positive expectancy
        pos_exp = sum(1 for r in completed if r.expectancy_per_trade_R > 0)
        pos_exp_pct = pos_exp / n_completed * 100 if n_completed else 0.0
        ok2 = pos_exp_pct >= self.min_positive_expectancy_pct
        checks["positive_expectancy_rate"] = {"pass": ok2, "value_pct": round(pos_exp_pct, 1), "required_pct": self.min_positive_expectancy_pct}
        if not ok2:
            failure_reasons.append(f"LOW_POSITIVE_EXPECTANCY_RATE: {pos_exp_pct:.1f}% < {self.min_positive_expectancy_pct}%")

        # 3. Total trades ≥ min_total_trades
        ok3 = total_trades_all >= self.min_total_trades
        checks["total_trades"] = {"pass": ok3, "value": total_trades_all, "required": self.min_total_trades}
        if not ok3:
            failure_reasons.append(f"INSUFFICIENT_TOTAL_TRADES: {total_trades_all} < {self.min_total_trades}")

        # 4. Median trades per ticker ≥ min_median_trades
        trade_counts = [r.total_trades for r in completed]
        med_trades = statistics.median(trade_counts) if trade_counts else 0.0
        ok4 = med_trades >= self.min_median_trades
        checks["median_trades_per_ticker"] = {"pass": ok4, "value": med_trades, "required": self.min_median_trades}
        if not ok4:
            failure_reasons.append(f"LOW_MEDIAN_TRADES: {med_trades} < {self.min_median_trades}")

        # 5. Average profit_factor ≥ min_avg_profit_factor
        pfs = [r.profit_factor for r in completed if r.total_trades > 0 and r.profit_factor != float("inf")]
        avg_pf = statistics.mean(pfs) if pfs else 0.0
        ok5 = avg_pf >= self.min_avg_profit_factor
        checks["avg_profit_factor"] = {"pass": ok5, "value": round(avg_pf, 3), "required": self.min_avg_profit_factor}
        if not ok5:
            failure_reasons.append(f"LOW_AVG_PROFIT_FACTOR: {avg_pf:.3f} < {self.min_avg_profit_factor}")

        # 6. Average strategy calmar ≥ average benchmark calmar
        s_calmars = [r.calmar_ratio for r in completed if r.total_trades > 0 and r.calmar_ratio != float("inf")]
        b_calmars = [r.benchmark_calmar_ratio for r in completed if r.benchmark_calmar_ratio != float("inf")]
        avg_s_calmar = statistics.mean(s_calmars) if s_calmars else 0.0
        avg_b_calmar = statistics.mean(b_calmars) if b_calmars else 0.0
        ok6 = not self.require_calmar_above_benchmark or avg_s_calmar >= avg_b_calmar
        checks["avg_calmar_vs_benchmark"] = {"pass": ok6, "strategy": round(avg_s_calmar, 3), "benchmark": round(avg_b_calmar, 3)}
        if not ok6:
            failure_reasons.append(f"CALMAR_BELOW_BENCHMARK: strategy={avg_s_calmar:.3f} < benchmark={avg_b_calmar:.3f}")

        # 7. No single ticker > max_single_ticker_trade_pct of total trades
        if total_trades_all > 0:
            max_conc = max(r.total_trades / total_trades_all * 100 for r in completed)
        else:
            max_conc = 0.0
        ok7 = total_trades_all == 0 or max_conc <= self.max_single_ticker_trade_pct
        checks["trade_concentration"] = {"pass": ok7, "max_single_pct": round(max_conc, 1), "allowed_pct": self.max_single_ticker_trade_pct}
        if not ok7:
            failure_reasons.append(f"TRADE_CONCENTRATION: {max_conc:.1f}% from one ticker > {self.max_single_ticker_trade_pct}%")

        # 8. Average ambiguous exits < max_avg_ambiguous_pct
        amb_pcts = [r.ambiguous_exits_pct for r in completed]
        avg_amb = statistics.mean(amb_pcts) if amb_pcts else 0.0
        ok8 = avg_amb < self.max_avg_ambiguous_pct
        checks["avg_ambiguous_exits"] = {"pass": ok8, "value_pct": round(avg_amb, 2), "max_pct": self.max_avg_ambiguous_pct}
        if not ok8:
            failure_reasons.append(f"TOO_MANY_AMBIGUOUS_EXITS: avg={avg_amb:.1f}% >= {self.max_avg_ambiguous_pct}%")

        overall_pass = len(failure_reasons) == 0

        # Extra aggregate stats
        exp_rs = [r.expectancy_per_trade_R for r in completed if r.total_trades > 0]

        # Exposure-matched aggregate stats
        exp_pcts = [r.exposure_time_pct for r in completed]
        avg_exposure_pct = statistics.mean(exp_pcts) if exp_pcts else 0.0
        em_calmars = [
            r.exposure_matched_calmar for r in completed
            if r.total_trades > 0 and r.exposure_matched_calmar != float("inf")
        ]
        avg_em_calmar = statistics.mean(em_calmars) if em_calmars else 0.0
        em_deltas = [r.strategy_vs_exposure_matched_calmar_delta for r in completed if r.total_trades > 0]
        avg_em_delta = statistics.mean(em_deltas) if em_deltas else 0.0
        tickers_beating_em = sum(
            1 for r in completed if r.total_trades > 0 and r.strategy_vs_exposure_matched_calmar_delta >= 0
        )

        return {
            "overall_verdict": "RESEARCH-GO" if overall_pass else "NO-GO",
            "overall_pass": overall_pass,
            "failure_reasons": failure_reasons,
            "checks": checks,
            "tickers_requested": len(results),
            "tickers_completed": n_completed,
            "tickers_failed": len(failed),
            "tickers_passing_falsifier": len(passing_falsifier),
            "pass_rate_pct": round(len(passing_falsifier) / n_completed * 100, 1) if n_completed else 0.0,
            "total_trades_all_tickers": total_trades_all,
            "median_trades_per_ticker": med_trades,
            "average_expectancy_R": round(statistics.mean(exp_rs), 3) if exp_rs else 0.0,
            "median_expectancy_R": round(statistics.median(exp_rs), 3) if exp_rs else 0.0,
            "average_profit_factor": round(avg_pf, 3),
            "median_profit_factor": round(statistics.median(pfs), 3) if pfs else 0.0,
            "average_calmar": round(avg_s_calmar, 3),
            "average_benchmark_calmar": round(avg_b_calmar, 3),
            "tickers_with_insufficient_trades": sum(1 for r in completed if r.total_trades < 30),
            "tickers_with_positive_expectancy": pos_exp,
            "tickers_with_calmar_above_benchmark": sum(1 for r in completed if r.calmar_ratio >= r.benchmark_calmar_ratio),
            "average_exposure_time_pct": round(avg_exposure_pct, 1),
            "average_exposure_matched_calmar": round(avg_em_calmar, 3),
            "average_strategy_vs_em_calmar_delta": round(avg_em_delta, 3),
            "tickers_beating_exposure_matched_calmar": tickers_beating_em,
        }


# ---------------------------------------------------------------------------
# Per-ticker runner
# ---------------------------------------------------------------------------

class MultiTickerRunner:
    """
    Runs the full backtest pipeline for each ticker independently.

    Parameters
    ----------
    config : BacktestConfig to use for every ticker (defaults to production defaults).
    fetch_fn : Optional callable(ticker, start, end, output_path_str) → None.
               If None, uses fetch_yfinance_to_csv. Injected in tests.
    """

    def __init__(
        self,
        config: BacktestConfig | None = None,
        fetch_fn: Callable | None = None,
    ) -> None:
        self.config = config or BacktestConfig()
        self._fetch_fn = fetch_fn

    def run_ticker(
        self,
        ticker: str,
        start: str,
        end: str,
        adjust: bool,
        data_dir: Path,
    ) -> TickerResult:
        result = TickerResult(ticker=ticker)

        try:
            csv_path = data_dir / f"{ticker}_{start}_{end}.csv"

            if self._fetch_fn is not None:
                self._fetch_fn(ticker, start, end, str(csv_path))
            else:
                fetch_yfinance_to_csv(ticker, start, end, str(csv_path))

            loader = DataLoader(use_adjusted_close=adjust)
            df = loader.load_from_csv(csv_path)
            report = loader.get_last_report()
            result.rows_loaded = report.get("rows_loaded", 0)
            result.rows_after_cleaning = report.get("rows_after_cleaning", 0)
            result.adjusted_ohlc_applied = bool(report.get("adjusted_ohlc_applied", False))

            df = FeatureEngine().generate_shifted_features(df, drop_warmup=False)

            portfolio = PortfolioTracker(initial_cash=self.config.initial_cash)
            execution = ExecutionSimulator(slippage_pct=0.0005, fixed_fee=2.0)
            bt_results = Backtester(
                config=self.config, portfolio=portfolio, execution=execution
            ).run(df)

            trades = bt_results["trades"]
            result.total_trades = len(trades)
            result.final_equity = round(bt_results["final_equity"], 2)

            if trades:
                result.ambiguous_exits_pct = round(
                    bt_results["ambiguous_exits"] / len(trades) * 100, 2
                )

            me = MetricsEngine(MetricsConfig(periods_per_year=252, risk_free_rate_annual=0.0))
            sm = me.calculate_all(equity_curve=bt_results["equity_curve"], trades=trades)

            def _safe(v):
                if v is None:
                    return 0.0
                try:
                    f = float(v)
                    return 0.0 if f != f or f == float("inf") or f == float("-inf") else round(f, 3)
                except (TypeError, ValueError):
                    return 0.0

            result.total_return_pct = _safe(sm.get("total_return_pct"))
            result.cagr_pct = _safe(sm.get("cagr_pct"))
            result.max_drawdown_pct = _safe(sm.get("max_drawdown_pct"))
            result.sharpe_ratio = _safe(sm.get("sharpe_ratio"))
            result.calmar_ratio = _safe(sm.get("calmar_ratio"))
            result.profit_factor = _safe(sm.get("profit_factor"))
            result.expectancy_per_trade_R = _safe(sm.get("expectancy_per_trade_r"))
            result.win_rate_pct = _safe(sm.get("win_rate_pct"))

            closes = df["close"].values
            if len(closes) > 0:
                bm_equity = (self.config.initial_cash * closes / closes[0]).tolist()
                bm = me.calculate_benchmark(bm_equity)
                result.benchmark_cagr_pct = _safe(bm.get("cagr_pct"))
                result.benchmark_max_drawdown_pct = _safe(bm.get("max_drawdown_pct"))
                result.benchmark_sharpe = _safe(bm.get("sharpe_ratio"))
                result.benchmark_calmar_ratio = _safe(bm.get("calmar_ratio"))

            # Exposure-matched benchmark (diagnostic)
            exp_pct = compute_exposure_pct(trades, df)
            result.exposure_time_pct = round(exp_pct, 1)
            em_close_s = pd.Series(df["close"].values, index=df.index)
            em = ExposureMatchedBenchmarkEngine().calculate(
                strategy_equity_curve=bt_results["equity_curve"],
                benchmark_close=em_close_s,
                initial_cash=self.config.initial_cash,
                exposure_time_pct=exp_pct,
            )
            result.exposure_matched_cagr_pct = _safe(em.get("exposure_matched_cagr_pct"))
            result.exposure_matched_max_drawdown_pct = _safe(em.get("exposure_matched_max_drawdown_pct"))
            em_cal = em.get("exposure_matched_calmar", 0.0)
            result.exposure_matched_calmar = _safe(em_cal)
            result.strategy_vs_exposure_matched_calmar_delta = round(
                result.calmar_ratio - result.exposure_matched_calmar, 3
            )
            sm["exposure_matched_calmar"] = result.exposure_matched_calmar

            gate = FalsifierEngine(FalsifierConfig()).evaluate(
                strategy_metrics=sm,
                benchmark_metrics={"calmar_ratio": result.benchmark_calmar_ratio},
                total_trades=result.total_trades,
                ambiguous_exits_pct=result.ambiguous_exits_pct,
            )
            result.falsifier_pass = gate["overall_pass"]
            result.falsifier_failure_reasons = "; ".join(gate["failure_reasons"])

            diag = SignalDiagnostics().analyze_feature_funnel(
                df, min_confluence_score=self.config.min_confluence_score
            )
            result.signal_count = diag["signal_count"]
            result.rows_reaching_min_score = diag["rows_reaching_min_score"]
            result.signal_rate_pct = diag["signal_rate_pct"]
            result.top_bottlenecks = "; ".join(diag["bottlenecks"][:3])

        except Exception as exc:
            result.status = "ERROR"
            result.error = str(exc)

        return result

    def run_all(
        self,
        tickers: list[str],
        start: str,
        end: str,
        adjust: bool,
        output: str,
        data_dir: Path | None = None,
    ) -> tuple:
        if data_dir is None:
            data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for ticker in tickers:
            print(f"\n--- {ticker} ---")
            r = self.run_ticker(ticker, start, end, adjust, data_dir)
            results.append(r)
            tag = "PASS" if r.falsifier_pass else ("ERROR" if r.status == "ERROR" else "FAIL")
            detail = r.error[:60] if r.status == "ERROR" else r.falsifier_failure_reasons[:60]
            print(f"  status={r.status} trades={r.total_trades} falsifier={tag}  {detail}")

        df_out = pd.DataFrame([asdict(r) for r in results])
        out_path = Path(output)
        df_out.to_csv(out_path, index=False)
        print(f"\nResults saved → {out_path.resolve()}")

        summary = PortfolioValidator().evaluate(results)
        return results, summary


# ---------------------------------------------------------------------------
# CLI printing
# ---------------------------------------------------------------------------

def _print_portfolio_summary(summary: dict) -> None:
    print("\n=== MULTI-TICKER VALIDATION SUMMARY ===")
    skip = {"checks", "failure_reasons", "overall_pass"}
    for k, v in summary.items():
        if k not in skip:
            print(f"  {k}: {v}")
    if summary.get("failure_reasons"):
        print("  failure_reasons:")
        for r in summary["failure_reasons"]:
            print(f"    ✗ {r}")
    print(f"\n  *** OVERALL VERDICT: {summary['overall_verdict']} ***")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-ticker backtest validation")
    parser.add_argument("--tickers", nargs="+", required=True, help="Ticker symbols")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--adjust", action="store_true", help="Apply adjusted_close scaling")
    parser.add_argument("--output", default="multi_ticker_summary.csv", help="Output CSV path")
    parser.add_argument("--data-dir", default="data", help="Directory for per-ticker CSVs")
    args = parser.parse_args()

    runner = MultiTickerRunner()
    _, summary = runner.run_all(
        tickers=args.tickers,
        start=args.start,
        end=args.end,
        adjust=args.adjust,
        output=args.output,
        data_dir=Path(args.data_dir),
    )
    _print_portfolio_summary(summary)


if __name__ == "__main__":
    main()
