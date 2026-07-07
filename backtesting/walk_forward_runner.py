"""
Walk-Forward Diagnostic Runner v1

Diagnostic only. No parameter optimization. No strategy changes.
Runs the full backtest pipeline on each OOS test window for each ticker,
then aggregates results across all tickers and splits.
"""

import argparse
from pathlib import Path
from typing import Callable

import pandas as pd

from backtester import BacktestConfig
from data_loader import DataLoader
from features import FeatureEngine
from randomized_benchmark import RandomizedBenchmarkConfig
from walk_forward import WalkForwardConfig, WalkForwardEngine


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_walk_forward(
    tickers: list[str],
    start: str,
    end: str,
    adjust: bool,
    output: str,
    data_dir: Path,
    fetch_fn: Callable | None = None,
    config: BacktestConfig | None = None,
    wf_config: WalkForwardConfig | None = None,
    random_config: RandomizedBenchmarkConfig | None = None,
) -> pd.DataFrame:
    """
    Run walk-forward diagnostic for a list of tickers.

    Parameters
    ----------
    fetch_fn     : optional callable(ticker, start, end, output_path) → None.
                   If None, uses yfinance (requires network access).
    config       : BacktestConfig (defaults to production defaults).
    wf_config    : WalkForwardConfig (defaults to 3/1/1-year splits).
    random_config: RandomizedBenchmarkConfig for the randomized timing sub-test.

    Returns
    -------
    pd.DataFrame with one row per (ticker, split).
    """
    config = config or BacktestConfig()
    wf_config = wf_config or WalkForwardConfig()
    engine = WalkForwardEngine(
        config=wf_config,
        backtester_config=config,
        random_config=random_config,
    )
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

            rows = engine.evaluate_ticker(df, ticker, start, end)
            all_rows.extend(rows)

            ok_rows = [r for r in rows if r.get("status") == "OK"]
            oos_trades = sum(r.get("test_total_trades", 0) for r in ok_rows)
            n_pass = sum(1 for r in ok_rows if r.get("falsifier_pass", False))
            rand_pass = sum(1 for r in ok_rows if r.get("randomized_timing_pass", False))

            print(
                f"  {len(rows)} splits  |  {oos_trades} OOS trades  |  "
                f"falsifier={n_pass}/{len(ok_rows)}  "
                f"random_timing={rand_pass}/{len(ok_rows)}"
            )

        except Exception as exc:
            all_rows.append({
                "ticker": ticker,
                "status": "ERROR",
                "failure_reasons": str(exc),
                "test_total_trades": 0,
                "randomized_timing_pass": False,
                "falsifier_pass": False,
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

def _print_walk_forward_summary(
    df: pd.DataFrame, engine: WalkForwardEngine
) -> None:
    if df.empty:
        print("\n=== WALK-FORWARD SUMMARY — no data ===")
        return

    all_rows = df.to_dict("records")
    agg = engine.aggregate(all_rows)

    print("\n=== WALK-FORWARD DIAGNOSTIC SUMMARY ===")
    print(f"  n_eligible_splits:                  {agg['n_eligible_splits']}")
    print(f"  oos_total_trades:                   {agg['oos_total_trades']}")
    print(
        f"  oos_positive_expectancy_rate:       "
        f"{agg['oos_positive_expectancy_rate']:.1%}"
    )
    print(
        f"  oos_average_profit_factor:          "
        f"{agg['oos_average_profit_factor']:.3f}"
    )
    print(
        f"  oos_calmar_above_benchmark_rate:    "
        f"{agg['oos_calmar_above_benchmark_rate']:.1%}"
    )
    print(
        f"  oos_randomized_timing_pass_rate:    "
        f"{agg['oos_randomized_timing_pass_rate']:.1%}"
    )
    print(
        f"  oos_max_ticker_concentration_pct:   "
        f"{agg['oos_max_ticker_concentration_pct']:.1f}%"
    )

    # Per-split table
    eligible = df[df["status"] == "OK"].copy()
    if not eligible.empty:
        print(
            f"\n  {'Ticker':<8} {'Split':>5} {'TestPeriod':<22} "
            f"{'Trades':>7} {'ExpR':>6} {'PF':>6} "
            f"{'Calmar':>7} {'BM_C':>7} {'RandPass':>9} {'FalsPass':>9}"
        )
        sep = (
            f"  {'-'*8} {'-'*5} {'-'*22} "
            f"{'-'*7} {'-'*6} {'-'*6} "
            f"{'-'*7} {'-'*7} {'-'*9} {'-'*9}"
        )
        print(sep)
        for _, row in eligible.iterrows():
            period = f"{row.get('test_start','?')[:10]}–{row.get('test_end','?')[:10]}"
            fp = "✓" if row.get("falsifier_pass") else "✗"
            rp = "✓" if row.get("randomized_timing_pass") else "✗"
            print(
                f"  {str(row.get('ticker', '')):<8} "
                f"{int(row.get('split_id', 0)):>5} "
                f"{period:<22} "
                f"{int(row.get('test_total_trades', 0)):>7} "
                f"{float(row.get('test_expectancy_per_trade_R') or 0):>6.3f} "
                f"{float(row.get('test_profit_factor') or 0):>6.3f} "
                f"{float(row.get('test_calmar') or 0):>7.3f} "
                f"{float(row.get('test_benchmark_calmar') or 0):>7.3f} "
                f"{rp:>9} "
                f"{fp:>9}"
            )

    # Verdict
    verdict = agg["verdict"]
    if agg["verdict_failure_reasons"]:
        print("\n  Failure reasons:")
        for r in agg["verdict_failure_reasons"]:
            print(f"    • {r}")
    print(f"\n  *** OVERALL VERDICT: {verdict} ***")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Walk-Forward Diagnostic Runner (diagnostics only)"
    )
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--adjust", action="store_true")
    parser.add_argument("--train-years", type=int, default=3)
    parser.add_argument("--test-years", type=int, default=1)
    parser.add_argument("--step-years", type=int, default=1)
    parser.add_argument("--n-simulations", type=int, default=200)
    parser.add_argument("--output", default="walk_forward_summary.csv")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    from run_github_data import github_fetch_fn

    wf_config = WalkForwardConfig(
        train_years=args.train_years,
        test_years=args.test_years,
        step_years=args.step_years,
    )
    random_config = RandomizedBenchmarkConfig(n_simulations=args.n_simulations)
    engine = WalkForwardEngine(
        config=wf_config,
        random_config=random_config,
    )

    df = run_walk_forward(
        tickers=args.tickers,
        start=args.start,
        end=args.end,
        adjust=args.adjust,
        output=args.output,
        data_dir=data_dir,
        fetch_fn=github_fetch_fn,
        wf_config=wf_config,
        random_config=random_config,
    )
    _print_walk_forward_summary(df, engine)


if __name__ == "__main__":
    main()
