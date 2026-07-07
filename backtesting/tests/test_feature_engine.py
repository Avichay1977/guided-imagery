"""
FeatureEngine unit tests.

Invariants verified:
  - All required output columns are added
  - local_high_20, volume_avg_20, ema_200, atr_14 are shifted by 1 (anti-lookahead)
  - signal == 0 during warm-up (NaN features)
  - signal == 1 only when all four breakout conditions hold
  - drop_warmup=False keeps all rows; drop_warmup=True drops NaN-feature rows
  - Input DataFrame is not mutated

  v2 optional context features:
  - ema_50 is shifted by 1
  - market_trend uses shifted ema_50 and ema_200; "neutral" during warmup
  - atr_pct = atr_14 / close.shift(1)
  - volatility_regime "extreme" only when atr_pct > shifted rolling 90th percentile
  - relative_strength is NOT added (requires benchmark data)
"""

import numpy as np
import pandas as pd
import pytest

from features import FeatureEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flat_bars(n: int, price: float = 100.0, high: float = 101.0,
               low: float = 99.0, volume: float = 1_000.0) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "open": price,
            "high": high,
            "low": low,
            "close": price,
            "volume": volume,
        },
        index=dates,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_feature_engine_adds_required_columns():
    df = _flat_bars(210)
    out = FeatureEngine().generate_shifted_features(df)
    for col in ("ema_200", "volume_avg_20", "local_high_20", "atr_14", "signal"):
        assert col in out.columns, f"missing column: {col}"


def test_local_high_20_is_shifted():
    """
    local_high_20 at bar N must equal max(high[N-20 : N]), NOT including bar N.

    We inject a spike at bar 21 (index 21).  At that same bar, local_high_20
    must NOT include the spike yet.  At bar 22 the spike appears in the window.
    """
    df = _flat_bars(25, high=50.0)
    df.iloc[21, df.columns.get_loc("high")] = 1000.0   # spike at bar 21

    out = FeatureEngine().generate_shifted_features(df)

    # Bar 21: lookback window is bars 1..20 (highs all == 50) → must be 50
    local_high_at_spike_bar = out["local_high_20"].iloc[21]
    assert local_high_at_spike_bar == pytest.approx(50.0), (
        f"local_high_20 at spike bar must NOT include current bar's high. "
        f"Got {local_high_at_spike_bar}, expected 50.0"
    )

    # Bar 22: lookback window is bars 2..21 (includes spike) → must be 1000
    local_high_next_bar = out["local_high_20"].iloc[22]
    assert local_high_next_bar == pytest.approx(1000.0), (
        f"local_high_20 at bar after spike must include spike. "
        f"Got {local_high_next_bar}, expected 1000.0"
    )


def test_volume_avg_20_is_shifted():
    """
    volume_avg_20 at bar N must equal mean(volume[N-20 : N]), not including bar N.
    """
    df = _flat_bars(25, volume=1_000.0)
    df.iloc[21, df.columns.get_loc("volume")] = 999_000.0   # spike at bar 21

    out = FeatureEngine().generate_shifted_features(df)

    # At bar 21: lookback bars 1..20, all 1000 → avg must be 1000
    avg_at_spike = out["volume_avg_20"].iloc[21]
    assert avg_at_spike == pytest.approx(1_000.0), (
        f"volume_avg_20 at spike bar must NOT include bar's own volume. "
        f"Got {avg_at_spike}"
    )

    # At bar 22: lookback bars 2..21, includes spike → avg must exceed 1000
    avg_next = out["volume_avg_20"].iloc[22]
    assert avg_next > 1_000.0


def test_ema_200_is_shifted():
    """
    ema_200[k] must equal raw EWM value at k-1 (strict 1-bar shift).
    """
    df = _flat_bars(210)
    out = FeatureEngine().generate_shifted_features(df)

    raw_ema = df["close"].ewm(span=200, adjust=False, min_periods=200).mean()

    # First valid shifted value is at index 200
    for k in range(200, 210):
        assert out["ema_200"].iloc[k] == pytest.approx(
            raw_ema.iloc[k - 1], rel=1e-9
        ), f"ema_200 mismatch at bar {k}"


