"""
Strategy Lab Runner v1

Diagnostic only. Tests a named strategy variant through the full existing gate:
DataLoader → FeatureEngine → Backtester → Metrics → Benchmark → Falsifier →
Exposure-Matched Benchmark → Randomized Timing Benchmark → Walk-Forward Diagnostic.

Overall verdict is determined solely by Walk-Forward.
No parameters are modified. No ticker selection based on prior results.
"""

import argparse
from pathlib import Path
from typing import Callable

import pandas as pd

from backtester import BacktestConfig
from data_loader import DataLoader
from exposure_benchmark import ExposureMatchedBenchmarkEngine, compute_exposure_pct
from execution import ExecutionSimulator
from falsifier import FalsifierConfig, FalsifierEngine
from features import FeatureEngine
from metrics import MetricsEngine, MetricsConfig
from portfolio import PortfolioTracker
from randomized_benchmark import RandomizedBenchmarkConfig, RandomizedTimingBenchmarkEngine
from strategy_variants import StrategyVariant, get_variant
from walk_forward import WalkForwardConfig, WalkForwardEngine

from protocol_v1_2_metric_sources import build_summary_row_with_v1_2_metrics


# ---------------------------------------------------------------------------
# v1.2 schema wiring helper
# ---------------------------------------------------------------------------

