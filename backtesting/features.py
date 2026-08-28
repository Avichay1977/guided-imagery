import pandas as pd


class FeatureEngine:
    """
    Transforms raw OHLCV data into shifted technical features.

    Anti-lookahead guarantee: every feature column for bar N
    depends only on bars 0..N-1.  This is achieved by computing
    each indicator on the full series and then calling .shift(1).

    Core features (required for signal):
        ema_200, local_high_20, volume_avg_20, atr_14, signal

    Optional context features (used by confluence score):
        ema_50, market_trend, atr_pct, volatility_regime
    """

    def __init__(self) -> None:
        pass

    def generate_shifted_features(
        self,
        df: pd.DataFrame,
        drop_warmup: bool = False,
    ) -> pd.DataFrame:
        """
        Parameters
        ----------
        df : DataFrame with columns open, high, low, close, volume.
        drop_warmup : if True, drop rows where any required core feature is NaN.
                      Default False — warm-up rows are kept with NaN features
                      and signal=0.

        Returns
        -------
        New DataFrame (input is not mutated) with all original columns plus
        ema_200, local_high_20, volume_avg_20, atr_14, ema_50,
        market_trend, atr_pct, volatility_regime, signal.
        """
        df = df.copy()

        # --- Core features ---

        raw_ema_200 = df["close"].ewm(span=200, adjust=False, min_periods=200).mean()
        df["ema_200"] = raw_ema_200.shift(1)

        df["local_high_20"] = (
            df["high"].rolling(20, min_periods=20).max().shift(1)
        )

        df["volume_avg_20"] = (
            df["volume"].rolling(20, min_periods=20).mean().shift(1)
        )

        df["atr_14"] = self._compute_atr(df).shift(1)

        # --- Optional context features ---

        raw_ema_50 = df["close"].ewm(span=50, adjust=False, min_periods=50).mean()
        df["ema_50"] = raw_ema_50.shift(1)

        # market_trend: "bullish" when shifted ema_50 > shifted ema_200
        # NaN comparisons evaluate to False → "neutral" during warmup
        df["market_trend"] = self._compute_market_trend(df)

        # atr_pct: atr_14 / previous close — both are already prior-bar values
        df["atr_pct"] = df["atr_14"] / df["close"].shift(1)

        # volatility_regime: "extreme" if atr_pct exceeds shifted rolling 90th percentile
        df["volatility_regime"] = self._compute_volatility_regime(df)

        # --- Signal ---
        df["signal"] = self._compute_signal(df)

        if drop_warmup:
            required = ["ema_200", "local_high_20", "volume_avg_20", "atr_14"]
            mask = df[required].notna().all(axis=1)
            df = df.loc[mask].copy()

        return df

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_atr(self, df: pd.DataFrame) -> pd.Series:
        prev_close = df["close"].shift(1)
        tr = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - prev_close).abs(),
                (df["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.rolling(14, min_periods=14).mean()

    def _compute_market_trend(self, df: pd.DataFrame) -> pd.Series:
        # Both ema_50 and ema_200 are already shifted — strictly anti-lookahead.
        # Pandas NaN comparisons evaluate to False, so warmup rows stay "neutral".
        trend = pd.Series("neutral", index=df.index)
        bullish = (
            df["ema_50"].notna()
            & df["ema_200"].notna()
            & (df["ema_50"] > df["ema_200"])
        )
        trend[bullish] = "bullish"
        return trend

    def _compute_volatility_regime(self, df: pd.DataFrame) -> pd.Series:
        # Rolling 252-day 90th percentile of atr_pct, then shift(1).
        # shift(1) ensures bar N compares against a threshold built from bars 0..N-2.
        raw_threshold = (
            df["atr_pct"]
            .rolling(252, min_periods=252)
            .quantile(0.90)
        )
        shifted_threshold = raw_threshold.shift(1)

        regime = pd.Series("normal", index=df.index)
        extreme = (
            df["atr_pct"].notna()
            & shifted_threshold.notna()
            & (df["atr_pct"] > shifted_threshold)
        )
        regime[extreme] = "extreme"
        return regime

    def _compute_signal(self, df: pd.DataFrame) -> pd.Series:
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