def test_atr_14_is_shifted():
    """
    atr_14[k] must equal raw 14-period ATR at k-1.
    """
    df = _flat_bars(30)
    out = FeatureEngine().generate_shifted_features(df)

    fe = FeatureEngine()
    raw_atr = fe._compute_atr(df)

    for k in range(15, 30):
        assert out["atr_14"].iloc[k] == pytest.approx(
            raw_atr.iloc[k - 1], rel=1e-9
        ), f"atr_14 mismatch at bar {k}"


def test_signal_zero_during_warmup():
    """
    Before all required features have valid values, signal must be 0.
    The warm-up period ends at bar 200 (ema_200 needs 200 prior bars + 1 shift).
    """
    df = _flat_bars(210)
    out = FeatureEngine().generate_shifted_features(df)

    # Bars 0..199 have NaN ema_200 → signal must be 0
    assert (out["signal"].iloc[:200] == 0).all(), (
        "signal must be 0 during warm-up (NaN ema_200)"
    )


def test_signal_triggers_on_valid_breakout():
    """
    Build a deterministic dataset where exactly one bar satisfies all four
    signal conditions after warm-up, and verify signal == 1 there.
    """
    # 210 baseline bars: price=100, high=101, volume=1000
    df = _flat_bars(210, price=100.0, high=101.0, low=99.0, volume=1_000.0)

    # Bar 209 (last bar): breakout — close > ema_200, close > local_high_20,
    # volume > volume_avg_20 * 1.5, atr_14 > 0
    df.iloc[209, df.columns.get_loc("close")] = 120.0
    df.iloc[209, df.columns.get_loc("high")] = 121.0
    df.iloc[209, df.columns.get_loc("volume")] = 3_000.0   # 3× avg of 1000

    out = FeatureEngine().generate_shifted_features(df)

    # ema_200[209] = raw_ema[208] ≈ 100 (all past closes were 100)
    # local_high_20[209] = max(high[189:209]) = 101
    # volume_avg_20[209] = mean(volume[189:209]) = 1000
    # close[209] = 120 > 100 ✓, 120 > 101 ✓, 3000 > 1500 ✓
    assert out["signal"].iloc[209] == 1, (
        f"Expected signal=1 on breakout bar, got {out['signal'].iloc[209]}"
    )


def test_drop_warmup_false_keeps_all_rows():
    """drop_warmup=False (default) must not drop any rows."""
    df = _flat_bars(210)
    out = FeatureEngine().generate_shifted_features(df, drop_warmup=False)
    assert len(out) == len(df)


def test_drop_warmup_true_drops_nan_feature_rows():
    """drop_warmup=True must remove rows where required features are NaN."""
    df = _flat_bars(210)
    out = FeatureEngine().generate_shifted_features(df, drop_warmup=True)

    required = ["ema_200", "local_high_20", "volume_avg_20", "atr_14"]
    assert out[required].notna().all().all(), (
        "drop_warmup=True must leave no NaN in required feature columns"
    )
    assert len(out) < len(df), "some warm-up rows must have been dropped"


def test_input_not_mutated():
    """generate_shifted_features must not modify the caller's DataFrame."""
    df = _flat_bars(30)
    cols_before = set(df.columns)
    FeatureEngine().generate_shifted_features(df)
    assert set(df.columns) == cols_before, "input DataFrame must not gain new columns"


# ---------------------------------------------------------------------------
# v2 optional context feature tests
# ---------------------------------------------------------------------------

def test_ema_50_is_shifted():
    """ema_50[k] must equal raw EWM(span=50) value at k-1."""
    df = _flat_bars(60)
    out = FeatureEngine().generate_shifted_features(df)

    raw_ema = df["close"].ewm(span=50, adjust=False, min_periods=50).mean()
    for k in range(50, 60):
        assert out["ema_50"].iloc[k] == pytest.approx(
            raw_ema.iloc[k - 1], rel=1e-9
        ), f"ema_50 mismatch at bar {k}"


