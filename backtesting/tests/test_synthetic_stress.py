"""
Synthetic stress tests for the backtesting engine.

Each test uses a deterministic DataFrame with known prices so the expected
trade outcome can be calculated analytically before running the engine.

Key numbers (derived from default parameters):
    signal_close  = 100.00
    entry_open    = 100.00  → entry_price = 100.00 * 1.0005 = 100.05
    stop_price    = 100.05 - 2.0 * 2.0 = 96.05
    risk_per_share= 4.00
    tp_price      = 100.05 + 3.0 * 4.0 = 112.05
    shares        = (100_000 * 0.01) / 4.0 = 250
"""

import math
import pandas as pd
import pytest

from backtester import Backtester, BacktestConfig
from portfolio import PortfolioTracker
from execution import ExecutionSimulator


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_SLIPPAGE = 0.0005
_FEE = 2.0
_PRICE = 100.0
_ATR = 2.0
_ENTRY_PRICE = _PRICE * (1 + _SLIPPAGE)         # 100.05
_STOP_PRICE = _ENTRY_PRICE - 2.0 * _ATR         # 96.05
_TP_PRICE = _ENTRY_PRICE + 3.0 * (_ENTRY_PRICE - _STOP_PRICE)  # 112.05


def make_bars(n: int, price: float = _PRICE, atr: float = _ATR) -> pd.DataFrame:
    """
    Return n flat daily bars where every scoring criterion is satisfied
    and signal=0 on every bar.  Callers override specific cells to inject
    signals and price events.
    """
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    df = pd.DataFrame(
        {
            "open": price,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": 1_000_000.0,
            "signal": 0,
            "atr": atr,
            # Technical structure fields (all pre-computed, all valid)
            "ema_200": price - 5.0,       # below close → close > ema_200 ✓
            "local_high_20": price - 1.0, # below close → breakout ✓
            "volume_avg_20": 500_000.0,   # volume is 2× avg → 2.0 > 1.5 ✓
            # Optional market context
            "relative_strength": 1.10,
            "market_trend": "bullish",
            "volatility_regime": "normal",
        },
        index=dates,
    )
    return df


def _make_backtester(config: BacktestConfig | None = None) -> Backtester:
    if config is None:
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
    portfolio = PortfolioTracker(initial_cash=config.initial_cash)
    execution = ExecutionSimulator(slippage_pct=_SLIPPAGE, fixed_fee=_FEE)
    return Backtester(config=config, portfolio=portfolio, execution=execution)


def _run(df: pd.DataFrame, config: BacktestConfig | None = None) -> dict:
    return _make_backtester(config).run(df)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_trending_market_hits_take_profit():
    """
    Signal on bar 260, entry on bar 261, take profit bar on 262.
    Verifies: one trade, exit_reason=take_profit, R>0, no lookahead.
    """
    df = make_bars(265)

    df.at[df.index[260], "signal"] = 1
    # Bar 262: high spikes well above TP (112.05)
    df.at[df.index[262], "high"] = 115.0

    results = _run(df)
    trades = results["trades"]

    assert len(trades) == 1
    t = trades[0]
    assert t["exit_reason"] == "take_profit"

    risk = t["entry_price"] - t["stop_price"]
    r_multiple = (t["exit_price"] - t["entry_price"]) / risk
    assert r_multiple > 0

    # Anti-lookahead: entry bar must come after signal bar
    assert t["entry_time"] == df.index[261]
    assert t["entry_time"] > df.index[260]
    assert t["exit_time"] >= t["entry_time"]


def test_entry_gap_up_is_cancelled():
    """
    Next bar opens 6 % above signal close (limit is +5 %).
    No trade should be taken.
    """
    df = make_bars(265)
    df.at[df.index[260], "signal"] = 1

    signal_close = df.at[df.index[260], "close"]
    gap_open = signal_close * 1.06  # +6 % > max_entry_gap_pct (+5 %)
    df.at[df.index[261], "open"] = gap_open
    df.at[df.index[261], "high"] = gap_open + 0.5
    df.at[df.index[261], "low"] = gap_open - 0.5

    results = _run(df)
    assert len(results["trades"]) == 0


def test_entry_gap_down_is_cancelled():
    """
    Next bar opens 4 % below signal close (limit is −3 %).
    No trade should be taken.
    """
    df = make_bars(265)
    df.at[df.index[260], "signal"] = 1

    signal_close = df.at[df.index[260], "close"]
    gap_open = signal_close * 0.96  # −4 % < min_entry_gap_pct (−3 %)
    df.at[df.index[261], "open"] = gap_open
    df.at[df.index[261], "high"] = gap_open + 0.5
    df.at[df.index[261], "low"] = gap_open - 0.5

    results = _run(df)
    assert len(results["trades"]) == 0


