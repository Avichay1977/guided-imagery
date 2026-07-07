from dataclasses import dataclass
import numpy as np


@dataclass
class MetricsConfig:
    periods_per_year: int = 252
    risk_free_rate_annual: float = 0.0


class MetricsEngine:
    def __init__(self, config: MetricsConfig):
        self.config = config

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def calculate_all(
        self,
        equity_curve: list,
        trades: list | None = None,
    ) -> dict:
        metrics = self._equity_metrics(equity_curve)

        if trades:
            metrics.update(self._trade_metrics(trades))
        else:
            metrics.update(
                {
                    "total_trades": 0,
                    "win_rate_pct": None,
                    "avg_win": None,
                    "avg_loss": None,
                    "profit_factor": None,
                    "expectancy_per_trade_r": None,
                }
            )

        return metrics

    def calculate_benchmark(self, equity_curve: list) -> dict:
        return self._equity_metrics(equity_curve)

    # --------------------------------------------------
    # Core calculations
    # --------------------------------------------------

    def _equity_metrics(self, equity_curve: list) -> dict:
        eq = np.array(equity_curve, dtype=float)

        if len(eq) < 2:
            return {}

        total_return = (eq[-1] - eq[0]) / eq[0] if eq[0] > 0 else 0.0

        n_bars = len(eq) - 1
        duration_years = n_bars / self.config.periods_per_year
        cagr = (
            (eq[-1] / eq[0]) ** (1.0 / duration_years) - 1.0
            if duration_years > 0 and eq[0] > 0
            else 0.0
        )

        returns = np.diff(eq) / eq[:-1]
        returns = returns[np.isfinite(returns)]

        rf_per_period = (
            (1 + self.config.risk_free_rate_annual) ** (1.0 / self.config.periods_per_year) - 1
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

        calmar = (
            cagr / max_drawdown
            if max_drawdown > 0
            else (float("inf") if cagr > 0 else 0.0)
        )

        return {
            "total_return_pct": round(total_return * 100, 2),
            "cagr_pct": round(cagr * 100, 2),
            "sharpe_ratio": round(float(sharpe), 3),
            "max_drawdown_pct": round(max_drawdown * 100, 2),
            "calmar_ratio": round(calmar, 3),
        }

    def _trade_metrics(self, trades: list) -> dict:
        pnls = [t["pnl"] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        win_rate = len(wins) / len(pnls) if pnls else 0.0
        avg_win = float(np.mean(wins)) if wins else 0.0
        avg_loss = float(np.mean(losses)) if losses else 0.0
        profit_factor = (
            abs(sum(wins) / sum(losses))
            if losses and sum(losses) != 0
            else float("inf")
        )

        r_multiples = []
        for t in trades:
            risk = t["entry_price"] - t["stop_price"]
            if risk > 0:
                r = (t["exit_price"] - t["entry_price"]) / risk
                r_multiples.append(r)

        expectancy_r = float(np.mean(r_multiples)) if r_multiples else 0.0

        return {
            "total_trades": len(trades),
            "win_rate_pct": round(win_rate * 100, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 3),
            "expectancy_per_trade_r": round(expectancy_r, 3),
        }
