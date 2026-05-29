import pandas as pd


class FeatureEngine:
    """
    Transforms raw OHLCV data into shifted technical features.

    Anti-lookahead guarantee: every feature column for bar N
    depends only on bars 0..N-1.  This is achieved by computing
    each indicator on the full series and then calling .shift(1).

    Output columns added to the input DataFrame:
        ema_200       — shifted 200-period EMA of close
        local_high_20 — shifted 20-period rolling max of high
        volume_avg_20 — shifted 20-period rolling mean of volume
        atr_14        — shifted 14-period Average True Range
        signal        — 1 when all four breakout conditions hold, else 0
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
        drop_warmup : if True, drop rows where any required feature is NaN.
                      Default False — warm-up rows are kept with NaN features
                      and signal=0.

        Returns
        -------
        New DataFrame (input is not mutated) with all original columns plus
        ema_200, local_high_20, volume_avg_20, atr_14, signal.
        """
        df = df.copy()

        # ema_200: raw EWM computed with min_periods=200, then shift(1)
        raw_ema = df["close"].ewm(span=200, adjust=False, min_periods=200).mean()
        df["ema_200"] = raw_ema.shift(1)

        # local_high_20: rolling 20-bar max of high, shift(1)
        df["local_high_20"] = (
            df["high"].rolling(20, min_periods=20).max().shift(1)
        )

        # volume_avg_20: rolling 20-bar mean of volume, shift(1)
        df["volume_avg_20"] = (
            df["volume"].rolling(20, min_periods=20).mean().shift(1)
        )

        # atr_14: 14-period mean of True Range, shift(1)
        df["atr_14"] = self._compute_atr(df).shift(1)

        # signal: 1 iff all four breakout conditions are met
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
