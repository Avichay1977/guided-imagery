"""
Unit tests for RotationBacktester.run() — portfolio path engine.

Deterministic toy feature matrices and toy return series only.
No real market data. No data fetch. No full research backtest.
No strategy_lab_runner.
"""

import inspect
import math

import pandas as pd
import pytest

from rotation_backtester import (
    RotationBacktester,
    RotationBacktesterConfig,
    RotationBacktesterResult,
)


# ---------------------------------------------------------------------------
# Toy data helpers
# ---------------------------------------------------------------------------

_DATES = list(pd.bdate_range("2020-01-02", periods=5))
# 2020-01-02, 2020-01-03, 2020-01-06, 2020-01-07, 2020-01-08

_DATES_2M = list(pd.bdate_range("2020-01-02", "2020-02-28"))
# spans Jan and Feb; rebalance on 2020-01-02 and 2020-02-03


def _frow(date, ticker, crs=0.8, rp=0.9, elig=True):
    return {
        "date": pd.Timestamp(date),
        "ticker": ticker,
        "composite_rs": crs,
        "rank_percentile": rp,
        "is_rotation_eligible": elig,
        "trend_filter_ema200": elig,
        "volatility_filter_atr_pct": elig,
        "liquidity_filter_volume_avg_20": elig,
    }


def _make_fm(*rows):
    return pd.DataFrame(list(rows))


def _make_ret(ticker, daily_ret, dates):
    return pd.Series([daily_ret] * len(dates), index=pd.DatetimeIndex(dates), name=ticker)


def _engine(**cfg):
    return RotationBacktester(RotationBacktesterConfig(**cfg)) if cfg else RotationBacktester()


def _universe_3full(daily_ret=0.01):
    """3 eligible tickers, fully invested, single rebalance."""
    fm = _make_fm(
        _frow("2020-01-02", "AAA", crs=0.9, rp=0.95),
        _frow("2020-01-02", "BBB", crs=0.8, rp=0.90),
        _frow("2020-01-02", "CCC", crs=0.7, rp=0.85),
    )
    ret = {
        "AAA": _make_ret("AAA", daily_ret, _DATES),
        "BBB": _make_ret("BBB", daily_ret, _DATES),
        "CCC": _make_ret("CCC", daily_ret, _DATES),
    }
    return {"feature_matrix": fm, "returns_by_ticker": ret}


def _universe_2tickers():
    """2 eligible tickers (top_n=3), one cash slot."""
    fm = _make_fm(
        _frow("2020-01-02", "AAA", crs=0.9),
        _frow("2020-01-02", "BBB", crs=0.8),
    )
    ret = {
        "AAA": _make_ret("AAA", 0.0, _DATES),
        "BBB": _make_ret("BBB", 0.0, _DATES),
    }
    return {"feature_matrix": fm, "returns_by_ticker": ret}


def _universe_1ticker():
    """1 eligible ticker (top_n=3), two cash slots."""
    fm = _make_fm(_frow("2020-01-02", "AAA", crs=0.9))
    ret = {"AAA": _make_ret("AAA", 0.0, _DATES)}
    return {"feature_matrix": fm, "returns_by_ticker": ret}


def _universe_no_eligible():
    """Feature rows present but ticker fails all filters."""
    fm = _make_fm(_frow("2020-01-02", "AAA", elig=False))
    ret = {"AAA": _make_ret("AAA", 0.0, _DATES)}
    return {"feature_matrix": fm, "returns_by_ticker": ret}


def _universe_2months():
    """Two rebalance dates across Jan and Feb 2020."""
    fm = _make_fm(
        _frow("2020-01-02", "AAA", crs=0.9, rp=0.95),
        _frow("2020-01-02", "BBB", crs=0.8, rp=0.90),
        _frow("2020-02-03", "AAA", crs=0.9, rp=0.95),
        _frow("2020-02-03", "BBB", crs=0.8, rp=0.90),
    )
    ret = {
        "AAA": _make_ret("AAA", 0.001, _DATES_2M),
        "BBB": _make_ret("BBB", 0.001, _DATES_2M),
    }
    return {"feature_matrix": fm, "returns_by_ticker": ret}


# ---------------------------------------------------------------------------
# Category 1: Input validation (tests 1–7)
# ---------------------------------------------------------------------------

def test_run_requires_precomputed_feature_matrix():
    e = _engine()
    with pytest.raises(ValueError, match="feature_matrix"):
        e.run({"AAPL": [1, 2, 3]}, None)


