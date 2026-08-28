"""
Unit tests for the rotation feature-matrix builder.

Deterministic toy OHLCV only. No market data. No fetch. No backtests. No runner.
"""

import inspect

import numpy as np
import pandas as pd
import pytest

import rotation_feature_matrix as rfm
from rotation_feature_matrix import (
    RotationFeatureConfig,
    add_cross_sectional_ranks,
    build_equal_weight_universe_index,
    build_rotation_feature_matrix,
    compute_rotation_features_for_ticker,
)


# ---------------------------------------------------------------------------
# Toy data
# ---------------------------------------------------------------------------

def _toy_ohlcv(n=320, base=100.0, slope=0.5, vol=2_000_000.0, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2015-01-01", periods=n)
    osc = np.sin(np.linspace(0, 12 * np.pi, n)) * 2.0
    close = base + slope * np.arange(n) + osc
    return pd.DataFrame(
        {
            "open": close * 0.999,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": np.full(n, vol),
        },
        index=dates,
    )


def _toy_universe(n=320):
    return {
        "AAA": _toy_ohlcv(n, base=100, slope=0.6, seed=1),
        "BBB": _toy_ohlcv(n, base=120, slope=0.3, seed=2),
        "CCC": _toy_ohlcv(n, base=80, slope=0.45, seed=3),
    }


def _rank_input():
    """A small long feature matrix to drive add_cross_sectional_ranks directly."""
    rows = []
    for date in ("2020-01-01", "2020-02-03"):
        rows += [
            {"date": pd.Timestamp(date), "ticker": "AAA",
             "relative_strength_126d": 1.30, "relative_strength_252d": 1.40,
             "benchmark_relative_strength": 1.20,
             "trend_filter_ema200": True, "volatility_filter_atr_pct": True,
             "liquidity_filter_volume_avg_20": True},
            {"date": pd.Timestamp(date), "ticker": "BBB",
             "relative_strength_126d": 1.10, "relative_strength_252d": 1.05,
             "benchmark_relative_strength": 1.02,
             "trend_filter_ema200": True, "volatility_filter_atr_pct": True,
             "liquidity_filter_volume_avg_20": True},
        ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 1-3 config / imports
# ---------------------------------------------------------------------------

def test_config_defaults_match_spec():
    c = RotationFeatureConfig()
    assert c.rs_short_window == 63
    assert c.rs_mid_window == 126
    assert c.rs_long_window == 252
    assert c.ema_window == 200
    assert c.atr_window == 14
    assert c.volume_window == 20
    assert c.volatility_atr_pct_max == pytest.approx(0.08)
    assert c.liquidity_volume_avg_20_min == pytest.approx(1_000_000)
    assert c.require_shifted_features is True


def test_module_does_not_import_yfinance():
    src = inspect.getsource(rfm)
    assert "yfinance" not in src
    assert "import yf" not in src


def test_module_does_not_import_backtester():
    src = inspect.getsource(rfm)
    assert "import backtester" not in src
    assert "from backtester" not in src


# ---------------------------------------------------------------------------
# 4-6 equal-weight universe index
# ---------------------------------------------------------------------------

def test_equal_weight_universe_index_starts_at_one():
    idx = build_equal_weight_universe_index(_toy_universe(50))
    assert idx.iloc[0] == pytest.approx(1.0)


def test_equal_weight_universe_index_is_deterministic():
    u = _toy_universe(60)
    a = build_equal_weight_universe_index(u)
    b = build_equal_weight_universe_index(u)
    pd.testing.assert_series_equal(a, b)


def test_equal_weight_universe_index_uses_close_returns():
    # Single ticker: index must reproduce that ticker's normalized close path.
    df = _toy_ohlcv(40, base=100, slope=1.0, seed=7)
    idx = build_equal_weight_universe_index({"AAA": df})
    expected = df["close"] / df["close"].iloc[0]
    np.testing.assert_allclose(idx.to_numpy(), expected.to_numpy(), rtol=1e-9)


# ---------------------------------------------------------------------------
# 7-10 matrix construction / validation
# ---------------------------------------------------------------------------

def test_build_feature_matrix_requires_non_empty_universe():
    with pytest.raises(ValueError):
        build_rotation_feature_matrix({})


def test_build_feature_matrix_rejects_missing_ohlcv_columns():
    bad = _toy_ohlcv(50).drop(columns=["volume"])
    with pytest.raises(ValueError):
        build_rotation_feature_matrix({"AAA": bad})


def test_feature_matrix_contains_required_feature_columns():
    m = build_rotation_feature_matrix(_toy_universe())
    for col in rfm.FEATURE_COLUMNS:
        assert col in m.columns
    assert "date" in m.columns
    assert "ticker" in m.columns


def test_feature_matrix_preserves_ticker_identity():
    m = build_rotation_feature_matrix(_toy_universe())
    assert set(m["ticker"].unique()) == {"AAA", "BBB", "CCC"}


# ---------------------------------------------------------------------------
# 11-17 shift-by-one (no same-bar lookahead)
# ---------------------------------------------------------------------------

def _features_last_date(df, universe_index):
    feats = compute_rotation_features_for_ticker("AAA", df, universe_index)
    return feats.iloc[-1]


def _shift_invariance(col, mutate):
    """Mutating the LAST bar must not change a feature at the last date
    (feature only depends on data up to T-1)."""
    df = _toy_ohlcv(320, seed=11)
    universe_index = build_equal_weight_universe_index({"AAA": df, "BBB": _toy_ohlcv(320, seed=12)})
    before = _features_last_date(df, universe_index)[col]
    df2 = df.copy()
    mutate(df2)
    after = compute_rotation_features_for_ticker("AAA", df2, universe_index).iloc[-1][col]
    assert before == pytest.approx(after), f"{col} changed when last bar mutated (lookahead!)"


def test_relative_strength_63d_is_shifted_by_one():
    _shift_invariance("relative_strength_63d", lambda d: d.__setitem__("close", d["close"].copy()))
    # explicit last-bar mutation
    df = _toy_ohlcv(320, seed=11)
    u = build_equal_weight_universe_index({"AAA": df, "BBB": _toy_ohlcv(320, seed=12)})
    before = compute_rotation_features_for_ticker("AAA", df, u).iloc[-1]["relative_strength_63d"]
    df2 = df.copy()
    df2.iloc[-1, df2.columns.get_loc("close")] = df2["close"].iloc[-1] * 5
    after = compute_rotation_features_for_ticker("AAA", df2, u).iloc[-1]["relative_strength_63d"]
    assert before == pytest.approx(after)


def test_relative_strength_126d_is_shifted_by_one():
    df = _toy_ohlcv(320, seed=11)
    u = build_equal_weight_universe_index({"AAA": df, "BBB": _toy_ohlcv(320, seed=12)})
    before = compute_rotation_features_for_ticker("AAA", df, u).iloc[-1]["relative_strength_126d"]
    df2 = df.copy()
    df2.iloc[-1, df2.columns.get_loc("close")] *= 5
    after = compute_rotation_features_for_ticker("AAA", df2, u).iloc[-1]["relative_strength_126d"]
    assert before == pytest.approx(after)


def test_relative_strength_252d_is_shifted_by_one():
    df = _toy_ohlcv(320, seed=11)
    u = build_equal_weight_universe_index({"AAA": df, "BBB": _toy_ohlcv(320, seed=12)})
    before = compute_rotation_features_for_ticker("AAA", df, u).iloc[-1]["relative_strength_252d"]
    df2 = df.copy()
    df2.iloc[-1, df2.columns.get_loc("close")] *= 5
    after = compute_rotation_features_for_ticker("AAA", df2, u).iloc[-1]["relative_strength_252d"]
    assert before == pytest.approx(after)


def test_benchmark_relative_strength_is_shifted_by_one():
    df = _toy_ohlcv(320, seed=11)
    u = build_equal_weight_universe_index({"AAA": df, "BBB": _toy_ohlcv(320, seed=12)})
    before = compute_rotation_features_for_ticker("AAA", df, u).iloc[-1]["benchmark_relative_strength"]
    df2 = df.copy()
    df2.iloc[-1, df2.columns.get_loc("close")] *= 5
    after = compute_rotation_features_for_ticker("AAA", df2, u).iloc[-1]["benchmark_relative_strength"]
    assert before == pytest.approx(after)


def test_trend_filter_ema200_is_shifted_by_one():
    df = _toy_ohlcv(320, seed=11)
    u = build_equal_weight_universe_index({"AAA": df, "BBB": _toy_ohlcv(320, seed=12)})
    before = compute_rotation_features_for_ticker("AAA", df, u).iloc[-1]["trend_filter_ema200"]
    df2 = df.copy()
    df2.iloc[-1, df2.columns.get_loc("close")] *= 0.001
    after = compute_rotation_features_for_ticker("AAA", df2, u).iloc[-1]["trend_filter_ema200"]
    assert bool(before) == bool(after)


def test_atr_pct_filter_is_shifted_by_one():
    df = _toy_ohlcv(320, seed=11)
    u = build_equal_weight_universe_index({"AAA": df, "BBB": _toy_ohlcv(320, seed=12)})
    before = compute_rotation_features_for_ticker("AAA", df, u).iloc[-1]["volatility_filter_atr_pct"]
    df2 = df.copy()
    df2.iloc[-1, df2.columns.get_loc("high")] *= 10
    df2.iloc[-1, df2.columns.get_loc("low")] *= 0.1
    after = compute_rotation_features_for_ticker("AAA", df2, u).iloc[-1]["volatility_filter_atr_pct"]
    assert bool(before) == bool(after)


def test_liquidity_filter_volume_avg_20_is_shifted_by_one():
    df = _toy_ohlcv(320, seed=11)
    u = build_equal_weight_universe_index({"AAA": df, "BBB": _toy_ohlcv(320, seed=12)})
    before = compute_rotation_features_for_ticker("AAA", df, u).iloc[-1]["liquidity_filter_volume_avg_20"]
    df2 = df.copy()
    df2.iloc[-1, df2.columns.get_loc("volume")] = 1.0
    after = compute_rotation_features_for_ticker("AAA", df2, u).iloc[-1]["liquidity_filter_volume_avg_20"]
    assert bool(before) == bool(after)


# ---------------------------------------------------------------------------
# 18-20 no fill / no interpolation
# ---------------------------------------------------------------------------

def _gap_setup():
    df = _toy_ohlcv(320, seed=11)
    u = build_equal_weight_universe_index({"AAA": df, "BBB": _toy_ohlcv(320, seed=12)})
    gap = 200
    df2 = df.copy()
    df2.iloc[gap, df2.columns.get_loc("close")] = np.nan
    feats = compute_rotation_features_for_ticker("AAA", df2, u)
    return feats, gap


def test_no_forward_fill_of_missing_close():
    assert "ffill" not in inspect.getsource(rfm)
    assert "method='pad'" not in inspect.getsource(rfm)
    feats, gap = _gap_setup()
    # date gap+1 consumes close[gap] via shift(1); must stay NaN (no ffill)
    assert np.isnan(feats.iloc[gap + 1]["relative_strength_63d"])


def test_no_backfill_of_missing_close():
    src = inspect.getsource(rfm)
    assert "bfill" not in src
    assert "backfill" not in src
    feats, gap = _gap_setup()
    # if close[gap] were backfilled from gap+1, this would be finite
    assert np.isnan(feats.iloc[gap + 1]["relative_strength_126d"])


def test_no_interpolation_of_missing_close():
    assert "interpolate" not in inspect.getsource(rfm)
    feats, gap = _gap_setup()
    assert np.isnan(feats.iloc[gap + 1]["relative_strength_252d"])


# ---------------------------------------------------------------------------
# 21-25 eligibility
# ---------------------------------------------------------------------------

def _one_date_rows():
    base = _rank_input()
    return base[base["date"] == pd.Timestamp("2020-01-01")].copy()


def test_nan_features_make_row_ineligible():
    rows = _one_date_rows()
    rows.loc[rows["ticker"] == "AAA", "relative_strength_126d"] = np.nan
    out = add_cross_sectional_ranks(rows)
    aaa = out[out["ticker"] == "AAA"].iloc[0]
    assert aaa["is_rotation_eligible"] == False  # noqa: E712
    assert np.isnan(aaa["composite_rs"])


def test_inf_features_make_row_ineligible():
    rows = _one_date_rows()
    rows.loc[rows["ticker"] == "AAA", "relative_strength_252d"] = np.inf
    out = add_cross_sectional_ranks(rows)
    aaa = out[out["ticker"] == "AAA"].iloc[0]
    assert aaa["is_rotation_eligible"] == False  # noqa: E712
    assert np.isnan(aaa["composite_rs"])


def test_trend_filter_false_makes_row_ineligible():
    rows = _one_date_rows()
    rows.loc[rows["ticker"] == "AAA", "trend_filter_ema200"] = False
    out = add_cross_sectional_ranks(rows)
    aaa = out[out["ticker"] == "AAA"].iloc[0]
    assert aaa["is_rotation_eligible"] == False  # noqa: E712


def test_volatility_filter_false_makes_row_ineligible():
    rows = _one_date_rows()
    rows.loc[rows["ticker"] == "AAA", "volatility_filter_atr_pct"] = False
    out = add_cross_sectional_ranks(rows)
    aaa = out[out["ticker"] == "AAA"].iloc[0]
    assert aaa["is_rotation_eligible"] == False  # noqa: E712


def test_liquidity_filter_false_makes_row_ineligible():
    rows = _one_date_rows()
    rows.loc[rows["ticker"] == "AAA", "liquidity_filter_volume_avg_20"] = False
    out = add_cross_sectional_ranks(rows)
    aaa = out[out["ticker"] == "AAA"].iloc[0]
    assert aaa["is_rotation_eligible"] == False  # noqa: E712


# ---------------------------------------------------------------------------
# 26-31 ranking
# ---------------------------------------------------------------------------

def test_cross_sectional_ranks_are_per_date():
    rows = _rank_input()
    # make BBB the strongest on the second date only
    mask = (rows["date"] == pd.Timestamp("2020-02-03")) & (rows["ticker"] == "BBB")
    rows.loc[mask, ["relative_strength_126d", "relative_strength_252d", "benchmark_relative_strength"]] = [9.0, 9.0, 9.0]
    out = add_cross_sectional_ranks(rows)
    d1 = out[out["date"] == pd.Timestamp("2020-01-01")]
    d2 = out[out["date"] == pd.Timestamp("2020-02-03")]
    # date1: AAA strongest; date2: BBB strongest
    assert d1.sort_values("composite_rs", ascending=False).iloc[0]["ticker"] == "AAA"
    assert d2.sort_values("composite_rs", ascending=False).iloc[0]["ticker"] == "BBB"


def test_cross_sectional_rank_ties_break_by_ticker():
    rows = _one_date_rows()
    # identical features for both -> equal composite -> ticker ascending order
    rows.loc[rows["ticker"] == "BBB",
             ["relative_strength_126d", "relative_strength_252d", "benchmark_relative_strength"]] = [1.30, 1.40, 1.20]
    out = add_cross_sectional_ranks(rows)
    assert out.iloc[0]["composite_rs"] == pytest.approx(out.iloc[1]["composite_rs"])
    assert list(out["ticker"]) == ["AAA", "BBB"]


def test_composite_rs_uses_fixed_40_40_20_weights():
    rows = _one_date_rows()
    out = add_cross_sectional_ranks(rows)
    aaa = out[out["ticker"] == "AAA"].iloc[0]
    bbb = out[out["ticker"] == "BBB"].iloc[0]
    # AAA dominates all three -> pct rank 1.0 each -> composite 1.0
    assert aaa["composite_rs"] == pytest.approx(0.40 * 1.0 + 0.40 * 1.0 + 0.20 * 1.0)
    # BBB lowest of two -> pct rank 0.5 each -> composite 0.5
    assert bbb["composite_rs"] == pytest.approx(0.40 * 0.5 + 0.40 * 0.5 + 0.20 * 0.5)


def test_rank_percentile_is_between_zero_and_one():
    out = add_cross_sectional_ranks(_rank_input())
    rp = out["rank_percentile"].dropna()
    assert ((rp >= 0.0) & (rp <= 1.0)).all()


def test_invalid_rows_do_not_receive_valid_rank():
    rows = _one_date_rows()
    rows.loc[rows["ticker"] == "AAA", "benchmark_relative_strength"] = np.nan
    out = add_cross_sectional_ranks(rows)
    aaa = out[out["ticker"] == "AAA"].iloc[0]
    assert np.isnan(aaa["composite_rs"])
    assert np.isnan(aaa["rank_percentile"])
    assert aaa["is_rotation_eligible"] == False  # noqa: E712


def test_add_cross_sectional_ranks_is_deterministic():
    rows = _rank_input()
    a = add_cross_sectional_ranks(rows)
    b = add_cross_sectional_ranks(rows)
    pd.testing.assert_frame_equal(a, b)


# ---------------------------------------------------------------------------
# 32 determinism of full builder
# ---------------------------------------------------------------------------

def test_build_rotation_feature_matrix_is_deterministic():
    u = _toy_universe()
    a = build_rotation_feature_matrix(u)
    b = build_rotation_feature_matrix(u)
    pd.testing.assert_frame_equal(a, b)


# ---------------------------------------------------------------------------
# 33-34 no verdict leakage
# ---------------------------------------------------------------------------

def test_feature_builder_outputs_no_live_go():
    assert "LIVE-GO" not in inspect.getsource(rfm)


def test_feature_builder_outputs_no_research_go():
    assert "RESEARCH-GO" not in inspect.getsource(rfm)


# ---------------------------------------------------------------------------
# 35-37 prior gates still intact (cross-module smoke checks)
# ---------------------------------------------------------------------------

def test_rotation_backtester_scaffold_tests_still_pass():
    from rotation_backtester import RotationBacktester
    e = RotationBacktester()
    assert e.calculate_cash_weight([]) == pytest.approx(1.0)
    assert e.config.top_n == 3


def test_relative_strength_rotation_scaffold_tests_still_pass():
    from strategy_variants import RelativeStrengthRotation_v1
    v = RelativeStrengthRotation_v1()
    assert v.STRATEGY_ID == "RelativeStrengthRotation_v1"
    assert len(v.UNIVERSE) == 15


def test_relative_strength_rotation_spec_tests_still_pass():
    import pathlib
    spec = (pathlib.Path(__file__).parent.parent
            / "RESEARCH_SPEC_RELATIVE_STRENGTH_ROTATION_V1.md")
    text = spec.read_text(encoding="utf-8")
    assert "## 10. Ranking Logic" in text
    assert "0.40 * rank(relative_strength_126d)" in text
