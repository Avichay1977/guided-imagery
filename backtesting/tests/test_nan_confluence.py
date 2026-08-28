"""
NaN / missing-value safety tests for Backtester.calculate_confluence_score.

Core invariant:
  A missing or NaN optional field must NEVER create a phantom confluence point.

This is a targeted regression suite for the old bug where:
  float("nan") != "extreme"  →  True  →  score += 1   (wrong)

The fix: _has_valid_value() checks pd.isna() before any comparison.

Scoring map (max 6 points):
  Technical (3):
    close > ema_200              → +1
    close > local_high_20        → +1
    volume > volume_avg_20 * 1.5 → +1
  Optional context (3):
    relative_strength > 1.05     → +1
    market_trend == "bullish"    → +1
    volatility_regime != "extreme" → +1
"""

import math

import pytest

from backtester import Backtester, BacktestConfig
from portfolio import PortfolioTracker
from execution import ExecutionSimulator


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _bt() -> Backtester:
    config = BacktestConfig(
        initial_cash=100_000,
        max_risk_pct=0.01,
        max_drawdown_kill_pct=0.15,
        min_confluence_score=5,
        atr_stop_multiplier=2.0,
        take_profit_r=3.0,
        max_entry_gap_pct=0.05,
        min_entry_gap_pct=-0.03,
    )
    return Backtester(
        config=config,
        portfolio=PortfolioTracker(initial_cash=config.initial_cash),
        execution=ExecutionSimulator(slippage_pct=0.0005, fixed_fee=2.0),
    )


class _Tech:
    """Row with all three technical fields valid (3 points)."""
    close = 100.0
    ema_200 = 95.0
    local_high_20 = 99.0
    volume = 1_500_001.0
    volume_avg_20 = 1_000_000.0


class _Full(_Tech):
    """Row with all six criteria valid (6 points)."""
    relative_strength = 1.10
    market_trend = "bullish"
    volatility_regime = "normal"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_nan_relative_strength_adds_no_point():
    """relative_strength=NaN → _has_valid_value=False → 0 points."""
    class Row(_Tech):
        relative_strength = float("nan")
        market_trend = "bullish"
        volatility_regime = "normal"

    score = _bt().calculate_confluence_score(Row())
    assert score == 5   # 3 tech + 0 RS + 1 trend + 1 regime


def test_nan_market_trend_adds_no_point():
    """market_trend=NaN → 0 points (even though NaN != "bullish" is True in Python)."""
    class Row(_Tech):
        relative_strength = 1.10
        market_trend = float("nan")
        volatility_regime = "normal"

    score = _bt().calculate_confluence_score(Row())
    assert score == 5   # 3 tech + 1 RS + 0 trend + 1 regime


def test_nan_volatility_regime_adds_no_point():
    """volatility_regime=NaN must NOT satisfy the != "extreme" check."""
    class Row(_Tech):
        relative_strength = 1.10
        market_trend = "bullish"
        volatility_regime = float("nan")

    score = _bt().calculate_confluence_score(Row())
    assert score == 5   # 3 tech + 1 RS + 1 trend + 0 regime


def test_missing_optional_fields_add_no_points():
    """
    Row object has no optional attributes at all.
    getattr returns None → _has_valid_value=False → 0 optional points.
    """
    score = _bt().calculate_confluence_score(_Tech())
    assert score == 3   # only technical fields


def test_valid_optional_fields_add_points_correctly():
    """All 6 valid criteria → score == 6."""
    score = _bt().calculate_confluence_score(_Full())
    assert score == 6


def test_volatility_regime_extreme_adds_no_point():
    """volatility_regime="extreme" is a valid value but contributes 0 points."""
    class Row(_Full):
        volatility_regime = "extreme"

    score = _bt().calculate_confluence_score(Row())
    assert score == 5   # 3 tech + 1 RS + 1 trend + 0 extreme


def test_volatility_regime_normal_adds_point():
    """volatility_regime="normal" is != "extreme" and valid → +1 point."""
    class Row(_Tech):
        relative_strength = float("nan")
        market_trend = float("nan")
        volatility_regime = "normal"

    score = _bt().calculate_confluence_score(Row())
    assert score == 4   # 3 tech + 0 + 0 + 1


def test_old_nan_bug_regression():
    """
    Direct regression test for the phantom-score bug.

    In Python:  float("nan") != "extreme"  →  True
    Old code without _has_valid_value would execute:
        score += 1   # wrong

    Current code must detect NaN via pd.isna and skip the check entirely.
    """
    # Prove the raw Python expression that caused the bug
    assert float("nan") != "extreme", (
        "this raw expression is True — exactly why the guard exists"
    )
    assert math.isnan(float("nan")), "pd.isna relies on this"

    class BugRow(_Tech):
        relative_strength = float("nan")
        market_trend = float("nan")
        volatility_regime = float("nan")

    score = _bt().calculate_confluence_score(BugRow())

    # If the old bug were present, NaN != "extreme" → True → score would be 4
    # Correct: NaN is blocked → score stays at 3 (technical only)
    assert score == 3, (
        f"NaN optional fields must score 0. "
        f"Got {score}, expected 3. "
        f"Old bug: `NaN != 'extreme'` evaluated to True."
    )
