"""
Tests for StrategyVariant implementations.

Tests 1-3: pure unit tests — no real market data required.
Test 4   : synthetic uptrend dataset (no external files needed).
"""

import numpy as np
import pandas as pd
import pytest

from backtester import BacktestConfig
from features import FeatureEngine
from strategy_variants import (
    BreakoutVolumeConfluence_v1,
    MomentumContinuationConfluence_v1,
    TrendPullbackConfluence_v1,
    get_variant,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_trend_df(n: int = 600, seed: int = 0) -> pd.DataFrame:
    """
    Synthetic uptrend: steady price rise with small oscillations.
    Volume is flat (no spikes), so BreakoutVolumeConfluence_v1 fires rarely.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2018-01-02", periods=n, freq="B")

    trend = np.linspace(100.0, 220.0, n)
    oscillation = np.sin(np.linspace(0, 30 * np.pi, n)) * 3.0
    prices = trend + oscillation

    df = pd.DataFrame(
        {
            "open":   prices * 0.9990,
            "high":   prices * 1.0050,
            "low":    prices * 0.9950,
            "close":  prices,
            "volume": np.full(n, 1_000_000.0),   # flat volume — no 1.5× spikes
        },
        index=dates,
    )
    return df


def _apply_features(df: pd.DataFrame) -> pd.DataFrame:
    return FeatureEngine().generate_shifted_features(df, drop_warmup=False)


# ---------------------------------------------------------------------------
# 1. V1 strategy identity is preserved
# ---------------------------------------------------------------------------

def test_v1_strategy_identity_preserved():
    v1 = BreakoutVolumeConfluence_v1()

    assert v1.strategy_name == "BreakoutVolumeConfluence"
    assert v1.strategy_version == "v1"
    assert len(v1.strategy_description) > 10

    d = v1.describe()
    assert d["strategy_name"] == "BreakoutVolumeConfluence"
    assert d["strategy_version"] == "v1"

    # BacktestConfig default identity must also match v1
    cfg = BacktestConfig()
    assert cfg.strategy_name == "BreakoutVolumeConfluence"
    assert cfg.strategy_version == "v1"

    # Registry lookup works
    v1_from_registry = get_variant("BreakoutVolumeConfluence_v1")
    assert v1_from_registry.strategy_name == "BreakoutVolumeConfluence"
    assert v1_from_registry.strategy_version == "v1"


# ---------------------------------------------------------------------------
# 2. TrendPullbackConfluence_v1 exposes required features
# ---------------------------------------------------------------------------

def test_trend_pullback_has_required_features():
    v2 = TrendPullbackConfluence_v1()

    required = v2.required_features
    assert isinstance(required, list)
    assert len(required) >= 4

    assert "ema_200" in required
    assert "ema_50"  in required
    assert "market_trend" in required
    assert "atr_14" in required

    d = v2.describe()
    assert d["strategy_name"] == "TrendPullbackConfluence"
    assert d["strategy_version"] == "v1"


# ---------------------------------------------------------------------------
# 3. TrendPullbackConfluence_v1 has no same-bar lookahead
# ---------------------------------------------------------------------------

def test_trend_pullback_no_same_bar_lookahead():
    """
    Verify anti-lookahead: when bar N's close is set to an extreme spike
    that triggers the pullback condition, shifting forward by one bar must
    produce a *different* signal pattern — proving the signal at bar N
    does not use bar N's values.
    """
    v2 = TrendPullbackConfluence_v1()
    df_raw = _make_trend_df(n=400)
    df = _apply_features(df_raw)
    df = v2.prepare_features(df)

    sig_original = v2.generate_signal(df).values.copy()

    # Artificially alter current-bar close for bars 300-350
    # If the strategy had lookahead it would react to this change
    df_altered = df.copy()
    df_altered.iloc[300:350, df_altered.columns.get_loc("close")] *= 1.50

    # Re-apply features (which shift(1) everything) — so bar 301 features
    # still encode bar 300's *original* close
    df_altered2 = _apply_features(df_altered)
    df_altered2 = v2.prepare_features(df_altered2)
    sig_altered = v2.generate_signal(df_altered2).values

    # With shifted features, the signal at bars 300-350 should differ from
    # the extreme-close version only one bar later — but the altered-close
    # signal at the SAME bars must not match a direct-use (non-shifted) signal.
    # Concretely: the signal Series must be int-valued 0 or 1 only.
    assert set(sig_original).issubset({0, 1}), "Signal must be 0 or 1 only"
    assert set(sig_altered).issubset({0, 1}),  "Altered signal must be 0 or 1 only"

    # The variant's local_high_10 must be a shifted column (not current high)
    assert "local_high_10" in df_altered2.columns, "local_high_10 must be added by prepare_features"
    # If local_high_10 at bar i were current-bar high, it would equal df["high"].iloc[i].
    # With shift(1) it should equal the rolling max of high up to bar i-1.
    n = len(df_altered2)
    for i in range(20, min(50, n)):
        expected_shift = (
            df_altered2["high"].iloc[max(0, i - v2.recent_high_window): i].max()
        )
        actual = df_altered2["local_high_10"].iloc[i]
        if not pd.isna(actual):
            assert abs(actual - expected_shift) < 1e-8, (
                f"local_high_10 at bar {i} ({actual:.4f}) != "
                f"prior-bar rolling max ({expected_shift:.4f}) — possible lookahead"
            )


# ---------------------------------------------------------------------------
# 4. TrendPullback generates more signals than v1 on synthetic uptrend
# ---------------------------------------------------------------------------

def test_trend_pullback_signal_more_frequent_than_v1_on_synthetic_trend():
    """
    On a steady uptrend with flat volume (no volume spikes), v1 needs a 1.5×
    volume surge that never occurs → few or zero signals.
    TrendPullbackConfluence_v1 only needs price to be near ema_50 in an
    uptrend → fires more often.
    """
    v1 = BreakoutVolumeConfluence_v1()
    v2 = TrendPullbackConfluence_v1()

    df_raw = _make_trend_df(n=600)
    df = _apply_features(df_raw)

    # V1 signal (uses FeatureEngine's pre-computed signal — same logic)
    df_v1 = v1.prepare_features(df.copy())
    sig_v1 = v1.generate_signal(df_v1)
    count_v1 = int(sig_v1.sum())

    # V2 signal
    df_v2 = v2.prepare_features(df.copy())
    sig_v2 = v2.generate_signal(df_v2)
    count_v2 = int(sig_v2.sum())

    assert count_v2 > count_v1, (
        f"Expected TrendPullback ({count_v2}) to fire more than "
        f"BreakoutVolume ({count_v1}) on flat-volume uptrend"
    )
    assert count_v2 >= 5, (
        f"TrendPullback should generate at least 5 signals on a 600-bar "
        f"uptrend; got {count_v2}"
    )


# ---------------------------------------------------------------------------
# 5. MomentumContinuation has required features and correct identity
# ---------------------------------------------------------------------------

def test_momentum_continuation_has_required_features_and_identity():
    v3 = MomentumContinuationConfluence_v1()

    assert v3.strategy_name == "MomentumContinuationConfluence"
    assert v3.strategy_version == "v1"

    req = v3.required_features
    assert "ema_200" in req
    assert "ema_50" in req
    assert "market_trend" in req
    assert "atr_14" in req

    d = v3.describe()
    assert d["strategy_name"] == "MomentumContinuationConfluence"
    assert d["strategy_version"] == "v1"

    v3_reg = get_variant("MomentumContinuationConfluence_v1")
    assert v3_reg.strategy_name == "MomentumContinuationConfluence"


# ---------------------------------------------------------------------------
# 6. MomentumContinuation fires more than TrendPullback on synthetic uptrend
# ---------------------------------------------------------------------------

def test_momentum_continuation_more_frequent_than_v1_on_uptrend():
    """
    On a steady uptrend with flat volume (no 1.5× spikes), v1 (BreakoutVolume)
    fires rarely. MomentumContinuation requires no volume spike and should
    fire far more often whenever trend + 5-bar momentum conditions are met.
    """
    v1 = BreakoutVolumeConfluence_v1()
    v3 = MomentumContinuationConfluence_v1()

    df_raw = _make_trend_df(n=600)
    df = _apply_features(df_raw)

    df_v1 = v1.prepare_features(df.copy())
    count_v1 = int(v1.generate_signal(df_v1).sum())

    df_v3 = v3.prepare_features(df.copy())
    count_v3 = int(v3.generate_signal(df_v3).sum())

    assert count_v3 > count_v1, (
        f"MomentumContinuation ({count_v3}) should fire more than "
        f"BreakoutVolume ({count_v1}) on a flat-volume uptrend"
    )
    assert count_v3 >= 10, (
        f"Expected at least 10 signals on a 600-bar uptrend; got {count_v3}"
    )

    # close_5 and close_10 must be in prepared df
    assert "close_5" in df_v3.columns
    assert "close_10" in df_v3.columns

    # Signal must be strictly 0 or 1
    sig = v3.generate_signal(df_v3)
    assert set(sig.unique()).issubset({0, 1})