def test_run_requires_returns_by_ticker():
    fm = _make_fm(_frow("2020-01-02", "AAA"))
    with pytest.raises(ValueError, match="returns_by_ticker"):
        _engine().run({"feature_matrix": fm}, None)


def test_run_rejects_raw_ohlcv_input():
    raw = {
        "AAPL": pd.DataFrame({
            "open": [100.0], "high": [101.0],
            "low": [99.0], "close": [100.0], "volume": [1e6],
        })
    }
    with pytest.raises(ValueError, match="feature_matrix"):
        _engine().run(raw, None)


def test_run_rejects_missing_feature_columns():
    fm = pd.DataFrame({"date": [pd.Timestamp("2020-01-02")], "ticker": ["AAA"]})
    ret = {"AAA": _make_ret("AAA", 0.01, _DATES)}
    with pytest.raises(ValueError):
        _engine().run({"feature_matrix": fm, "returns_by_ticker": ret}, None)


def test_run_rejects_missing_returns_for_selected_ticker():
    # AAA is eligible and selected but absent from returns_by_ticker
    fm = _make_fm(_frow("2020-01-02", "AAA"))
    dummy_dates = [pd.Timestamp("2020-01-02"), pd.Timestamp("2020-01-03")]
    ret = {"DUMMY": pd.Series([0.01, 0.01], index=pd.DatetimeIndex(dummy_dates))}
    with pytest.raises(ValueError):
        _engine().run({"feature_matrix": fm, "returns_by_ticker": ret}, None)


def test_run_rejects_nan_returns():
    fm = _make_fm(_frow("2020-01-02", "AAA"))
    ret = {"AAA": pd.Series([float("nan")], index=pd.DatetimeIndex([pd.Timestamp("2020-01-02")]))}
    with pytest.raises(ValueError):
        _engine().run({"feature_matrix": fm, "returns_by_ticker": ret}, None)


def test_run_rejects_inf_returns():
    fm = _make_fm(_frow("2020-01-02", "AAA"))
    ret = {"AAA": pd.Series([float("inf")], index=pd.DatetimeIndex([pd.Timestamp("2020-01-02")]))}
    with pytest.raises(ValueError):
        _engine().run({"feature_matrix": fm, "returns_by_ticker": ret}, None)


# ---------------------------------------------------------------------------
# Category 2: Result structure (tests 8–14)
# ---------------------------------------------------------------------------

def test_run_returns_rotation_backtester_result():
    r = _engine().run(_universe_3full(), None)
    assert isinstance(r, RotationBacktesterResult)


def test_equity_curve_is_series():
    r = _engine().run(_universe_3full(), None)
    assert isinstance(r.equity_curve, pd.Series)


def test_rebalance_events_is_list():
    r = _engine().run(_universe_3full(), None)
    assert isinstance(r.rebalance_events, list)


def test_final_equity_is_positive():
    r = _engine().run(_universe_3full(daily_ret=0.01), None)
    assert r.final_equity is not None
    assert r.final_equity > 0


def test_strategy_total_return_is_set():
    r = _engine().run(_universe_3full(), None)
    assert r.strategy_total_return is not None


def test_per_ticker_contribution_is_dict():
    r = _engine().run(_universe_3full(), None)
    assert isinstance(r.per_ticker_contribution_pct, dict)


def test_exposure_pct_in_valid_range():
    r = _engine().run(_universe_3full(), None)
    assert r.exposure_pct is not None
    assert 0.0 <= r.exposure_pct <= 100.0


# ---------------------------------------------------------------------------
# Category 3: Equity curve correctness (tests 15–21)
# ---------------------------------------------------------------------------

def test_equity_curve_starts_at_initial_cash():
    r = _engine().run(_universe_3full(), None)
    assert float(r.equity_curve.iloc[0]) == pytest.approx(100_000.0)


def test_equity_curve_length_equals_trading_days():
    r = _engine().run(_universe_3full(), None)
    assert len(r.equity_curve) == len(_DATES)


def test_equity_curve_updates_from_asset_returns():
    # 3 tickers fully invested at 1% daily; day-1 equity = 100_000 * 1.01
    r = _engine().run(_universe_3full(daily_ret=0.01), None)
    assert float(r.equity_curve.iloc[1]) == pytest.approx(100_000.0 * 1.01)


