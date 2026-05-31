"""
Unit tests for RotationBacktester scaffold.

Deterministic toy dicts / dates only.
No market data. No real backtests. No runner execution.
"""

import inspect

import pandas as pd
import pytest

from rotation_backtester import (
    RotationBacktester,
    RotationBacktesterConfig,
    RotationBacktesterResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine(**cfg) -> RotationBacktester:
    return RotationBacktester(RotationBacktesterConfig(**cfg)) if cfg else RotationBacktester()


def _row(ticker, composite_rs, rank_percentile=1.0,
         trend=True, vol=True, liq=True):
    return {
        "ticker": ticker,
        "composite_rs": composite_rs,
        "rank_percentile": rank_percentile,
        "trend_filter_ema200": trend,
        "volatility_filter_atr_pct": vol,
        "liquidity_filter_volume_avg_20": liq,
    }


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_engine_constructs_with_defaults():
    e = _engine()
    assert e.config.top_n == 3
    assert e.config.hysteresis_threshold == pytest.approx(0.50)
    assert e.config.rebalance_frequency == "monthly"


def test_config_defaults_are_frozen_spec_values():
    c = RotationBacktesterConfig()
    assert c.top_n == 3
    assert c.hysteresis_threshold == pytest.approx(0.50)
    assert c.allow_leverage is False
    assert c.allow_shorting is False


def test_leverage_rejected():
    with pytest.raises(ValueError):
        RotationBacktester(RotationBacktesterConfig(allow_leverage=True))


def test_shorting_rejected():
    with pytest.raises(ValueError):
        RotationBacktester(RotationBacktesterConfig(allow_shorting=True))


def test_result_dataclass_exists_and_defaults_empty():
    r = RotationBacktesterResult()
    assert r.equity_curve == []
    assert r.per_ticker_contribution_pct == {}
    assert r.final_equity is None
    assert r.strategy_total_return is None


# ---------------------------------------------------------------------------
# run() must remain scaffold-only
# ---------------------------------------------------------------------------

def test_run_raises_not_implemented():
    e = _engine()
    with pytest.raises(NotImplementedError) as excinfo:
        e.run({"AAPL": [1, 2, 3]}, strategy=object())
    assert "scaffold only" in str(excinfo.value).lower()


def test_run_message_is_exact():
    e = _engine()
    with pytest.raises(NotImplementedError) as excinfo:
        e.run({}, None)
    assert str(excinfo.value) == (
        "RotationBacktester.run is not implemented yet; scaffold only."
    )


# ---------------------------------------------------------------------------
# select_rebalance_dates
# ---------------------------------------------------------------------------

def test_rebalance_dates_first_of_each_month():
    dates = pd.bdate_range("2020-01-01", "2020-03-31")
    out = _engine().select_rebalance_dates(dates)
    assert len(out) == 3
    assert out[0] == pd.Timestamp("2020-01-01")
    assert out[1].month == 2
    assert out[2].month == 3


def test_rebalance_dates_picks_first_available_trading_day():
    # First business day of Feb 2020 is the 3rd (Sat 1, Sun 2)
    dates = pd.bdate_range("2020-02-01", "2020-02-28")
    out = _engine().select_rebalance_dates(dates)
    assert len(out) == 1
    assert out[0] == pd.Timestamp("2020-02-03")


def test_rebalance_dates_unsorted_input():
    dates = [pd.Timestamp("2020-02-10"),
             pd.Timestamp("2020-01-15"),
             pd.Timestamp("2020-01-05"),
             pd.Timestamp("2020-02-03")]
    out = _engine().select_rebalance_dates(dates)
    assert out == [pd.Timestamp("2020-01-05"), pd.Timestamp("2020-02-03")]


def test_rebalance_dates_accepts_strings():
    out = _engine().select_rebalance_dates(["2021-06-15", "2021-06-01", "2021-07-02"])
    assert out == [pd.Timestamp("2021-06-01"), pd.Timestamp("2021-07-02")]


# ---------------------------------------------------------------------------
# validate_universe_data
# ---------------------------------------------------------------------------

def test_validate_universe_data_ok():
    assert _engine().validate_universe_data({"AAPL": [1, 2], "MSFT": [3, 4]}) is True


def test_validate_universe_data_rejects_non_dict():
    with pytest.raises(ValueError):
        _engine().validate_universe_data(["AAPL", "MSFT"])


def test_validate_universe_data_rejects_empty():
    with pytest.raises(ValueError):
        _engine().validate_universe_data({})


def test_validate_universe_data_rejects_none_value():
    with pytest.raises(ValueError):
        _engine().validate_universe_data({"AAPL": None})


def test_validate_universe_data_rejects_empty_value():
    with pytest.raises(ValueError):
        _engine().validate_universe_data({"AAPL": []})


# ---------------------------------------------------------------------------
# select_top_n_assets — eligibility filtering
# ---------------------------------------------------------------------------

def test_select_filters_out_trend_failures():
    rows = [_row("AAPL", 0.9, trend=False), _row("MSFT", 0.8)]
    assert _engine().select_top_n_assets(rows) == ["MSFT"]


def test_select_filters_out_volatility_failures():
    rows = [_row("AAPL", 0.9, vol=False), _row("MSFT", 0.8)]
    assert _engine().select_top_n_assets(rows) == ["MSFT"]


def test_select_filters_out_liquidity_failures():
    rows = [_row("AAPL", 0.9, liq=False), _row("MSFT", 0.8)]
    assert _engine().select_top_n_assets(rows) == ["MSFT"]


# ---------------------------------------------------------------------------
# select_top_n_assets — invalid composite_rs rejection
# ---------------------------------------------------------------------------

def test_select_rejects_nan_composite():
    rows = [_row("AAPL", float("nan")), _row("MSFT", 0.8)]
    assert _engine().select_top_n_assets(rows) == ["MSFT"]


def test_select_rejects_inf_composite():
    rows = [_row("AAPL", float("inf")), _row("MSFT", 0.8)]
    assert _engine().select_top_n_assets(rows) == ["MSFT"]


def test_select_rejects_none_composite():
    rows = [_row("AAPL", None), _row("MSFT", 0.8)]
    assert _engine().select_top_n_assets(rows) == ["MSFT"]


def test_select_rejects_missing_composite():
    bad = {"ticker": "AAPL", "rank_percentile": 1.0,
           "trend_filter_ema200": True,
           "volatility_filter_atr_pct": True,
           "liquidity_filter_volume_avg_20": True}
    rows = [bad, _row("MSFT", 0.8)]
    assert _engine().select_top_n_assets(rows) == ["MSFT"]


def test_select_rejects_nan_rank_percentile():
    rows = [_row("AAPL", 0.9, rank_percentile=float("nan")), _row("MSFT", 0.8)]
    assert _engine().select_top_n_assets(rows) == ["MSFT"]


# ---------------------------------------------------------------------------
# select_top_n_assets — top-N ordering and cap
# ---------------------------------------------------------------------------

def test_select_top_n_picks_highest_composite():
    rows = [_row("AAPL", 0.5), _row("MSFT", 0.9),
            _row("NVDA", 0.8), _row("AMD", 0.7)]
    # No existing holdings; top 3 by composite: MSFT, NVDA, AMD
    assert _engine().select_top_n_assets(rows) == ["MSFT", "NVDA", "AMD"]


def test_select_never_exceeds_top_n():
    rows = [_row(t, score) for t, score in
            [("AAPL", 0.9), ("MSFT", 0.8), ("NVDA", 0.7),
             ("AMD", 0.6), ("META", 0.5)]]
    out = _engine().select_top_n_assets(rows)
    assert len(out) == 3


def test_select_tie_break_alphabetical():
    rows = [_row("MSFT", 0.8), _row("AAPL", 0.8), _row("NVDA", 0.8), _row("AMD", 0.8)]
    # All tied; tie-break ticker ascending → AAPL, AMD, MSFT
    assert _engine().select_top_n_assets(rows) == ["AAPL", "AMD", "MSFT"]


def test_select_fewer_than_n_eligible():
    rows = [_row("AAPL", 0.9), _row("MSFT", 0.8)]
    assert _engine().select_top_n_assets(rows) == ["AAPL", "MSFT"]


def test_select_no_eligible_returns_empty():
    rows = [_row("AAPL", 0.9, trend=False), _row("MSFT", 0.8, vol=False)]
    assert _engine().select_top_n_assets(rows) == []


# ---------------------------------------------------------------------------
# select_top_n_assets — hysteresis
# ---------------------------------------------------------------------------

def test_hysteresis_keeps_existing_above_threshold():
    # Existing holding IBM has lower composite but rank >= 0.50; it should be
    # kept in preference to a marginally stronger newcomer when slots are tight.
    rows = [
        _row("IBM", 0.55, rank_percentile=0.60),   # existing, qualifies to keep
        _row("AAPL", 0.90, rank_percentile=0.95),
        _row("MSFT", 0.85, rank_percentile=0.90),
        _row("NVDA", 0.60, rank_percentile=0.70),  # newcomer, just above IBM
    ]
    out = _engine().select_top_n_assets(rows, existing_holdings=["IBM"])
    assert "IBM" in out
    assert len(out) == 3
    # AAPL and MSFT are strongest newcomers; NVDA is squeezed out by held IBM
    assert set(out) == {"IBM", "AAPL", "MSFT"}


def test_hysteresis_drops_existing_below_threshold():
    rows = [
        _row("IBM", 0.55, rank_percentile=0.40),   # existing but rank < 0.50
        _row("AAPL", 0.90, rank_percentile=0.95),
        _row("MSFT", 0.85, rank_percentile=0.90),
        _row("NVDA", 0.80, rank_percentile=0.85),
    ]
    out = _engine().select_top_n_assets(rows, existing_holdings=["IBM"])
    assert "IBM" not in out
    assert set(out) == {"AAPL", "MSFT", "NVDA"}


def test_hysteresis_keepset_larger_than_n_trims_to_n():
    # Four existing holdings all qualify to keep; must trim to top 3 by composite.
    rows = [
        _row("AAPL", 0.95, rank_percentile=0.95),
        _row("MSFT", 0.90, rank_percentile=0.90),
        _row("NVDA", 0.85, rank_percentile=0.85),
        _row("AMD", 0.60, rank_percentile=0.55),   # weakest of the held set
    ]
    out = _engine().select_top_n_assets(
        rows, existing_holdings=["AAPL", "MSFT", "NVDA", "AMD"]
    )
    assert len(out) == 3
    assert "AMD" not in out
    assert set(out) == {"AAPL", "MSFT", "NVDA"}


def test_hysteresis_threshold_boundary_inclusive():
    # rank exactly == 0.50 should be kept (>= threshold)
    rows = [
        _row("IBM", 0.40, rank_percentile=0.50),
        _row("AAPL", 0.90, rank_percentile=0.95),
        _row("MSFT", 0.85, rank_percentile=0.90),
    ]
    out = _engine().select_top_n_assets(rows, existing_holdings=["IBM"])
    assert "IBM" in out


# ---------------------------------------------------------------------------
# calculate_equal_weights / calculate_cash_weight
# ---------------------------------------------------------------------------

def test_equal_weights_full_portfolio():
    w = _engine().calculate_equal_weights(["AAPL", "MSFT", "NVDA"])
    assert w == {"AAPL": pytest.approx(1/3),
                 "MSFT": pytest.approx(1/3),
                 "NVDA": pytest.approx(1/3)}


def test_equal_weights_are_one_over_top_n_not_one_over_selected():
    # Only 2 selected, but each still gets 1/3 (NOT 1/2)
    w = _engine().calculate_equal_weights(["AAPL", "MSFT"])
    assert w["AAPL"] == pytest.approx(1/3)
    assert w["MSFT"] == pytest.approx(1/3)


def test_equal_weights_reject_more_than_top_n():
    with pytest.raises(ValueError):
        _engine().calculate_equal_weights(["A", "B", "C", "D"])


def test_cash_weight_full_portfolio_is_zero():
    assert _engine().calculate_cash_weight(["AAPL", "MSFT", "NVDA"]) == pytest.approx(0.0)


def test_cash_weight_two_selected_is_one_third():
    assert _engine().calculate_cash_weight(["AAPL", "MSFT"]) == pytest.approx(1/3)


def test_cash_weight_empty_is_full_cash():
    assert _engine().calculate_cash_weight([]) == pytest.approx(1.0)


def test_weights_plus_cash_sum_to_one():
    selected = ["AAPL", "MSFT"]
    e = _engine()
    total = sum(e.calculate_equal_weights(selected).values()) + e.calculate_cash_weight(selected)
    assert total == pytest.approx(1.0)


def test_no_leverage_total_weight_le_one():
    selected = ["AAPL", "MSFT", "NVDA"]
    e = _engine()
    total = sum(e.calculate_equal_weights(selected).values())
    assert total <= 1.0 + 1e-9


# ---------------------------------------------------------------------------
# Guardrails: no market-data / no verdict leakage
# ---------------------------------------------------------------------------

def test_no_yfinance_import_in_module():
    import rotation_backtester
    src = inspect.getsource(rotation_backtester)
    assert "yfinance" not in src
    assert "import yf" not in src


def test_no_research_go_or_live_go_in_module():
    import rotation_backtester
    src = inspect.getsource(rotation_backtester)
    assert "RESEARCH-GO" not in src
    assert "LIVE-GO" not in src
