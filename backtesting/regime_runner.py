"""
Regime Analysis Runner v1

Diagnostic only. No parameter optimization. No strategy changes.
Runs full backtest pipeline per ticker, builds date-indexed equity curves,
runs RegimeAnalysisEngine, saves per-(ticker,year) CSV, prints summary.
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
from regime_analysis import RegimeAnalysisEngine


# ---------------------------------------------------------------------------
# Equity-curve builders
# ---------------------------------------------------------------------------

def _build_equity_series(equity_curve: list, df_index: pd.DatetimeIndex) -> pd.Series:
    n = min(len(equity_curve), len(df_index))
    return pd.Series(equity_curve[:n], index=df_index[:n])


def _build_benchmark_series(df: pd.DataFrame, initial_cash: float) -> pd.Series:
    closes = df["close"].values
    bm_equity = initial_cash * closes / closes[0]
    return pd.Series(bm_equity, index=df.index)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_regime_analysis(
    tickers: list[str],
    start: str,
    end: str,
    adjust: bool,
    output: str,
    data_dir: Path,
    fetch_fn: Callable | None = None,
    config: BacktestConfig | None = None,
) -> pd.DataFrame:
    """
    Run regime analysis for a list of tickers.

    Parameters
    ----------
    fetch_fn : optional callable(ticker, start, end, output_path_str) → None.
               If None, uses yfinance (requires network access).
    config : BacktestConfig to use (defaults to production defaults).

    Returns
    -------
    pd.DataFrame with one row per (ticker, year).
    """
    config = config or BacktestConfig()
    engine = RegimeAnalysisEngine()
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
            bt_results = Backtester(
                config=config, portfolio=portfolio, execution=execution
            ).run(df)

            strat_series = _build_equity_series(bt_results["equity_curve"], df.index)
            bench_series = _build_benchmark_series(df, config.initial_cash)

            analysis = engine.analyze_by_year(
                strat_series, bench_series, bt_results["trades"]
            )

            for year, yr in analysis["years"].items():
                row: dict = {"ticker": ticker, "year": year}
                row.update(yr)
                row["warnings"] = "; ".join(yr["warnings"])
                all_rows.append(row)

            print(
                f"  {len(bt_results['trades'])} trades  |  "
                f"{len(analysis['all_warnings'])} warnings"
            )

        except Exception as exc:
            print(f"  ERROR: {exc}")

    df_out = pd.DataFrame(all_rows)
    out_path = Path(output)
    df_out.to_csv(out_path, index=False)
    print(f"\nRegime analysis saved → {out_path.resolve()}")

    return df_out


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_regime_summary(df: pd.DataFrame) -> None:
    if df.empty:
        print("\n=== REGIME ANALYSIS SUMMARY — no data ===")
        return

    print("\n=== REGIME ANALYSIS SUMMARY ===")

    year_agg = (
        df.groupby("year")
        .agg(
            strategy_return_pct=("strategy_return_pct", "mean"),
            benchmark_return_pct=("benchmark_return_pct", "mean"),
            strategy_calmar=("strategy_calmar", lambda x: x[x != float("inf")].mean()),
            benchmark_calmar=("benchmark_calmar", lambda x: x[x != float("inf")].mean()),
            total_trades=("trade_count", "sum"),
            avg_exposure_pct=("exposure_pct", "mean"),
        )
        .reset_index()
    )

    header = f"  {'Year':<6} {'Strat%':>8} {'BM%':>8} {'S.Calmar':>10} {'B.Calmar':>10} {'Trades':>7} {'Exp%':>7}"
    print(header)
    print(f"  {'-'*6} {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*7} {'-'*7}")
    for _, row in year_agg.iterrows():
        sc = row.strategy_calmar
        bc = row.benchmark_calmar
        flag = "" if (pd.isna(sc) or pd.isna(bc) or sc >= bc) else "  ✗"
        print(
            f"  {int(row.year):<6} "
            f"{row.strategy_return_pct:>8.1f} "
            f"{row.benchmark_return_pct:>8.1f} "
            f"{sc:>10.3f} "
            f"{bc:>10.3f} "
            f"{int(row.total_trades):>7} "
            f"{row.avg_exposure_pct:>7.1f}"
            f"{flag}"
        )

    all_warns = (
        df["warnings"]
        .dropna()
        .str.split("; ")
        .explode()
        .dropna()
        .pipe(lambda s: s[s != ""])
    )
    if not all_warns.empty:
        warn_counts = all_warns.value_counts().head(15)
        print(f"\n  Warnings ({len(all_warns)} total):")
        for warn, count in warn_counts.items():
            print(f"    [{count:>2}x] {warn}")

    finite = df[(df["strategy_calmar"] != float("inf")) & (df["benchmark_calmar"] != float("inf"))].copy()
    if not finite.empty:
        finite["calmar_delta"] = finite["strategy_calmar"] - finite["benchmark_calmar"]
        delta_by_year = finite.groupby("year")["calmar_delta"].mean()
        print(f"\n  Avg calmar delta (strategy − benchmark) by year:")
        for year, delta in delta_by_year.items():
            flag = "✓" if delta >= 0 else "✗"
            print(f"    {int(year)}: {delta:+.3f}  {flag}")

    tickers_beating = df.groupby("ticker").apply(
        lambda g: (g["strategy_calmar"] >= g["benchmark_calmar"]).all()
    )
    beat_count = int(tickers_beating.sum())
    total_count = len(tickers_beating)
    print(
        f"\n  Tickers beating benchmark calmar ALL years: "
        f"{beat_count}/{total_count}"
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Regime Analysis Runner (diagnostics only)")
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--adjust", action="store_true")
    parser.add_argument("--output", default="regime_summary.csv")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    from run_github_data import github_fetch_fn

    df = run_regime_analysis(
        tickers=args.tickers,
        start=args.start,
        end=args.end,
        adjust=args.adjust,
        output=args.output,
        data_dir=data_dir,
        fetch_fn=github_fetch_fn,
    )
    _print_regime_summary(df)


if __name__ == "__main__":
    main()
