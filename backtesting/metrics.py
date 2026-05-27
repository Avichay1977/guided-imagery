from dataclasses import dataclass
import numpy as np


@dataclass
class MetricsConfig:
    periods_per_year: int = 252
    risk_free_rate_annual: float = 0.0


class MetricsEngine:
    def __init__(self, config: MetricsConfig):
        self.config = config

    def calculate_all(self, equity_curve: list, trades: list) -> dict:
        eq = np.array(equity_curve, dtype=float)

        if len(eq) < 2:
            return {}

        total_return = (eq[-1] - eq[0]) / eq[0] if eq[0] > 0 else 0.0

        returns = np.diff(eq) / eq[:-1]
        returns = returns[np.isfinite(returns)]

        rf_per_period = (
            (1 + self.config.risk_free_rate_annual) ** (1 / self.config.periods_per_year) - 1
        )

        excess = returns - rf_per_period
        sharpe = (
            (excess.mean() / excess.std()) * np.sqrt(self.config.periods_per_year)
            if excess.std() > 0
            else 0.0
        )

        peak = np.maximum.accumulate(eq)
        drawdown = (peak - eq) / peak
        max_drawdown = float(drawdown.max())

        trade_pnls = [t["pnl"] for t in trades]
        wins = [p for p in trade_pnls if p > 0]
        losses = [p for p in trade_pnls if p <= 0]

        win_rate = len(wins) / len(trade_pnls) if trade_pnls else 0.0
        avg_win = float(np.mean(wins)) if wins else 0.0
        avg_loss = float(np.mean(losses)) if losses else 0.0
        profit_factor = (
            abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float("inf")
        )

        return {
            "total_return_pct": round(total_return * 100, 2),
            "sharpe_ratio": round(float(sharpe), 3),
            "max_drawdown_pct": round(max_drawdown * 100, 2),
            "total_trades": len(trades),
            "win_rate_pct": round(win_rate * 100, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 3),
        }
