"""
SignalDiagnostics tests.

Core invariants:
  - total_rows counts the full DataFrame
  - rows_with_valid_core_features excludes warmup (NaN) rows
  - Missing optional columns → condition not counted (not counted as pass)
  - NaN optional values → condition not counted as pass
  - score_distribution sums to rows_with_valid_core_features
  - _compute_scores is numerically identical to Backtester.calculate_confluence_score
  - Bottleneck detection fires on the correct thresholds
"""

import pandas as pd
import pytest

from diagnostics import SignalDiagnostics
from backtester import Backtester, BacktestConfig
from portfolio import PortfolioTracker
from execution import ExecutionSimulator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_row(
    close=100.0,
    ema_200=95.0,
    local_high_20=99.0,
    volume=2_000_000.0,
    volume_avg_20=1_000_000.0,
    atr_14=2.0,
    market_trend="bullish",
    volatility_regime="normal",
    relative_strength=None,
) -> dict:
    d = {
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": volume,
        "ema_200": ema_200,
        "local_high_20": local_high_20,
        "volume_avg_20": volume_avg_20,
        "atr_14": atr_14,
        "signal": 1,
        "market_trend": market_trend,
        "volatility_regime": volatility_regime,
    }
    if relative_strength is not None:
        d["relative_strength"] = relative_strength
    return d