def test_stop_gap_down_exits_at_open_not_stop():
    """
    Bar 262 gaps down far below stop (open=80, stop≈96.05).
    Exit must be at bar's open (adjusted for slippage), not the stop level.
    R must be worse than −1 (slippage makes actual loss exceed 1R).
    """
    df = make_bars(265)
    df.at[df.index[260], "signal"] = 1

    crash_open = 80.0
    df.at[df.index[262], "open"] = crash_open
    df.at[df.index[262], "high"] = crash_open + 1.0
    df.at[df.index[262], "low"] = crash_open - 1.0
    df.at[df.index[262], "close"] = crash_open

    results = _run(df)
    trades = results["trades"]

    assert len(trades) == 1
    t = trades[0]
    assert t["exit_reason"] == "stop_loss"

    expected_exit_price = crash_open * (1 - _SLIPPAGE)
    assert t["exit_price"] == pytest.approx(expected_exit_price, rel=1e-4)

    risk = t["entry_price"] - t["stop_price"]
    r_multiple = (t["exit_price"] - t["entry_price"]) / risk
    assert r_multiple < -1


def test_ambiguous_bar_counts_and_uses_stop_first():
    """
    Bar 262: open between stop and TP, but low <= stop AND high >= TP.
    Must be counted as ambiguous exit; trade records conservative stop_loss fill.
    """
    df = make_bars(265)
    df.at[df.index[260], "signal"] = 1

    # open stays neutral (100), low breaches stop, high breaches TP
    df.at[df.index[262], "open"] = 100.0     # between stop (96.05) and TP (112.05)
    df.at[df.index[262], "low"] = 95.0       # <= 96.05
    df.at[df.index[262], "high"] = 115.0     # >= 112.05

    results = _run(df)

    assert results["ambiguous_exits"] == 1

    t = results["trades"][0]
    assert t["exit_reason"] == "stop_loss"  # conservative: stop fills first


def test_nan_optional_fields_do_not_add_score():
    """
    NaN in optional market-context fields must not add score.
    This guards against the old `NaN != 'extreme'` → True bug.

    With only technical fields valid (close>ema_200, breakout, volume), score=3.
    NaN relative_strength / market_trend / volatility_regime must contribute 0.
    """
    bt = _make_backtester()

    class FakeRow:
        close = 100.0
        ema_200 = 95.0          # close > ema_200 → +1
        local_high_20 = 99.0    # close > local_high_20 → +1
        volume = 1_500_001.0
        volume_avg_20 = 1_000_000.0   # volume > 1.5× avg → +1
        relative_strength = float("nan")   # NaN → 0
        market_trend = float("nan")        # NaN → 0
        volatility_regime = float("nan")   # NaN → 0, NOT +1 (old bug)

    score = bt.calculate_confluence_score(FakeRow())
    assert score == 3, (
        f"Expected 3 (technical only), got {score}. "
        "NaN optional fields must not add to score."
    )

    # Prove the old bug would have fired: NaN != 'extreme' is True in Python
    assert float("nan") != "extreme", "sanity: this is why the guard is necessary"
    assert math.isnan(float("nan")), "sanity: pd.isna catches this"


def test_crash_scenario_triggers_kill_switch():
    """
    Entry on bar 261, large gap-down crash on bar 262 (open=80).
    With max_drawdown_kill_pct=0.03, the 5%+ realized loss must trigger
    the kill switch on the following bar.
    """
    config = BacktestConfig(
        initial_cash=100_000,
        max_risk_pct=0.01,
        max_drawdown_kill_pct=0.03,  # 3 % threshold — crash exceeds this
        min_confluence_score=5,
        atr_stop_multiplier=2.0,
        take_profit_r=3.0,
        max_entry_gap_pct=0.05,
        min_entry_gap_pct=-0.03,
    )

    df = make_bars(270)
    df.at[df.index[260], "signal"] = 1

    crash_open = 80.0
    df.at[df.index[262], "open"] = crash_open
    df.at[df.index[262], "high"] = crash_open + 1.0
    df.at[df.index[262], "low"] = crash_open - 1.0
    df.at[df.index[262], "close"] = crash_open

    results = _run(df, config=config)

    # Kill switch must have fired
    assert results["kill_switch_triggered"] is True

    # Position must have been exited (crash exit happened before kill switch check)
    assert len(results["trades"]) >= 1
    crash_trade = results["trades"][-1]
    assert crash_trade["exit_reason"] == "stop_loss"

    # Final equity must reflect the loss
    assert results["final_equity"] < config.initial_cash
