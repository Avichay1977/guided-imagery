"""
Randomized Timing Benchmark Runner v1

Diagnostic only. Runs the full backtest pipeline per ticker, then evaluates
whether the strategy's entry timing beats 1000 random entry schedules with
the same trade count and holding durations.
"""

import argparse
from pathlib import Path
from typing import Callable

import pandas as pd

from data_loader import DataLoader
from features import FeatureEngine
from backtester import Backtester, BacktestConfig
from portfolio import PortfolioTracker
from execution import ExecutionSimulator
from metrics import MetricsEngine, MetricsConfig
from randomized_benchmark import RandomizedTimingBenchmarkEngine, RandomizedBenchmarkConfig


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_randomized_benchmark(
    tickers: list[str],
    start: str,
    end: str,
    adjust: bool,
    output: str,
    data_dir: Path,
    fetch_fn: Callable | None = None,
    config: BacktestConfig | None = None,
    random_config: RandomizedBenchmarkConfig | None = None,
) -> pd.DataFrame:
    """
    Run randomized timing benchmark for a list of tickers.

    Parameters
    ----------
    fetch_fn     : optional callable(ticker, start, end, output_path) → None.
                   If None, uses yfinance (requires network access).
    config       : BacktestConfig (defaults to production defaults).
    random_config: RandomizedBenchmarkConfig (defaults to 1000 sims, seed=42).

    Returns
    -------
    pd.DataFrame with one row per ticker.
    """
    config = config or BacktestConfig()
    random_config = random_config or RandomizedBenchmarkConfig()
    engine = RandomizedTimingBenchmarkEngine(random_config)
    all_rows: list[dict] = []

    for ticker in tickers:
        print(f"\n--- {ticker} ---")
        try:
            csv_path = data_dir / f"{ticker}_{start}_{end}.csv"

            if fetch_fn is not None:
                fetch_fn(ticker, start, end, str(csv_path))
            else:
                from fetch_yfinance_data import fetch_yfinance_to_csv
                fetch_yfinance_to_csv(ticker, start, end, str(csv_path))

            loader = DataLoader(use_adjusted_close=adjust)
            df = loader.load_from_csv(csv_path)
            df = FeatureEngine().generate_shifted_features(df, drop_warmup=False)

            portfolio = PortfolioTracker(initial_cash=config.initial_cash)
            execution = ExecutionSimulator(slippage_pct=0.0005, fixed_fee=2.0)
            bt = Backtester(config=config, portfolio=portfolio, execution=execution).run(df)

            me = MetricsEngine(MetricsConfig(periods_per_year=252))
            sm = me.calculate_all(bt["equity_curve"], bt["trades"])

            result = engine.evaluate(df, bt["trades"], config.initial_cash, sm)
            result["ticker"] = ticker

            # Serialize list fields for CSV
            result["failure_reasons"] = "; ".join(result.get("failure_reasons", []))

            all_rows.append(result)

            p75_c = result.get("random_p75_calmar")
            p75_r = result.get("random_p75_total_return_pct")
            edge_c = result.get("timing_edge_percentile_calmar")
            status_tag = "PASS" if result.get("randomized_timing_pass") else result["status"]

            print(
                f"  {len(bt['trades'])} trades  |  "
                f"real_calmar={result['real_calmar']:.3f}  "
                f"p75_calmar={p75_c if p75_c is not None else 'N/A'}  "
                f"calmar_edge%={edge_c if edge_c is not None else 'N/A'}  |  "
                f"{status_tag}"
            )

        except Exception as exc:
            all_rows.append({
                "ticker": ticker,
                "status": "ERROR",
                "failure_reasons": str(exc),
                "randomized_timing_pass": False,
                "real_total_trades": 0,
            })
            print(f"  ERROR: {exc}")

    df_out = pd.DataFrame(all_rows)
    out_path = Path(output)
    df_out.to_csv(out_path, index=False)
    print(f"\nResults saved → {out_path.resolve()}")

    return df_out


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_randomized_summary(df: pd.DataFrame) -> None:
    if df.empty:
        print("\n=== RANDOMIZED TIMING BENCHMARK SUMMARY — no data ===")
        return

    print("\n=== RANDOMIZED TIMING BENCHMARK SUMMARY ===")

    n_error = (df["status"] == "ERROR").sum()
    n_insuff = (df["status"] == "INSUFFICIENT_TRADES_FOR_RANDOMIZATION").sum()
    eligible = df[df["status"].isin(["OK", "FAIL"])].copy()
    n_eligible = len(eligible)
    n_completed = len(df) - n_error
    n_passing = int(df["randomized_timing_pass"].sum())

    p75_calmar_beats = int(eligible["beats_random_p75_calmar"].sum()) if n_eligible > 0 else 0
    p75_return_beats = int(eligible["beats_random_p75_return"].sum()) if n_eligible > 0 else 0

    pass_rate = n_passing / n_completed * 100 if n_completed > 0 else 0.0
    med_edge_calmar = eligible["timing_edge_percentile_calmar"].dropna().median() if n_eligible > 0 else 0.0
    med_edge_return = eligible["timing_edge_percentile_return"].dropna().median() if n_eligible > 0 else 0.0

    print(f"  tickers_completed:                 {n_completed}")
    print(f"  tickers_failed (error):            {n_error}")
    print(f"  tickers_insufficient_trades:       {n_insuff}")
    print(f"  tickers_passing_randomized_timing: {n_passing}")
    print(f"  pass_rate_pct:                     {pass_rate:.1f}%")
    print(f"  median_timing_edge_percentile_calmar: {med_edge_calmar:.1f}")
    print(f"  median_timing_edge_percentile_return: {med_edge_return:.1f}")
    print(f"  tickers_above_random_p75_calmar:   {p75_calmar_beats}/{n_eligible}")
    print(f"  tickers_above_random_p75_return:   {p75_return_beats}/{n_eligible}")

    # Per-ticker table
    print(
        f"\n  {'Ticker':<8} {'Trades':>7} {'RealRet%':>9} {'p75Ret%':>8} "
        f"{'RealCalm':>9} {'p75Calm':>8} {'CalEdge%':>9} {'Pass':>5}"
    )
    sep = f"  {'-'*8} {'-'*7} {'-'*9} {'-'*8} {'-'*9} {'-'*8} {'-'*9} {'-'*5}"
    print(sep)
    for _, row in df.iterrows():
        if row.get("status") in ("ERROR", "INSUFFICIENT_TRADES_FOR_RANDOMIZATION"):
            print(f"  {str(row['ticker']):<8} {row['status']}")
            continue
        flag = "✓" if row.get("randomized_timing_pass") else "✗"
        trades = int(row.get("real_total_trades", 0))
        rr = row.get("real_total_return_pct", 0.0) or 0.0
        p75r = row.get("random_p75_total_return_pct", 0.0) or 0.0
        rc = row.get("real_calmar", 0.0) or 0.0
        p75c = row.get("random_p75_calmar", 0.0) or 0.0
        ec = row.get("timing_edge_percentile_calmar", 0.0) or 0.0
        print(
            f"  {str(row['ticker']):<8} "
            f"{trades:>7} "
            f"{rr:>9.1f} "
            f"{p75r:>8.1f} "
            f"{rc:>9.3f} "
            f"{p75c:>8.3f} "
            f"{ec:>9.1f} "
            f"{flag:>5}"
        )

    # Overall verdict
    overall_pass = (
        n_eligible >= 10
        and n_eligible > 0
        and (p75_calmar_beats / n_eligible) >= 0.60
        and (p75_return_beats / n_eligible) >= 0.60
        and med_edge_calmar >= 75
    )
    verdict = "RESEARCH-GO" if overall_pass else "NO-GO"
    print(f"\n  overall_randomized_verdict: {verdict}")
    print(f"\n  *** OVERALL VERDICT: {verdict} ***")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Randomized Timing Benchmark Runner (diagnostics only)"
    )
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--adjust", action="store_true")
    parser.add_argument("--n-simulations", type=int, default=1000)
    parser.add_argument("--output", default="randomized_timing_summary.csv")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    from run_github_data import github_fetch_fn

    random_config = RandomizedBenchmarkConfig(n_simulations=args.n_simulations)

    df = run_randomized_benchmark(
        tickers=args.tickers,
        start=args.start,
        end=args.end,
        adjust=args.adjust,
        output=args.output,
        data_dir=data_dir,
        fetch_fn=github_fetch_fn,
        random_config=random_config,
    )
    _print_randomized_summary(df)


if __name__ == "__main__":
    main()
