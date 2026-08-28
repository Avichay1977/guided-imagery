"""
Rotation feature-matrix builder for RelativeStrengthRotation_v1.

Computes the cross-sectional, shifted, no-lookahead features that the rotation
strategy ranks on. SCAFFOLD-LEVEL feature computation only — no backtest, no
runner, no market-data fetch.

Feature integrity (frozen by the spec §8/§9):
  - Every decision feature is shifted by 1 bar. For date T, a feature may only
    consume information from bars up to T-1. No same-bar lookahead.
  - No forward-fill, back-fill, or interpolation of decision-time features.
  - NaN / inf are surfaced as invalid (the row becomes ineligible); they are
    never silently repaired.

Two distinct equal-weight references are built so the spec's separation of
relative_strength_252d and benchmark_relative_strength is preserved (spec §8
explicitly forbids collapsing the two):
  - universe_index   : daily-rebalanced equal-weight RETURN index
                       (denominator of relative_strength_{63,126,252})
  - benchmark_index  : equal-weight BUY-AND-HOLD index
                       (denominator of benchmark_relative_strength)

No market-data-fetch library is imported. No Backtester is imported.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class RotationFeatureConfig:
    rs_short_window: int = 63
    rs_mid_window: int = 126
    rs_long_window: int = 252
    ema_window: int = 200
    atr_window: int = 14
    volume_window: int = 20
    volatility_atr_pct_max: float = 0.08
    liquidity_volume_avg_20_min: float = 1_000_000
    require_shifted_features: bool = True


REQUIRED_OHLCV = ("open", "high", "low", "close", "volume")

FEATURE_COLUMNS = (
    "relative_strength_63d",
    "relative_strength_126d",
    "relative_strength_252d",
    "benchmark_relative_strength",
    "trend_filter_ema200",
    "volatility_filter_atr_pct",
    "liquidity_filter_volume_avg_20",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_ohlcv(ticker: str, df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_OHLCV if c not in df.columns]
    if missing:
        raise ValueError(
            f"universe_data[{ticker!r}] missing OHLCV columns: {missing}"
        )


def _aligned_series(series: pd.Series, index: pd.Index) -> pd.Series:
    """Reindex a reference series onto a ticker's date index (no fill)."""
    return series.reindex(index)


# ---------------------------------------------------------------------------
# Equal-weight references
# ---------------------------------------------------------------------------

def build_equal_weight_universe_index(
    universe_data: "dict[str, pd.DataFrame]",
) -> pd.Series:
    """
    Daily-rebalanced equal-weight RETURN index across the universe.

    Uses close-to-close simple returns, equal weights across the tickers that
    have data on each date. Index level starts at 1.0. Deterministic.
    """
    if not isinstance(universe_data, dict) or not universe_data:
        raise ValueError("universe_data must be a non-empty dict of ticker -> DataFrame.")

    closes = {}
    for ticker, df in universe_data.items():
        if "close" not in df.columns:
            raise ValueError(f"universe_data[{ticker!r}] missing 'close' column.")
        closes[ticker] = df["close"]

    close_frame = pd.DataFrame(closes).sort_index()
    returns = close_frame.pct_change()
    # equal weight across available (non-NaN) tickers per date
    port_return = returns.mean(axis=1, skipna=True)
    # anchor: first row has no prior bar -> 0 return (set explicitly, no fillna)
    if len(port_return) > 0:
        port_return.iloc[0] = 0.0
    index = (1.0 + port_return).cumprod()
    if len(index) > 0:
        index.iloc[0] = 1.0
    index.name = "equal_weight_universe_index"
    return index


def build_equal_weight_buy_hold_index(
    universe_data: "dict[str, pd.DataFrame]",
) -> pd.Series:
    """
    Equal-weight BUY-AND-HOLD index (no rebalancing).

    Each ticker's close is normalized to its first valid value, then averaged
    equally across tickers. Distinct from the rebalanced return index above —
    this is the B1-style aggregate used to normalize benchmark_relative_strength.
    """
    if not isinstance(universe_data, dict) or not universe_data:
        raise ValueError("universe_data must be a non-empty dict of ticker -> DataFrame.")

    normalized = {}
    for ticker, df in universe_data.items():
        close = df["close"]
        first_idx = close.first_valid_index()
        if first_idx is None:
            continue
        base = close.loc[first_idx]
        normalized[ticker] = close / base

    norm_frame = pd.DataFrame(normalized).sort_index()
    bh_index = norm_frame.mean(axis=1, skipna=True)
    bh_index.name = "equal_weight_buy_hold_index"
    return bh_index


# ---------------------------------------------------------------------------
# Per-ticker features
# ---------------------------------------------------------------------------