def test_equity_curve_flat_for_zero_returns():
    r = _engine().run(_universe_3full(daily_ret=0.0), None)
    for val in r.equity_curve:
        assert float(val) == pytest.approx(100_000.0)


def test_final_equity_exceeds_initial_for_positive_returns():
    r = _engine().run(_universe_3full(daily_ret=0.01), None)
    assert r.final_equity > 100_000.0


def test_weights_by_date_is_dataframe():
    r = _engine().run(_universe_3full(), None)
    assert isinstance(r.weights_by_date, pd.DataFrame)


def test_cash_by_date_is_series():
    r = _engine().run(_universe_3full(), None)
    assert isinstance(r.cash_by_date, pd.Series)


# ---------------------------------------------------------------------------
# Category 4: Holdings and weight invariants (tests 22–28)
# ---------------------------------------------------------------------------

def test_run_uses_monthly_rebalance_dates():
    r = _engine().run(_universe_2months(), None)
    assert len(r.rebalance_events) == 2
    event_dates = {e["date"] for e in r.rebalance_events}
    assert pd.Timestamp("2020-01-02") in event_dates
    assert pd.Timestamp("2020-02-03") in event_dates


def test_run_selects_top_n_assets_on_rebalance():
    # 5 eligible tickers; only top 3 by composite_rs should be selected
    fm = _make_fm(
        _frow("2020-01-02", "AAA", crs=0.9),
        _frow("2020-01-02", "BBB", crs=0.8),
        _frow("2020-01-02", "CCC", crs=0.7),
        _frow("2020-01-02", "DDD", crs=0.6),
        _frow("2020-01-02", "EEE", crs=0.5),
    )
    ret = {t: _make_ret(t, 0.0, _DATES) for t in ["AAA", "BBB", "CCC", "DDD", "EEE"]}
    r = _engine().run({"feature_matrix": fm, "returns_by_ticker": ret}, None)
    assert r.rebalance_events[0]["holdings_after"] == ["AAA", "BBB", "CCC"]


def test_run_never_exceeds_top_n_holdings():
    r = _engine().run(_universe_3full(), None)
    for date, holdings in r.holdings_by_date.items():
        assert len(holdings) <= 3


def test_run_uses_one_over_top_n_allocation_not_one_over_selected_count():
    # 2 eligible tickers, top_n=3; new_weights must each be 1/3, not 1/2
    r = _engine().run(_universe_2tickers(), None)
    nw = r.rebalance_events[0]["new_weights"]
    assert nw["AAA"] == pytest.approx(1.0 / 3)
    assert nw["BBB"] == pytest.approx(1.0 / 3)


def test_unused_slots_remain_cash():
    # 2 tickers selected, 1 slot unused → cash = initial_cash / 3
    r = _engine().run(_universe_2tickers(), None)
    assert float(r.cash_by_date.iloc[0]) == pytest.approx(100_000.0 / 3, rel=1e-6)


def test_full_cash_when_no_assets_eligible():
    r = _engine().run(_universe_no_eligible(), None)
    # All cash — no holdings at any date
    for _, holdings in r.holdings_by_date.items():
        assert len(holdings) == 0
    # equity curve stays flat (cash_return=0)
    for val in r.equity_curve:
        assert float(val) == pytest.approx(100_000.0)


def test_holdings_by_date_is_populated():
    r = _engine().run(_universe_3full(), None)
    assert len(r.holdings_by_date) == len(_DATES)
    # Every date in the equity curve should be in holdings_by_date
    for ts in r.equity_curve.index:
        assert ts in r.holdings_by_date


# ---------------------------------------------------------------------------
# Category 5: Rebalance events (tests 29–33)
# ---------------------------------------------------------------------------

def test_no_daily_rebalancing_between_rebalance_dates():
    r = _engine().run(_universe_3full(), None)
    # All 5 dates are in Jan 2020; only one rebalance event expected
    assert len(r.rebalance_events) == 1


def test_no_intramonth_exit_logic():
    # Holdings should remain constant across all dates within a single month
    r = _engine().run(_universe_3full(daily_ret=-0.01), None)  # negative returns
    first = r.holdings_by_date[_DATES[0]]
    for ts in _DATES[1:]:
        assert r.holdings_by_date[ts] == first


def test_trades_only_on_rebalance_dates():
    r = _engine().run(_universe_2months(), None)
    rebalance_ts = {e["date"] for e in r.rebalance_events}
    assert rebalance_ts == {pd.Timestamp("2020-01-02"), pd.Timestamp("2020-02-03")}