def test_market_trend_uses_shifted_ema_50_and_ema_200():
    """
    With a steadily rising price series, shifted ema_50 > shifted ema_200
    after both warmup periods complete → market_trend must be "bullish".
    """
    n = 210
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    closes = [100.0 + i * 0.5 for i in range(n)]
    df = pd.DataFrame(
        {
            "open": closes,
            "high": [c + 1 for c in closes],
            "low": [c - 1 for c in closes],
            "close": closes,
            "volume": 1_000.0,
        },
        index=dates,
    )
    out = FeatureEngine().generate_shifted_features(df)

    # After bar 201, ema_50 tracks more recent (higher) prices than ema_200
    # → ema_50 > ema_200 → "bullish"
    assert (out["market_trend"].iloc[205:] == "bullish").all(), (
        "Expected 'bullish' market_trend for rising price series after warmup"
    )


def test_market_trend_neutral_during_warmup():
    """
    ema_200 is NaN until bar 200 (200 prior bars + shift).
    market_trend must be "neutral" for all bars before both EMAs are valid.
    """
    df = _flat_bars(210)
    out = FeatureEngine().generate_shifted_features(df)

    assert (out["market_trend"].iloc[:200] == "neutral").all(), (
        "market_trend must be 'neutral' during ema_200 warmup period"
    )


def test_atr_pct_uses_shifted_safe_values():
    """atr_pct must equal atr_14 / close.shift(1) — no same-bar data."""
    df = _flat_bars(30)
    out = FeatureEngine().generate_shifted_features(df)

    expected = out["atr_14"] / out["close"].shift(1)
    pd.testing.assert_series_equal(
        out["atr_pct"],
        expected,
        check_names=False,
        rtol=1e-9,
    )


def test_volatility_regime_extreme_when_above_shifted_rolling_threshold():
    """
    Baseline period (300 bars): ATR ≈ 2 → atr_pct ≈ 0.02.
    Spike period (150 bars): ATR ≈ 100 → atr_pct ≈ 1.00.

    After the spike propagates through the ATR rolling window (~15 bars)
    and the threshold is established from the normal baseline, at least
    one bar in the spike window must have volatility_regime == "extreme".
    """
    n_normal = 300
    n_spike = 150
    n = n_normal + n_spike

    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    high = [101.0] * n_normal + [150.0] * n_spike
    low = [99.0] * n_normal + [50.0] * n_spike
    close = [100.0] * n

    df = pd.DataFrame(
        {
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1_000.0,
        },
        index=dates,
    )
    out = FeatureEngine().generate_shifted_features(df)

    # Allow 30 bars after the spike onset for ATR and threshold to settle
    spike_slice = out["volatility_regime"].iloc[n_normal + 30:]
    assert (spike_slice == "extreme").any(), (
        "Expected 'extreme' volatility_regime during high-volatility period"
    )


def test_volatility_regime_normal_when_not_extreme():
    """
    Flat bars → constant ATR → all atr_pct values equal.
    The 90th percentile of a constant series equals that constant.
    atr_pct > threshold is False → every bar is "normal".
    """
    df = _flat_bars(270)
    out = FeatureEngine().generate_shifted_features(df)

    assert not (out["volatility_regime"] == "extreme").any(), (
        "Constant-ATR series must never produce 'extreme' volatility_regime"
    )


def test_no_relative_strength_added_without_benchmark():
    """
    relative_strength requires a benchmark (e.g. SPY).
    FeatureEngine must NOT add this column from single-ticker data.
    """
    df = _flat_bars(30)
    out = FeatureEngine().generate_shifted_features(df)

    assert "relative_strength" not in out.columns, (
        "relative_strength must not be computed without benchmark data"
    )
