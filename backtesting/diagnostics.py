import pandas as pd


class SignalDiagnostics:
    """
    Funnel analysis: counts how many rows survive each filter stage.

    Reproduces Backtester.calculate_confluence_score logic vectorized
    so results are directly comparable to actual trade triggers.

    Does not execute trades and does not modify the DataFrame.
    """

    def analyze_feature_funnel(
        self,
        df: pd.DataFrame,
        min_confluence_score: int = 5,
    ) -> dict:
        """
        Parameters
        ----------
        df : DataFrame after FeatureEngine.generate_shifted_features().
        min_confluence_score : score threshold used by the Backtester.

        Returns
        -------
        dict — see class docstring for field list.
        """
        total_rows = len(df)

        # ---------------------------------------------------------------
        # Core feature validity (ema warmup exclusion)
        # ---------------------------------------------------------------
        core_cols = ["ema_200", "local_high_20", "volume_avg_20", "atr_14"]
        present_core = [c for c in core_cols if c in df.columns]
        core_valid_mask = df[present_core].notna().all(axis=1) if present_core else pd.Series(False, index=df.index)
        rows_with_valid_core_features = int(core_valid_mask.sum())

        rows_with_valid_atr = 0
        if "atr_14" in df.columns:
            rows_with_valid_atr = int((df["atr_14"].notna() & (df["atr_14"] > 0)).sum())

        # All subsequent analysis only over valid-core rows
        vdf = df.loc[core_valid_mask]
        n_valid = len(vdf)

        def _rate(count: int) -> float:
            return round(count / n_valid * 100, 2) if n_valid > 0 else 0.0

        # ---------------------------------------------------------------
        # Per-condition counts  (denominator = valid-core rows)
        # ---------------------------------------------------------------
        condition_counts: dict = {}
        condition_rates_pct: dict = {}

        def _add_cond(name: str, mask: pd.Series) -> None:
            c = int(mask.sum())
            condition_counts[name] = c
            condition_rates_pct[name] = _rate(c)

        if "ema_200" in vdf.columns:
            _add_cond("close_above_ema_200", vdf["close"] > vdf["ema_200"])

        if "local_high_20" in vdf.columns:
            _add_cond("close_above_local_high_20", vdf["close"] > vdf["local_high_20"])

        if "volume_avg_20" in vdf.columns:
            _add_cond("volume_above_1_5x_avg", vdf["volume"] > vdf["volume_avg_20"] * 1.5)

        if "atr_14" in vdf.columns:
            _add_cond("atr_valid_positive", vdf["atr_14"].notna() & (vdf["atr_14"] > 0))

        if "market_trend" in vdf.columns:
            _add_cond(
                "market_trend_bullish",
                vdf["market_trend"].notna() & (vdf["market_trend"] == "bullish"),
            )

        if "volatility_regime" in vdf.columns:
            _add_cond(
                "volatility_regime_not_extreme",
                vdf["volatility_regime"].notna() & (vdf["volatility_regime"] != "extreme"),
            )

        if "relative_strength" in vdf.columns:
            _add_cond(
                "relative_strength_above_1_05",
                vdf["relative_strength"].notna() & (vdf["relative_strength"] > 1.05),
            )

        # ---------------------------------------------------------------
        # Score distribution (vectorized confluence scoring)
        # ---------------------------------------------------------------
        scores = self._compute_scores(vdf)
        score_distribution = {s: int((scores == s).sum()) for s in range(7)}

        # ---------------------------------------------------------------
        # Signal & min-score counts
        # ---------------------------------------------------------------
        signal_count = int(vdf["signal"].sum()) if "signal" in vdf.columns else 0
        signal_rate_pct = _rate(signal_count)

        rows_reaching_min_score = int((scores >= min_confluence_score).sum())
        min_score_rate_pct = _rate(rows_reaching_min_score)

        # ---------------------------------------------------------------
        # Bottleneck detection
        # ---------------------------------------------------------------
        bottlenecks = self._detect_bottlenecks(
            signal_count=signal_count,
            rows_reaching_min_score=rows_reaching_min_score,
            condition_rates_pct=condition_rates_pct,
        )

        warnings: list[str] = []
        if n_valid == 0:
            warnings.append("All rows are in warmup period — no valid core features")

        return {
            "total_rows": total_rows,
            "rows_with_valid_core_features": rows_with_valid_core_features,
            "rows_with_valid_atr": rows_with_valid_atr,
            "condition_counts": condition_counts,
            "condition_rates_pct": condition_rates_pct,
            "score_distribution": score_distribution,
            "signal_count": signal_count,
            "signal_rate_pct": signal_rate_pct,
            "rows_reaching_min_score": rows_reaching_min_score,
            "min_score_rate_pct": min_score_rate_pct,
            "bottlenecks": bottlenecks,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_scores(self, df: pd.DataFrame) -> pd.Series:
        """Vectorized replica of Backtester.calculate_confluence_score."""
        score = pd.Series(0, index=df.index, dtype=int)

        # Technical (max 3)
        if "ema_200" in df.columns:
            score += (df["close"] > df["ema_200"]).fillna(False).astype(int)
        if "local_high_20" in df.columns:
            score += (df["close"] > df["local_high_20"]).fillna(False).astype(int)
        if "volume_avg_20" in df.columns:
            score += (df["volume"] > df["volume_avg_20"] * 1.5).fillna(False).astype(int)

        # Optional context (max 3, NaN-safe)
        if "relative_strength" in df.columns:
            valid = df["relative_strength"].notna()
            score += (valid & (df["relative_strength"] > 1.05)).astype(int)

        if "market_trend" in df.columns:
            valid = df["market_trend"].notna()
            score += (valid & (df["market_trend"] == "bullish")).astype(int)

        if "volatility_regime" in df.columns:
            valid = df["volatility_regime"].notna()
            score += (valid & (df["volatility_regime"] != "extreme")).astype(int)

        return score

    def _detect_bottlenecks(
        self,
        signal_count: int,
        rows_reaching_min_score: int,
        condition_rates_pct: dict,
    ) -> list[str]:
        bottlenecks: list[str] = []

        if signal_count == 0:
            bottlenecks.append("NO_SIGNALS: signal column is all zeros")

        if rows_reaching_min_score < 30:
            bottlenecks.append(
                f"LOW_SIGNAL_SAMPLE: {rows_reaching_min_score} rows reach min_confluence_score (< 30)"
            )

        vol_rate = condition_rates_pct.get("volume_above_1_5x_avg", 100.0)
        if vol_rate < 5.0:
            bottlenecks.append(
                f"VOLUME_FILTER_TOO_RESTRICTIVE: volume_above_1_5x_avg = {vol_rate:.1f}% (< 5%)"
            )

        breakout_rate = condition_rates_pct.get("close_above_local_high_20", 100.0)
        if breakout_rate < 5.0:
            bottlenecks.append(
                f"BREAKOUT_FILTER_TOO_RESTRICTIVE: close_above_local_high_20 = {breakout_rate:.1f}% (< 5%)"
            )

        trend_rate = condition_rates_pct.get("market_trend_bullish")
        if trend_rate is not None and trend_rate < 20.0:
            bottlenecks.append(
                f"MARKET_TREND_FILTER_TOO_RESTRICTIVE: market_trend_bullish = {trend_rate:.1f}% (< 20%)"
            )

        vol_reg_rate = condition_rates_pct.get("volatility_regime_not_extreme")
        if vol_reg_rate is not None and vol_reg_rate < 20.0:
            bottlenecks.append(
                f"VOLATILITY_FILTER_TOO_RESTRICTIVE: volatility_regime_not_extreme = {vol_reg_rate:.1f}% (< 20%)"
            )

        return bottlenecks