def enrich_lab_row(base_row: dict, metric_sources: "list[dict] | None" = None) -> dict:
    """
    Return a new summary row that includes v1.2 metric source fields alongside
    the existing v1.1 fields.

    This is the documented integration point for future runners: when a run
    collects richer metric objects (total returns, p95 comparators), pass them
    here as metric_sources so the output CSV carries v1.2-ready fields from
    the start. If metric_sources is None or empty, the eight v1.2 metric
    fields are added as None and will surface as *_INSUFFICIENT_DATA in
    downstream v1.2 reporting.

    Rules (enforced by build_summary_row_with_v1_2_metrics):
    - Returns a new dict; base_row is never mutated.
    - All existing v1.1 fields preserved unchanged.
    - Protected v1.1 keys (verdict / status / failure_reasons) cannot be
      overwritten by any source.
    - p75 source keys are never aliased to p95 fields.
    - Does not add v1.2 diagnostic labels — call the reporting adapter for that.
    - Never emits RESEARCH-GO or LIVE-GO.
    """
    return build_summary_row_with_v1_2_metrics(base_row, metric_sources)


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def run_strategy_lab(
    variant: StrategyVariant,
    tickers: list[str],
    start: str,
    end: str,
    adjust: bool,
    output: str,
    data_dir: Path,
    fetch_fn: Callable | None = None,
    bt_config: BacktestConfig | None = None,
    wf_config: WalkForwardConfig | None = None,
    rand_config: RandomizedBenchmarkConfig | None = None,
) -> pd.DataFrame:
    """
    Run the full research gate for a strategy variant across a ticker universe.

    Parameters
    ----------
    variant    : a StrategyVariant instance (from strategy_variants.py)
    fetch_fn   : optional callable(ticker, start, end, output_path) → None
    bt_config  : BacktestConfig — must not be modified by the variant
    wf_config  : WalkForwardConfig
    rand_config: RandomizedBenchmarkConfig for timing benchmark

    Returns
    -------
    pd.DataFrame  — one row per (ticker, split); includes strategy identity.
    """
    bt_config = bt_config or BacktestConfig()
    wf_config = wf_config or WalkForwardConfig()
    rand_config = rand_config or RandomizedBenchmarkConfig()

    wf_engine = WalkForwardEngine(
        config=wf_config,
        backtester_config=bt_config,
        random_config=rand_config,
        strategy_variant=variant,
    )

    all_rows: list[dict] = []

    for ticker in tickers:
        print(f"\n--- {ticker}  [{variant.strategy_name} {variant.strategy_version}] ---")
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

            # Walk-forward OOS evaluation (runs Backtester, Metrics,
            # Exposure-Matched, Randomized Timing internally per split)
            rows = wf_engine.evaluate_ticker(df, ticker, start, end)

            # Stamp strategy identity on every row
            for r in rows:
                r["strategy_name"] = variant.strategy_name
                r["strategy_version"] = variant.strategy_version

            all_rows.extend(rows)

            ok_rows = [r for r in rows if r.get("status") == "OK"]
            oos_trades = sum(r.get("test_total_trades", 0) for r in ok_rows)
            n_fp = sum(1 for r in ok_rows if r.get("falsifier_pass", False))
            n_rp = sum(1 for r in ok_rows if r.get("randomized_timing_pass", False))

            print(
                f"  {len(rows)} splits  |  {oos_trades} OOS trades  |  "
                f"falsifier={n_fp}/{len(ok_rows)}  "
                f"random_timing={n_rp}/{len(ok_rows)}"
            )

        except Exception as exc:
            all_rows.append({
                "ticker": ticker,
                "strategy_name": variant.strategy_name,
                "strategy_version": variant.strategy_version,
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


def get_verdict(df: pd.DataFrame, wf_config: WalkForwardConfig | None = None) -> dict:
    """
    Compute the walk-forward aggregate verdict from a lab results DataFrame.

    Returns the same dict as WalkForwardEngine.aggregate().
    """
    engine = WalkForwardEngine(config=wf_config)
    return engine.aggregate(df.to_dict("records"))


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_lab_summary(df: pd.DataFrame, wf_config: WalkForwardConfig | None = None) -> None:
    if df.empty:
        print("\n=== STRATEGY LAB SUMMARY — no data ===")
        return

    agg = get_verdict(df, wf_config)
    variant_id = ""
    if "strategy_name" in df.columns and "strategy_version" in df.columns:
        sn = df["strategy_name"].dropna().iloc[0] if not df["strategy_name"].dropna().empty else ""
        sv = df["strategy_version"].dropna().iloc[0] if not df["strategy_version"].dropna().empty else ""
        variant_id = f"  {sn} {sv}"

    print(f"\n=== STRATEGY LAB SUMMARY{variant_id} ===")
    print(f"  n_eligible_splits:                  {agg['n_eligible_splits']}")
    print(f"  oos_total_trades:                   {agg['oos_total_trades']}")
    print(f"  oos_positive_expectancy_rate:       {agg['oos_positive_expectancy_rate']:.1%}")
    print(f"  oos_average_profit_factor:          {agg['oos_average_profit_factor']:.3f}")
    print(f"  oos_calmar_above_benchmark_rate:    {agg['oos_calmar_above_benchmark_rate']:.1%}")
    print(f"  oos_randomized_timing_pass_rate:    {agg['oos_randomized_timing_pass_rate']:.1%}")
    print(f"  oos_max_ticker_concentration_pct:   {agg['oos_max_ticker_concentration_pct']:.1f}%")

    if agg["verdict_failure_reasons"]:
        print("\n  Failure reasons:")
        for r in agg["verdict_failure_reasons"]:
            print(f"    • {r}")

    print(f"\n  *** OVERALL VERDICT: {agg['verdict']} ***")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Strategy Lab Runner v1 (diagnostics only)"
    )
    parser.add_argument(
        "--strategy", required=True,
        help="Variant name, e.g. TrendPullbackConfluence_v1"
    )
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--adjust", action="store_true")
    parser.add_argument("--train-years", type=int, default=3)
    parser.add_argument("--test-years", type=int, default=1)
    parser.add_argument("--step-years", type=int, default=1)
    parser.add_argument("--n-simulations", type=int, default=200)
    parser.add_argument("--output", default="strategy_lab_summary.csv")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()

    variant = get_variant(args.strategy)

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    from run_github_data import github_fetch_fn

    wf_config = WalkForwardConfig(
        train_years=args.train_years,
        test_years=args.test_years,
        step_years=args.step_years,
    )
    rand_config = RandomizedBenchmarkConfig(n_simulations=args.n_simulations)

    df = run_strategy_lab(
        variant=variant,
        tickers=args.tickers,
        start=args.start,
        end=args.end,
        adjust=args.adjust,
        output=args.output,
        data_dir=data_dir,
        fetch_fn=github_fetch_fn,
        wf_config=wf_config,
        rand_config=rand_config,
    )
    _print_lab_summary(df, wf_config)


if __name__ == "__main__":
    main()
