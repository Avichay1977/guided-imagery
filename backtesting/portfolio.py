class PortfolioTracker:
    def __init__(self, initial_cash: float):
        self.cash = initial_cash
        self._position_value = 0.0

    @property
    def equity(self) -> float:
        return self.cash + self._position_value

    def update_position_value(self, shares: float, current_price: float):
        self._position_value = shares * current_price
