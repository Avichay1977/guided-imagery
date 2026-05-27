from data_loader import DataLoader
from backtester import Backtester, BacktestConfig
from portfolio import PortfolioTracker
from execution import ExecutionSimulator
from metrics import MetricsEngine, MetricsConfig


def main():
    loader = DataLoader(
        use_adjusted_close=False,
    )

    df = loader.load_from_csv("data.csv")

    print("=== DATA QUALITY REPORT ===")
    for key, value in loader.get_last_report().items():
        print(f"{key}: {value}")

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

    execution = ExecutionSimulator(
        slippage_pct=0.0005,
        fixed_fee=2.0,
    )

    backtester = Backtester(
        config=config,
        portfolio=portfolio,
        execution=execution,
    )

    results = backtester.run(df)

    metrics_engine = MetricsEngine(
        MetricsConfig(
            periods_per_year=252,
            risk_free_rate_annual=0.0,
        )
    )

    metrics = metrics_engine.calculate_all(
        equity_curve=results["equity_curve"],
        trades=results["trades"],
    )

    print("\n=== BACKTEST ===")
    print("Final Equity:", results["final_equity"])
    print("Trades:", len(results["trades"]))
    print("Kill Switch:", results["kill_switch_triggered"])
    print("Ambiguous Exits:", results["ambiguous_exits"])

    print("\n=== METRICS ===")
    for key, value in metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
