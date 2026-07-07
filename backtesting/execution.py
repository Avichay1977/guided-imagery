class ExecutionSimulator:
    def __init__(self, slippage_pct: float = 0.0005, fixed_fee: float = 0.0):
        self.slippage_pct = slippage_pct
        self.fixed_fee = fixed_fee

    def apply_slippage(self, price: float, direction: str = "buy") -> float:
        if direction == "buy":
            return price * (1 + self.slippage_pct)
        return price * (1 - self.slippage_pct)

    def open_position(
        self,
        portfolio,
        entry_price: float,
        entry_time,
        shares: float,
        stop_price: float,
        take_profit_price: float,
        confluence_score: int,
    ) -> dict | None:
        cost = shares * entry_price + self.fixed_fee
        if cost > portfolio.cash:
            shares = (portfolio.cash - self.fixed_fee) / entry_price
        if shares <= 0:
            return None

        portfolio.cash -= shares * entry_price + self.fixed_fee
        portfolio._position_value = shares * entry_price

        return {
            "entry_time": entry_time,
            "entry_price": entry_price,
            "shares": shares,
            "stop_price": stop_price,
            "take_profit_price": take_profit_price,
            "confluence_score": confluence_score,
        }

    def close_position(
        self,
        portfolio,
        position: dict,
        exit_price: float,
        exit_time,
        exit_reason: str,
    ) -> dict:
        exit_price_adj = self.apply_slippage(exit_price, direction="sell")
        gross_proceeds = position["shares"] * exit_price_adj
        net_proceeds = gross_proceeds - self.fixed_fee
        portfolio.cash += net_proceeds
        portfolio._position_value = 0.0

        entry_cost = position["shares"] * position["entry_price"] + self.fixed_fee
        pnl = net_proceeds - entry_cost

        return {
            "entry_time": position["entry_time"],
            "exit_time": exit_time,
            "entry_price": position["entry_price"],
            "exit_price": exit_price_adj,
            "stop_price": position["stop_price"],
            "take_profit_price": position["take_profit_price"],
            "shares": position["shares"],
            "pnl": pnl,
            "exit_reason": exit_reason,
            "confluence_score": position["confluence_score"],
        }
