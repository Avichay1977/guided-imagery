from dataclasses import dataclass
from typing import Any
import pandas as pd


@dataclass
class BacktestConfig:
    initial_cash: float = 100_000
    max_risk_pct: float = 0.01
    max_drawdown_kill_pct: float = 0.15
    min_confluence_score: int = 5
    atr_stop_multiplier: float = 2.0
    take_profit_r: float = 3.0
    max_entry_gap_pct: float = 0.05
    min_entry_gap_pct: float = -0.03


class Backtester:
    def __init__(self, config: BacktestConfig, portfolio, execution):
        self.config = config
        self.portfolio = portfolio
        self.execution = execution

    def run(self, df: pd.DataFrame) -> dict:
        trades = []
        equity_curve = []
        kill_switch_triggered = False
        ambiguous_exits = 0
        open_position = None
        peak_equity = self.portfolio.cash

        rows = list(df.itertuples())

        for i, row in enumerate(rows):
            current_equity = self.portfolio.equity
            equity_curve.append(current_equity)

            if current_equity > peak_equity:
                peak_equity = current_equity

            drawdown = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0.0
            if drawdown >= self.config.max_drawdown_kill_pct:
                kill_switch_triggered = True
                break

            if open_position is not None:
                exit_price, exit_reason = self._check_exit(row, open_position)
                if exit_price is not None:
                    trade = self.execution.close_position(
                        portfolio=self.portfolio,
                        position=open_position,
                        exit_price=exit_price,
                        exit_time=row.Index,
                        exit_reason=exit_reason,
                    )
                    trades.append(trade)
                    open_position = None
                    if exit_reason == "ambiguous":
                        ambiguous_exits += 1
                continue

            if not self._has_valid_value(row, "signal") or row.signal != 1:
                continue

            score = self.calculate_confluence_score(row)
            if score < self.config.min_confluence_score:
                continue

            if i + 1 >= len(rows):
                continue

            next_row = rows[i + 1]

            gap_pct = (next_row.open - row.close) / row.close
            if gap_pct > self.config.max_entry_gap_pct or gap_pct < self.config.min_entry_gap_pct:
                continue

            if not self._has_valid_value(row, "atr") or row.atr <= 0:
                continue

            entry_price = self.execution.apply_slippage(next_row.open, direction="buy")
            stop_price = entry_price - (self.config.atr_stop_multiplier * row.atr)
            risk_per_share = entry_price - stop_price

            if risk_per_share <= 0:
                continue

            risk_amount = self.portfolio.cash * self.config.max_risk_pct
            shares = risk_amount / risk_per_share
            tp_price = entry_price + (self.config.take_profit_r * risk_per_share)

            position = self.execution.open_position(
                portfolio=self.portfolio,
                entry_price=entry_price,
                entry_time=next_row.Index,
                shares=shares,
                stop_price=stop_price,
                take_profit_price=tp_price,
                confluence_score=score,
            )

            if position is not None:
                open_position = position

        equity_curve.append(self.portfolio.equity)

        return {
            "equity_curve": equity_curve,
            "trades": trades,
            "final_equity": self.portfolio.equity,
            "kill_switch_triggered": kill_switch_triggered,
            "ambiguous_exits": ambiguous_exits,
        }

    def _check_exit(self, row, position) -> tuple:
        hit_stop = row.low <= position["stop_price"]
        hit_tp = row.high >= position["take_profit_price"]

        if hit_stop and hit_tp:
            return position["stop_price"], "ambiguous"
        if hit_stop:
            return position["stop_price"], "stop_loss"
        if hit_tp:
            return position["take_profit_price"], "take_profit"

        return None, None

    def calculate_confluence_score(self, row) -> int:
        score = 0

        if self._has_valid_value(row, "relative_strength") and row.relative_strength > 1.05:
            score += 1

        if self._has_valid_value(row, "market_trend") and row.market_trend == "bullish":
            score += 1

        if self._has_valid_value(row, "volatility_regime") and row.volatility_regime != "extreme":
            score += 1

        return score

    def _has_valid_value(self, row, field_name: str) -> bool:
        value = getattr(row, field_name, None)
        return value is not None and not pd.isna(value)