def compute_rotation_features_for_ticker(
    ticker: str,
    df: pd.DataFrame,
    universe_index: pd.Series,
    config: Optional[RotationFeatureConfig] = None,
    benchmark_index: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """
    Compute shifted, no-lookahead rotation features for one ticker.

    All decision features are shifted by 1: the value at date T uses only data
    through T-1. NaN / inf are never repaired.

    benchmark_index : optional equal-weight buy-and-hold reference. When None,
        falls back to universe_index (keeps direct unit tests self-contained).
    """
    cfg = config or RotationFeatureConfig()
    _require_ohlcv(ticker, df)

    df = df.sort_index()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    U = _aligned_series(universe_index, df.index)
    B = _aligned_series(
        benchmark_index if benchmark_index is not None else universe_index,
        df.index,
    )

    def _rs(window: int) -> pd.Series:
        t_ratio = close.shift(1) / close.shift(window + 1)
        u_ratio = U.shift(1) / U.shift(window + 1)
        return t_ratio / u_ratio

    rs_63 = _rs(cfg.rs_short_window)
    rs_126 = _rs(cfg.rs_mid_window)
    rs_252 = _rs(cfg.rs_long_window)

    # benchmark_relative_strength: ticker 252d return vs buy-and-hold aggregate
    w = cfg.rs_long_window
    bench_t_ratio = close.shift(1) / close.shift(w + 1)
    bench_b_ratio = B.shift(1) / B.shift(w + 1)
    benchmark_rs = bench_t_ratio / bench_b_ratio

    # trend filter: prior close above prior EMA200
    ema = close.ewm(span=cfg.ema_window, adjust=False).mean()
    trend_filter = close.shift(1) > ema.shift(1)

    # volatility filter: prior ATR% <= threshold
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = true_range.rolling(cfg.atr_window, min_periods=cfg.atr_window).mean()
    atr_pct = atr.shift(1) / close.shift(1)
    volatility_filter = atr_pct <= cfg.volatility_atr_pct_max

    # liquidity filter: prior 20-bar avg volume >= floor
    vol_avg = volume.rolling(cfg.volume_window, min_periods=cfg.volume_window).mean()
    liquidity_filter = vol_avg.shift(1) >= cfg.liquidity_volume_avg_20_min

    out = pd.DataFrame(
        {
            "ticker": ticker,
            "relative_strength_63d": rs_63,
            "relative_strength_126d": rs_126,
            "relative_strength_252d": rs_252,
            "benchmark_relative_strength": benchmark_rs,
            "trend_filter_ema200": trend_filter.astype(bool),
            "volatility_filter_atr_pct": volatility_filter.astype(bool),
            "liquidity_filter_volume_avg_20": liquidity_filter.astype(bool),
        },
        index=df.index,
    )
    return out


# ---------------------------------------------------------------------------
# Long matrix across the universe
# ---------------------------------------------------------------------------

def build_rotation_feature_matrix(
    universe_data: "dict[str, pd.DataFrame]",
    config: Optional[RotationFeatureConfig] = None,
) -> pd.DataFrame:
    """
    Build a long feature matrix (one row per date per ticker).

    Columns: date, ticker, + the 7 feature columns. Ranking is NOT performed
    here — call add_cross_sectional_ranks() once all tickers are present.
    """
    cfg = config or RotationFeatureConfig()
    if not isinstance(universe_data, dict) or not universe_data:
        raise ValueError("universe_data must be a non-empty dict of ticker -> DataFrame.")
    for ticker, df in universe_data.items():
        _require_ohlcv(ticker, df)

    universe_index = build_equal_weight_universe_index(universe_data)
    benchmark_index = build_equal_weight_buy_hold_index(universe_data)

    frames = []
    for ticker in sorted(universe_data):
        feats = compute_rotation_features_for_ticker(
            ticker, universe_data[ticker], universe_index, cfg, benchmark_index
        )
        feats = feats.reset_index()
        feats = feats.rename(columns={feats.columns[0]: "date"})
        frames.append(feats)

    matrix = pd.concat(frames, ignore_index=True)
    matrix = matrix.sort_values(["date", "ticker"]).reset_index(drop=True)
    return matrix


# ---------------------------------------------------------------------------
# Cross-sectional ranking
# ---------------------------------------------------------------------------

def _is_finite_col(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return np.isfinite(numeric.to_numpy(dtype="float64", na_value=np.nan))


def add_cross_sectional_ranks(
    feature_matrix: pd.DataFrame,
    config: Optional[RotationFeatureConfig] = None,
) -> pd.DataFrame:
    """
    Add per-date cross-sectional composite score and rank percentile.

    Eligibility requires finite RS_126 / RS_252 / benchmark_RS AND all three
    filters True. composite_rs = 0.40*rank(RS126) + 0.40*rank(RS252)
    + 0.20*rank(benchmark_RS), ranks taken within the eligible set per date.
    Invalid rows receive NaN composite/rank and is_rotation_eligible = False.
    Output is sorted by date, then composite_rs descending, then ticker
    ascending (ties broken by ticker).
    """
    cfg = config or RotationFeatureConfig()
    out = feature_matrix.copy()

    finite = (
        _is_finite_col(out["relative_strength_126d"])
        & _is_finite_col(out["relative_strength_252d"])
        & _is_finite_col(out["benchmark_relative_strength"])
    )
    eligible = (
        finite
        & out["trend_filter_ema200"].astype(bool)
        & out["volatility_filter_atr_pct"].astype(bool)
        & out["liquidity_filter_volume_avg_20"].astype(bool)
    )
    out["is_rotation_eligible"] = eligible.to_numpy()
    out["composite_rs"] = np.nan
    out["rank_percentile"] = np.nan

    for _, idx in out.groupby("date").groups.items():
        rows = out.loc[idx]
        elig_idx = rows.index[rows["is_rotation_eligible"].to_numpy()]
        if len(elig_idx) == 0:
            continue
        e = out.loc[elig_idx]
        r126 = e["relative_strength_126d"].rank(pct=True, method="average")
        r252 = e["relative_strength_252d"].rank(pct=True, method="average")
        rb = e["benchmark_relative_strength"].rank(pct=True, method="average")
        composite = 0.40 * r126 + 0.40 * r252 + 0.20 * rb
        out.loc[elig_idx, "composite_rs"] = composite
        out.loc[elig_idx, "rank_percentile"] = composite.rank(pct=True, method="average")

    out = out.sort_values(
        ["date", "composite_rs", "ticker"],
        ascending=[True, False, True],
        na_position="last",
    ).reset_index(drop=True)
    return out
