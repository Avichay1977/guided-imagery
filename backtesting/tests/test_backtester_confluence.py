"""
Targeted tests for Backtester.calculate_confluence_score NaN safety.

Invariants verified:
  - Missing fields (not present on row object) → score contribution = 0
  - NaN fields → score contribution = 0
  - None fields → score contribution = 0
  - volatility_regime=NaN must NOT satisfy != "extreme" (old phantom-score bug)
  - All 6 valid fields → score = 6
  - Only technical fields valid, optional fields NaN → score = 3
"""

import math

import pytest

from backtester import Backtester, BacktestConfig
from portfolio import PortfolioTracker
from execution import ExecutionSimulator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_backtester() -> Backtester:
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


class _TechnicalOnly:
    """Row with valid technical fields only — no optional market-context attrs."""
    close = 100.0
    ema_200 = 95.0          # close > ema_200 → +1
    local_high_20 = 99.0    # close > local_high_20 → +1
    volume = 1_500_001.0
    volume_avg_20 = 1_000_000.0   # volume > 1.5× avg → +1


class _AllValid:
    """Row with all 6 scoring criteria satisfied."""
    close = 100.0
    ema_200 = 95.0
    local_high_20 = 99.0
    volume = 1_500_001.0
    volume_avg_20 = 1_000_000.0
    relative_strength = 1.10   # > 1.05 → +1
    market_trend = "bullish"   # == "bullish" → +1
    volatility_regime = "normal"  # != "extreme" → +1


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_missing_optional_fields_do_not_add_score():
    """
    When optional attributes are absent from the row object entirely,
    getattr returns None → _has_valid_value → False → score += 0.
    """
    bt = _make_backtester()
    score = bt.calculate_confluence_score(_TechnicalOnly())
    assert score == 3, f"Expected 3 (technical only), got {score}"


def test_valid_optional_fields_add_score_correctly():
    """All 6 criteria satisfied → score == 6."""
    bt = _make_backtester()
    score = bt.calculate_confluence_score(_AllValid())
    assert score == 6, f"Expected 6, got {score}"


def test_nan_optional_fields_do_not_add_score():
    """
    NaN in optional fields must not contribute.
    This guards the specific bug where `NaN != "extreme"` evaluates to True,
    granting a phantom confluence point.
    """
    bt = _make_backtester()

    class Row(_TechnicalOnly):
        relative_strength = float("nan")
        market_trend = float("nan")
        volatility_regime = float("nan")

    score = bt.calculate_confluence_score(Row())
    assert score == 3, f"Expected 3 (NaN optionals must score 0), got {score}"


def test_none_optional_fields_do_not_add_score():
    """None values (e.g. from optional columns absent in CSV) score 0."""
    bt = _make_backtester()

    class Row(_TechnicalOnly):
        relative_strength = None
        market_trend = None
        volatility_regime = None

    score = bt.calculate_confluence_score(Row())
    assert score == 3


def test_volatility_regime_nan_no_phantom_score():
    """
    Focused regression test for the NaN != 'extreme' phantom-score bug.

    Python evaluates `float('nan') != 'extreme'` as True.
    Without _has_valid_value, this would add +1 to the score for every
    bar where volatility_regime is NaN.
    """
    bt = _make_backtester()

    # Prove the raw Python expression that caused the bug
    assert float("nan") != "extreme", (
        "sanity: this is why the guard is necessary"
    )
    assert math.isnan(float("nan")), "sanity: pd.isna catches this"

    class Row(_TechnicalOnly):
        relative_strength = 1.10     # valid → +1
        market_trend = "bullish"     # valid → +1
        volatility_regime = float("nan")  # NaN → must NOT add +1

    score = bt.calculate_confluence_score(Row())
    # Expected: 3 (technical) + 1 (RS) + 1 (trend) + 0 (NaN regime) = 5
    assert score == 5, (
        f"Expected 5 (NaN volatility_regime must not add point), got {score}"
    )


def test_extreme_volatility_regime_blocks_score():
    """volatility_regime='extreme' is a valid value that correctly scores 0."""
    bt = _make_backtester()

    class Row(_AllValid):
        volatility_regime = "extreme"

    score = bt.calculate_confluence_score(Row())
    assert score == 5, f"Expected 5 (extreme regime = 0 points), got {score}"


def test_relative_strength_at_boundary():
    """relative_strength must be strictly > 1.05 to score."""
    bt = _make_backtester()

    class RowExact(_TechnicalOnly):
        relative_strength = 1.05   # not strictly greater → 0
        market_trend = "bullish"
        volatility_regime = "normal"

    class RowAbove(_TechnicalOnly):
        relative_strength = 1.051   # just above threshold → +1
        market_trend = "bullish"
        volatility_regime = "normal"

    assert bt.calculate_confluence_score(RowExact()) == 5   # 3 + 0 + 1 + 1
    assert bt.calculate_confluence_score(RowAbove()) == 6   # 3 + 1 + 1 + 1