def _df_from_rows(rows: list[dict], start: str = "2020-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=len(rows), freq="B")
    return pd.DataFrame(rows, index=dates)


def _diag() -> SignalDiagnostics:
    return SignalDiagnostics()


def _backtester() -> Backtester:
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
        portfolio=PortfolioTracker(initial_cash=100_000),
        execution=ExecutionSimulator(slippage_pct=0.0005, fixed_fee=2.0),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_signal_diagnostics_counts_total_rows():
    df = _df_from_rows([_make_valid_row()] * 50)
    result = _diag().analyze_feature_funnel(df)
    assert result["total_rows"] == 50


def test_signal_diagnostics_counts_core_feature_validity():
    """
    First 20 rows have ema_200=NaN → not valid.
    Remaining 30 rows are valid.
    """
    rows = []
    for _ in range(20):
        r = _make_valid_row()
        r["ema_200"] = float("nan")
        rows.append(r)
    for _ in range(30):
        rows.append(_make_valid_row())

    df = _df_from_rows(rows)
    result = _diag().analyze_feature_funnel(df)

    assert result["total_rows"] == 50
    assert result["rows_with_valid_core_features"] == 30


def test_signal_diagnostics_missing_optional_fields_do_not_pass():
    """
    DataFrame has no market_trend column.
    market_trend_bullish must not appear in condition_counts.
    """
    row = _make_valid_row()
    del row["market_trend"]
    df = _df_from_rows([row] * 10)
    result = _diag().analyze_feature_funnel(df)

    assert "market_trend_bullish" not in result["condition_counts"], (
        "market_trend_bullish must not be counted when column is absent"
    )


def test_signal_diagnostics_nan_optional_fields_do_not_pass():
    """
    market_trend=NaN must not count as 'bullish'.
    The NaN phantom-score bug (NaN != 'extreme' → True) must not apply here.
    """
    row = _make_valid_row()
    row["market_trend"] = float("nan")
    df = _df_from_rows([row] * 10)
    result = _diag().analyze_feature_funnel(df)

    assert result["condition_counts"].get("market_trend_bullish", 0) == 0, (
        "NaN market_trend must not count as bullish"
    )


def test_signal_diagnostics_score_distribution():
    """
    score_distribution values must sum to rows_with_valid_core_features.
    """
    rows = [_make_valid_row()] * 20
    df = _df_from_rows(rows)
    result = _diag().analyze_feature_funnel(df)

    total_in_dist = sum(result["score_distribution"].values())
    assert total_in_dist == result["rows_with_valid_core_features"], (
        f"score_distribution sum {total_in_dist} != "
        f"rows_with_valid_core_features {result['rows_with_valid_core_features']}"
    )


def test_signal_diagnostics_detects_low_signal_sample():
    """
    Only 5 rows reach min_confluence_score → LOW_SIGNAL_SAMPLE bottleneck.
    """
    # 5 rows that score >= 5 (valid bullish breakout with normal volatility)
    # + many rows that score low (close below ema_200)
    rows = []
    for _ in range(5):
        rows.append(_make_valid_row())  # scores 5: 3 tech + trend + regime
    for _ in range(25):
        r = _make_valid_row()
        r["close"] = 80.0   # close < ema_200(95) and < local_high_20(99) → 0 tech
        rows.append(r)

    df = _df_from_rows(rows)
    result = _diag().analyze_feature_funnel(df, min_confluence_score=5)

    assert any("LOW_SIGNAL_SAMPLE" in b for b in result["bottlenecks"]), (
        f"Expected LOW_SIGNAL_SAMPLE bottleneck, got: {result['bottlenecks']}"
    )


def test_signal_diagnostics_detects_volume_bottleneck():
    """
    Volume always below threshold → VOLUME_FILTER_TOO_RESTRICTIVE.
    """
    row = _make_valid_row(volume=100.0, volume_avg_20=1_000_000.0)
    df = _df_from_rows([row] * 30)
    result = _diag().analyze_feature_funnel(df)

    assert any("VOLUME_FILTER_TOO_RESTRICTIVE" in b for b in result["bottlenecks"]), (
        f"Expected VOLUME_FILTER_TOO_RESTRICTIVE, got: {result['bottlenecks']}"
    )


def test_signal_diagnostics_detects_breakout_bottleneck():
    """
    close always below local_high_20 → BREAKOUT_FILTER_TOO_RESTRICTIVE.
    """
    row = _make_valid_row(close=90.0, local_high_20=200.0)
    df = _df_from_rows([row] * 30)
    result = _diag().analyze_feature_funnel(df)

    assert any("BREAKOUT_FILTER_TOO_RESTRICTIVE" in b for b in result["bottlenecks"]), (
        f"Expected BREAKOUT_FILTER_TOO_RESTRICTIVE, got: {result['bottlenecks']}"
    )


def test_signal_diagnostics_matches_backtester_confluence_score_on_sample_rows():
    """
    For each row in a known DataFrame, the score computed by SignalDiagnostics
    must exactly match the score from Backtester.calculate_confluence_score.

    This verifies that the vectorized diagnostic scoring is an exact replica
    of the row-by-row Backtester logic.
    """
    bt = _backtester()
    diag = _diag()

    # Three rows with analytically computed scores:
    # Row 0: 3 tech + neutral trend + extreme regime       → 3+0+0 = 3
    # Row 1: 3 tech + bullish trend + normal regime        → 3+1+1 = 5
    # Row 2: close=80 misses 2 price conditions but volume
    #        still passes; bullish + normal                → 1+1+1 = 3
    #        (volume > avg*1.5 ✓, but close < ema_200 and < local_high_20)
    rows = [
        _make_valid_row(market_trend="neutral", volatility_regime="extreme"),   # 3
        _make_valid_row(market_trend="bullish", volatility_regime="normal"),    # 5
        _make_valid_row(close=80.0, market_trend="bullish", volatility_regime="normal"),  # 3
    ]
    df = _df_from_rows(rows)

    result = diag.analyze_feature_funnel(df, min_confluence_score=5)
    diag_scores = diag._compute_scores(df)

    # Verify against Backtester row by row
    for i, row in enumerate(df.itertuples()):
        bt_score = bt.calculate_confluence_score(row)
        diag_score = int(diag_scores.iloc[i])
        assert diag_score == bt_score, (
            f"Row {i}: diagnostics score={diag_score} != backtester score={bt_score}"
        )

    # score_distribution: rows 0 and 2 score 3, row 1 scores 5
    assert result["score_distribution"][3] == 2   # rows 0 and 2
    assert result["score_distribution"][5] == 1   # row 1