def test_trades_record_old_and_new_weights():
    r = _engine().run(_universe_3full(), None)
    ev = r.rebalance_events[0]
    assert "old_weights" in ev
    assert "new_weights" in ev
    assert "holdings_before" in ev
    assert "holdings_after" in ev


def test_run_applies_hysteresis_between_months():
    # Month 1: AAA(0.9) + BBB(0.8) selected (top_n=3, only 2 eligible)
    # Month 2: AAA has rp=0.6 (>= 0.50 → keep), DDD enters with crs=0.95
    # Expected: AAA kept (hysteresis), DDD fills the open slot
    fm = _make_fm(
        _frow("2020-01-02", "AAA", crs=0.9, rp=0.95),
        _frow("2020-01-02", "BBB", crs=0.8, rp=0.90),
        _frow("2020-02-03", "AAA", crs=0.5, rp=0.60),  # weaker but above threshold
        _frow("2020-02-03", "BBB", crs=0.8, rp=0.90),
        _frow("2020-02-03", "DDD", crs=0.95, rp=0.99),  # new strong entrant
    )
    tickers = ["AAA", "BBB", "DDD"]
    ret = {t: _make_ret(t, 0.001, _DATES_2M) for t in tickers}
    r = _engine().run({"feature_matrix": fm, "returns_by_ticker": ret}, None)
    feb_ev = next(e for e in r.rebalance_events if e["date"] == pd.Timestamp("2020-02-03"))
    holdings_feb = set(feb_ev["holdings_after"])
    assert "AAA" in holdings_feb  # kept by hysteresis
    assert "DDD" in holdings_feb  # entered as fill


# ---------------------------------------------------------------------------
# Category 5b: Cash return and cash bounds
# ---------------------------------------------------------------------------

def test_cash_return_is_applied_to_cash_sleeve():
    # 2 tickers, top_n=3 → 1 cash slot; cash_return=0.02/day
    cfg = RotationBacktesterConfig(cash_return=0.02)
    fm = _make_fm(_frow("2020-01-02", "AAA"), _frow("2020-01-02", "BBB"))
    ret = {
        "AAA": _make_ret("AAA", 0.0, _DATES),
        "BBB": _make_ret("BBB", 0.0, _DATES),
    }
    r = RotationBacktester(cfg).run({"feature_matrix": fm, "returns_by_ticker": ret}, None)
    # Initial cash = 100_000 / 3; after day 0 returns, cash = (100_000/3) * 1.02
    initial_cash_slice = 100_000.0 / 3
    expected_cash_day1 = initial_cash_slice * 1.02
    # cash_by_date[0] = cash after rebalance (before applying returns)
    # cash_by_date[1] = cash_by_date[0] * 1.02 (after day-0 cash return applied)
    assert float(r.cash_by_date.iloc[0]) == pytest.approx(initial_cash_slice, rel=1e-6)
    assert float(r.cash_by_date.iloc[1]) == pytest.approx(expected_cash_day1, rel=1e-6)


def test_cash_by_date_is_between_zero_and_equity_or_weight_bounds():
    r = _engine().run(_universe_2tickers(), None)
    for i, (ts, cash_val) in enumerate(r.cash_by_date.items()):
        equity_val = float(r.equity_curve.iloc[i])
        assert float(cash_val) >= 0.0
        assert float(cash_val) <= equity_val + 1e-9


def test_run_is_deterministic():
    ud = _universe_3full(daily_ret=0.01)
    r1 = _engine().run(ud, None)
    r2 = _engine().run(ud, None)
    assert list(r1.equity_curve) == list(r2.equity_curve)
    assert r1.final_equity == pytest.approx(r2.final_equity)
    assert r1.strategy_total_return == pytest.approx(r2.strategy_total_return)


# ---------------------------------------------------------------------------
# Category 6: Weights and cash bounds (tests 34–36)
# ---------------------------------------------------------------------------

def test_weights_by_date_sum_lte_one():
    r = _engine().run(_universe_3full(), None)
    for date, row in r.weights_by_date.iterrows():
        assert float(row.sum()) <= 1.0 + 1e-9


def test_weights_are_non_negative():
    r = _engine().run(_universe_3full(daily_ret=0.01), None)
    for date, row in r.weights_by_date.iterrows():
        for w in row:
            assert float(w) >= 0.0


