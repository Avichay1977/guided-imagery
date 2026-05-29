import argparse
import sys

from data_loader import DataLoader
from features import FeatureEngine
from backtester import Backtester, BacktestConfig
from portfolio import PortfolioTracker
from execution import ExecutionSimulator
from metrics import MetricsEngine, MetricsConfig
from falsifier import FalsifierEngine, FalsifierConfig


def _print_section(title: str, data: dict) -> None:
    print(f"\n=== {title} ===")
    for key, value in data.items():
        print(f"  {key}: {value}")


def _build_benchmark_equity(df, initial_cash: float) -> list:
    """Buy at first close, hold to last close. Normalized to initial_cash."""
    closes = df["close"].values
    if len(closes) == 0:
        return [initial_cash]
    return (initial_cash * closes / closes[0]).tolist()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run backtest on OHLCV CSV")
    parser.add_argument("--input", required=True, help="Path to OHLCV CSV")
    parser.add_argument(
        "--adjust",
        action="store_true",
        help="Apply adjusted_close scaling via DataLoader (requires adjusted_close column)",
    )
    args = parser.parse_args()

    # --------------------------------------------------
    # Load & clean data
    # --------------------------------------------------
    loader = DataLoader(use_adjusted_close=args.adjust)

    try:
        df = loader.load_from_csv(args.input)
    except Exception as exc:
        print(f"ERROR loading data: {exc}", file=sys.stderr)
        sys.exit(1)

    _print_section("DATA QUALITY REPORT", loader.get_last_report())

    # --------------------------------------------------
    # Feature engineering (all shifts applied — no lookahead)
    # --------------------------------------------------
    fe = FeatureEngine()
    df = fe.generate_shifted_features(df, drop_warmup=False)

    report = loader.get_last_report()
    if report.get("invalid_geometry_rows_corrected", 0) > len(df) * 0.01:
        print(
            "\nWARNING: >1% of rows had geometry corrections — inspect data source.",
            file=sys.stderr,
        )

    # --------------------------------------------------
    # Backtest
    # --------------------------------------------------
    config = BacktestConfig(
        initial_cash=100_000,
        max_risk_pct=0.01,
        max_drawdown_kill_pct=0.15,
        min_confluence_score=5,
        atr_stop_multiplier=2.0,
        take_profit_r=3.0,
        max_entry_gap_pct=0.05,
        min_entry_gap_pct=-0.03,
    )

    portfolio = PortfolioTracker(initial_cash=config.initial_cash)
    execution = ExecutionSimulator(slippage_pct=0.0005, fixed_fee=2.0)
    backtester = Backtester(config=config, portfolio=portfolio, execution=execution)

    results = backtester.run(df)

    ambiguous_pct = (
        results["ambiguous_exits"] / len(results["trades"]) * 100
        if results["trades"]
        else 0.0
    )

    _print_section(
        "BACKTEST",
        {
            "final_equity": round(results["final_equity"], 2),
            "trades": len(results["trades"]),
            "kill_switch_triggered": results["kill_switch_triggered"],
            "ambiguous_exits": results["ambiguous_exits"],
            "ambiguous_exits_pct": f"{ambiguous_pct:.1f}%",
        },
    )

    # --------------------------------------------------
    # Metrics
    # --------------------------------------------------
    engine = MetricsEngine(MetricsConfig(periods_per_year=252, risk_free_rate_annual=0.0))

    strategy_metrics = engine.calculate_all(
        equity_curve=results["equity_curve"],
        trades=results["trades"],
    )
    _print_section("METRICS", strategy_metrics)

    # --------------------------------------------------
    # Benchmark (buy & hold)
    # --------------------------------------------------
    benchmark_equity = _build_benchmark_equity(df, config.initial_cash)
    benchmark_metrics = engine.calculate_benchmark(benchmark_equity)
    _print_section("BENCHMARK (buy & hold)", benchmark_metrics)

    # --------------------------------------------------
    # Strategy vs Benchmark
    # --------------------------------------------------
    def _delta(key: str, higher_is_better: bool = True) -> str:
        s = strategy_metrics.get(key)
        b = benchmark_metrics.get(key)
        if s is None or b is None:
            return "n/a"
        diff = s - b
        sign = "+" if diff >= 0 else ""
        better = (diff > 0) == higher_is_better
        tag = "✓" if better else "✗"
        return f"{sign}{diff:.2f}  {tag}"

    comparison = {
        "cagr_pct      [strategy vs benchmark]": _delta("cagr_pct"),
        "sharpe_ratio  [strategy vs benchmark]": _delta("sharpe_ratio"),
        "max_drawdown  [strategy vs benchmark]": _delta("max_drawdown_pct", higher_is_better=False),
        "calmar_ratio  [strategy vs benchmark]": _delta("calmar_ratio"),
    }
    _print_section("STRATEGY VS BENCHMARK", comparison)

    # --------------------------------------------------
    # Falsifier Gate
    # --------------------------------------------------
    falsifier = FalsifierEngine(FalsifierConfig())
    ambiguous_pct = (
        results["ambiguous_exits"] / len(results["trades"]) * 100
        if results["trades"] else 0.0
    )
    gate = falsifier.evaluate(
        strategy_metrics=strategy_metrics,
        benchmark_metrics=benchmark_metrics,
        total_trades=len(results["trades"]),
        ambiguous_exits_pct=ambiguous_pct,
    )

    print("\n=== FALSIFIER GATE ===")
    for check_name, detail in gate["checks"].items():
        status = "PASS" if detail.get("pass") else "FAIL"
        if detail.get("skipped"):
            status = "SKIP"
        print(f"  [{status}] {check_name}: {detail}")
    if gate["failure_reasons"]:
        print("  failure_reasons:")
        for r in gate["failure_reasons"]:
            print(f"    ✗ {r}")
    if gate["warnings"]:
        print("  warnings:")
        for w in gate["warnings"]:
            print(f"    ⚠ {w}")
    print(f"  overall_pass: {gate['overall_pass']}")

    # Summary verdict — depends on FalsifierEngine
    s_calmar = strategy_metrics.get("calmar_ratio", 0)
    b_calmar = benchmark_metrics.get("calmar_ratio", 0)
    exp_r = strategy_metrics.get("expectancy_per_trade_r", 0)

    print("\n--- VERDICT ---")
    if not gate["overall_pass"]:
        print("  ✗ FALSIFIER GATE: FAIL")
        for r in gate["failure_reasons"]:
            print(f"      {r}")
        print("  → NO-GO: strategy not validated")
        return

    if exp_r is not None and exp_r <= 0:
        print("  ✗ expectancy_per_trade_R ≤ 0 → edge not confirmed")
    else:
        print(f"  ✓ expectancy_per_trade_R = {exp_r}")

    if s_calmar >= b_calmar:
        print(f"  ✓ Calmar {s_calmar:.3f} ≥ benchmark {b_calmar:.3f}")
    else:
        print(f"  ✗ Calmar {s_calmar:.3f} < benchmark {b_calmar:.3f}")

    pf = strategy_metrics.get("profit_factor", 0) or 0
    if pf >= 1.2:
        print(f"  ✓ profit_factor = {pf}")
    else:
        print(f"  ✗ profit_factor = {pf}  (target ≥ 1.2)")


if __name__ == "__main__":
    main()
