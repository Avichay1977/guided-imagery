"""
Strategy Variant Framework v1

Each strategy variant is a self-contained object that:
  - declares required feature columns
  - generates a 0/1 entry signal from a feature-enriched DataFrame
  - scores confluence on a signal bar
  - does NOT modify BacktestConfig, FeatureEngine, or risk parameters

Anti-lookahead guarantee: every feature computed inside prepare_features()
and generate_signal() must use only data available at end of bar N-1.
Use .shift(1) on any rolling computation, exactly as FeatureEngine does.

Registered variants
-------------------
BreakoutVolumeConfluence_v1  — original strategy (reference, not re-tested)
TrendPullbackConfluence_v1   — pullback in confirmed uptrend (new candidate)
"""

from abc import ABC, abstractmethod

import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid(row, field: str) -> bool:
    """Return True when row has field and it is not NaN / None."""
    v = getattr(row, field, None)
    return v is not None and not pd.isna(v)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class StrategyVariant(ABC):
    strategy_name: str = ""
    strategy_version: str = ""
    strategy_description: str = ""

    @property
    def required_features(self) -> list[str]:
        """Feature columns that must exist in df before generate_signal()."""
        return []

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add variant-specific features to df.

        Called by Backtester before generate_signal(). Override when the
        variant needs columns not produced by FeatureEngine.

        Must return a DataFrame (may be a copy). Must not use same-bar data
        for any column that will be read during generate_signal() or
        calculate_score().
        """
        return df

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> pd.Series:
        """
        Return a 0/1 integer Series aligned to df.index.

        Contract: must not use current-bar OHLCV for the decision — only
        previously-shifted features that encode data up to bar N-1.
        """

    @abstractmethod
    def calculate_score(self, row) -> int:
        """
        Return confluence score for a bar where generate_signal == 1.

        row is a namedtuple from df.itertuples(); all feature columns are
        accessible as row.<column_name>.
        """

    def describe(self) -> dict:
        return {
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "strategy_description": self.strategy_description,
        }


# ---------------------------------------------------------------------------
# BreakoutVolumeConfluence v1  (reference — mirrors original Backtester logic)
# ---------------------------------------------------------------------------

class BreakoutVolumeConfluence_v1(StrategyVariant):
    """
    Original strategy. Archived as REJECTED_FOR_PORTFOLIO_USE.
    Kept here as reference; do not re-test or select based on prior results.
    """

    strategy_name = "BreakoutVolumeConfluence"
    strategy_version = "v1"
    strategy_description = (
        "Breakout above 20-day high with volume surge (1.5x avg), "
        "price above EMA-200, ATR-based stop, 3R take-profit. "
        "Status: REJECTED_FOR_PORTFOLIO_USE — insufficient OOS trades, "
        "poor OOS calmar robustness, weak randomized timing pass rate."
    )

    @property
    def required_features(self) -> list[str]:
        return ["ema_200", "local_high_20", "volume_avg_20", "atr_14"]

    # prepare_features: FeatureEngine already provides everything — no-op
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        return df

    def generate_signal(self, df: pd.DataFrame) -> pd.Series:
        required_valid = (
            df["ema_200"].notna()
            & df["local_high_20"].notna()
            & df["volume_avg_20"].notna()
            & df["atr_14"].notna()
            & (df["atr_14"] > 0)
        )
        breakout = (
            (df["close"] > df["ema_200"])
            & (df["close"] > df["local_high_20"])
            & (df["volume"] > df["volume_avg_20"] * 1.5)
        )
        return (required_valid & breakout).astype(int)

    def calculate_score(self, row) -> int:
        score = 0
        if _valid(row, "close") and _valid(row, "ema_200") and row.close > row.ema_200:
            score += 1
        if _valid(row, "close") and _valid(row, "local_high_20") and row.close > row.local_high_20:
            score += 1
        if _valid(row, "volume") and _valid(row, "volume_avg_20") and row.volume > row.volume_avg_20 * 1.5:
            score += 1
        if _valid(row, "relative_strength") and row.relative_strength > 1.05:
            score += 1
        if _valid(row, "market_trend") and row.market_trend == "bullish":
            score += 1
        if _valid(row, "volatility_regime") and row.volatility_regime != "extreme":
            score += 1
        return score


# ---------------------------------------------------------------------------
# TrendPullbackConfluence v1  (new candidate)
# ---------------------------------------------------------------------------

class TrendPullbackConfluence_v1(StrategyVariant):
    """
    Pullback entry in a confirmed uptrend.

    Entry logic (all conditions use features shifted to end-of-prior-bar):
      1. market_trend == "bullish"  (ema_50 > ema_200, both shifted)
      2. close > ema_200            (price above long-term trend)
      3. Pullback: close > ema_50 AND close < local_high_{recent_high_window}
         OR abs(close - ema_50) <= atr_14 * pullback_distance_atr
      4. volatility_regime != "extreme"
      5. atr_14 > 0

    Confluence scoring (max 6, threshold unchanged: min_confluence_score=5):
      +1 close > ema_200
      +1 market_trend == "bullish"
      +1 volatility_regime != "extreme"
      +1 close > ema_50           (confirms price in upper half of trend)
      +1 close < local_high_10    (confirms pullback, not chasing)
      +1 close within 0.5 ATR of ema_50  (tight pullback bonus)
    """

    strategy_name = "TrendPullbackConfluence"
    strategy_version = "v1"
    strategy_description = (
        "Pullback entry in confirmed uptrend (ema_50 > ema_200). "
        "Enters when price retraces toward ema_50 while remaining above it, "
        "in a normal volatility regime. ATR-based stop, 3R take-profit."
    )

    pullback_distance_atr: float = 1.0
    recent_high_window: int = 10

    @property
    def required_features(self) -> list[str]:
        return [
            "ema_200", "ema_50", "market_trend",
            "volatility_regime", "atr_14",
        ]

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add local_high_10 (10-bar rolling high, shifted 1 bar)."""
        df = df.copy()
        df["local_high_10"] = (
            df["high"]
            .rolling(self.recent_high_window, min_periods=self.recent_high_window)
            .max()
            .shift(1)
        )
        return df

    def generate_signal(self, df: pd.DataFrame) -> pd.Series:
        required_valid = (
            df["ema_200"].notna()
            & df["ema_50"].notna()
            & df["atr_14"].notna()
            & (df["atr_14"] > 0)
            & df["market_trend"].notna()
            & df["volatility_regime"].notna()
            & df["local_high_10"].notna()
        )

        in_uptrend = (
            (df["market_trend"] == "bullish")
            & (df["close"] > df["ema_200"])
        )

        # Pullback: price in uptrend but not at new recent high
        above_ema50_below_high = (
            (df["close"] > df["ema_50"])
            & (df["close"] < df["local_high_10"])
        )
        # OR: within 1 ATR of ema_50 (tight pullback, may be slightly below ema_50)
        near_ema50 = (
            (df["close"] - df["ema_50"]).abs() <= df["atr_14"] * self.pullback_distance_atr
        )
        pullback = above_ema50_below_high | near_ema50

        not_extreme = df["volatility_regime"] != "extreme"

        return (required_valid & in_uptrend & pullback & not_extreme).astype(int)

    def calculate_score(self, row) -> int:
        score = 0

        if _valid(row, "close") and _valid(row, "ema_200") and row.close > row.ema_200:
            score += 1

        if _valid(row, "market_trend") and row.market_trend == "bullish":
            score += 1

        if _valid(row, "volatility_regime") and row.volatility_regime != "extreme":
            score += 1

        if _valid(row, "close") and _valid(row, "ema_50") and row.close > row.ema_50:
            score += 1

        if _valid(row, "close") and _valid(row, "local_high_10") and row.close < row.local_high_10:
            score += 1

        # Tight pullback bonus: within 0.5 ATR of ema_50
        if (
            _valid(row, "close")
            and _valid(row, "ema_50")
            and _valid(row, "atr_14")
            and row.atr_14 > 0
            and abs(row.close - row.ema_50) <= row.atr_14 * 0.5
        ):
            score += 1

        return score


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

REGISTRY: dict[str, type[StrategyVariant]] = {
    "BreakoutVolumeConfluence_v1": BreakoutVolumeConfluence_v1,
    "TrendPullbackConfluence_v1": TrendPullbackConfluence_v1,
}


def get_variant(name: str) -> StrategyVariant:
    """Instantiate a registered strategy variant by name."""
    if name not in REGISTRY:
        raise ValueError(
            f"Unknown strategy variant: {name!r}. "
            f"Available: {sorted(REGISTRY)}"
        )
    return REGISTRY[name]()