def test_cash_by_date_is_non_negative():
    r = _engine().run(_universe_3full(), None)
    for val in r.cash_by_date:
        assert float(val) >= 0.0


# ---------------------------------------------------------------------------
# Category 7: Metrics correctness (tests 37–38)
# ---------------------------------------------------------------------------

def test_total_return_matches_final_equity():
    r = _engine().run(_universe_3full(daily_ret=0.01), None)
    expected = r.final_equity / 100_000.0 - 1.0
    assert r.strategy_total_return == pytest.approx(expected)


def test_calmar_is_reported():
    r = _engine().run(_universe_3full(daily_ret=0.01), None)
    # strategy_calmar is a float (may be NaN for no-drawdown case)
    assert r.strategy_calmar is not None
    assert isinstance(float(r.strategy_calmar), float)


# ---------------------------------------------------------------------------
# Category 8: Diagnostics (tests 39–40)
# ---------------------------------------------------------------------------

def test_diagnostics_mark_precomputed_toy_mode():
    r = _engine().run(_universe_3full(), None)
    assert r.v1_2_metric_sources["mode"] == "PRECOMPUTED_TOY_ROTATION_PATH"
    assert r.v1_2_metric_sources["research_valid"] is False
    assert r.v1_2_metric_sources["market_data_used"] is False
    assert r.v1_2_metric_sources["strategy_lab_runner_used"] is False


def test_diagnostics_mark_verdict_impact_none():
    r = _engine().run(_universe_3full(), None)
    assert r.v1_2_metric_sources["v1_1_verdict_impact"] == "NONE"
    assert r.v1_2_metric_sources["live_go_emitted"] is False
    assert r.v1_2_metric_sources["research_go_emitted"] is False


# ---------------------------------------------------------------------------
# Category 9: Source-token guardrails (test 41)
# ---------------------------------------------------------------------------

def test_run_outputs_no_live_go_and_no_research_go():
    import rotation_backtester as _m
    src = inspect.getsource(_m)
    assert "LIVE-GO" not in src
    assert "RESEARCH-GO" not in src
    assert "yfinance" not in src


# ---------------------------------------------------------------------------
# Cross-module smoke tests (tests 36-41 from payload; listed here as extras)
# These verify the other modules are still importable with the correct interface
# after our changes to rotation_backtester.py.
# ---------------------------------------------------------------------------

def test_random_selection_comparator_interface_intact():
    from rotation_random_selection_comparator import RandomSelectionComparatorConfig
    c = RandomSelectionComparatorConfig()
    assert c.n_simulations == 1000
    assert c.top_n == 3
    assert c.comparator_label == "RANDOMIZED_SELECTION_P95_REPORT_ONLY"


def test_rotation_benchmark_b2_interface_intact():
    from rotation_benchmark_b2 import EqualWeightBenchmarkConfig, calculate_calmar
    c = EqualWeightBenchmarkConfig()
    assert c.benchmark_label == "B2_EQUAL_WEIGHT_UNIVERSE_REPORT_ONLY"
    assert c.annualization_days == 252


def test_rotation_feature_matrix_interface_intact():
    from rotation_feature_matrix import RotationFeatureConfig
    c = RotationFeatureConfig()
    assert c.rs_short_window == 63
    assert c.rs_mid_window == 126
    assert c.rs_long_window == 252


def test_rotation_backtester_scaffold_interface_intact():
    c = RotationBacktesterConfig()
    assert c.top_n == 3
    assert c.hysteresis_threshold == pytest.approx(0.50)
    assert c.annualization_days == 252


def test_relative_strength_rotation_scaffold_interface_intact():
    from strategy_variants import RelativeStrengthRotation_v1
    s = RelativeStrengthRotation_v1()
    desc = s.describe()
    assert desc["top_n"] == 3
    assert desc["universe_size"] == 15


def test_relative_strength_rotation_spec_interface_intact():
    # Verify spec-locked invariants still hold (universe=15, top_n=3, weights 0.40/0.40/0.20)
    from strategy_variants import RelativeStrengthRotation_v1
    s = RelativeStrengthRotation_v1()
    desc = s.describe()
    assert desc["universe_size"] == 15
    weights = desc["weights"]
    assert abs(weights["relative_strength_126d"] - 0.40) < 1e-9
    assert abs(weights["relative_strength_252d"] - 0.40) < 1e-9
    assert abs(weights["benchmark_relative_strength"] - 0.20) < 1e-9
