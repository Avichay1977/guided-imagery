"""
Unit and integration tests for rotation_research_orchestrator.

All toy inputs only. No real market data, no yfinance, no strategy_lab_runner,
no real research backtest.
"""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rotation_research_orchestrator import (
    FROZEN_UNIVERSE,
    SPLIT_SPEC_VERSION,
    TRAIN_YEARS,
    TEST_YEARS,
    STEP_YEARS,
    WINDOW_START,
    WINDOW_END,
    OrchestratorConfig,
    OrchestratorRunResult,
    OrchestratorSplitResult,
    build_returns_by_ticker,
    compute_aggregate_b1,
    extract_eligible_by_date,
    generate_walk_forward_splits,
    load_universe_csvs,
    run_full_pipeline,
    run_single_split,
)
from rotation_walk_forward_adapter import RotationWalkForwardSplit


# ---------------------------------------------------------------------------
# Toy data helpers
# ---------------------------------------------------------------------------

_TOY_TICKERS = ["AAA", "BBB", "CCC"]

# Enough business days for RS_252 warmup (256) + 2 years train + 1 year test
_TOY_DATES = list(pd.bdate_range("2018-01-01", "2022-12-31"))  # ~1305 days
_TEST_WINDOW_DATES = list(pd.bdate_range("2022-01-03", "2022-12-30"))  # 1 test year


def _toy_ohlcv_df(dates, base_price=100.0, volume=5_000_000):
    """Create a minimal OHLCV DataFrame with monotonically trending price."""
    n = len(dates)
    # Slowly rising price (1 bps/day) to keep ATR% below 8% and trend above EMA200
    prices = base_price * (1.001 ** np.arange(n))
    # Small OHLC spread so ATR% stays low
    opens = prices * 0.999
    highs = prices * 1.001
    lows = prices * 0.998
    volumes = np.full(n, float(volume))
    return pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": prices,
            "volume": volumes,
            "adjusted_close": prices,
        },
        index=pd.DatetimeIndex(dates),
    )


def _toy_universe_data(dates=None):
    if dates is None:
        dates = _TOY_DATES
    return {
        t: _toy_ohlcv_df(dates, base_price=100.0 + i * 10)
        for i, t in enumerate(_TOY_TICKERS)
    }


def _write_toy_csvs(tmp_dir: Path, dates=None, tickers=None):
    """Write toy OHLCV CSVs to tmp_dir. Returns the dict of DataFrames."""
    if dates is None:
        dates = _TOY_DATES
    if tickers is None:
        tickers = _TOY_TICKERS
    data = {}
    for i, t in enumerate(tickers):
        df = _toy_ohlcv_df(dates, base_price=100.0 + i * 10)
        df_out = df.copy()
        df_out.index.name = "timestamp"
        start_str = str(pd.Timestamp(dates[0]).date())
        end_str = str(pd.Timestamp(dates[-1]).date())
        path = tmp_dir / f"{t}_{start_str}_{end_str}.csv"
        df_out.to_csv(path)
        data[t] = df
    return data


def _toy_feature_matrix(dates, tickers, elig=True, crs=0.8, rp=0.9):
    """Build minimal feature matrix compatible with the backtester."""
    rows = []
    for d in dates:
        for t in tickers:
            rows.append(
                {
                    "date": pd.Timestamp(d),
                    "ticker": t,
                    "composite_rs": crs,
                    "rank_percentile": rp,
                    "trend_filter_ema200": elig,
                    "volatility_filter_atr_pct": elig,
                    "liquidity_filter_volume_avg_20": elig,
                    "is_rotation_eligible": elig,
                }
            )
    return pd.DataFrame(rows)


def _toy_split(split_id="WF-01", n_test_days=20):
    test_dates = list(pd.bdate_range("2022-01-03", periods=n_test_days))
    return RotationWalkForwardSplit(
        split_id=split_id,
        train_start=pd.Timestamp("2019-01-01"),
        train_end=pd.Timestamp("2021-12-31"),
        test_start=test_dates[0],
        test_end=test_dates[-1],
    )


# ---------------------------------------------------------------------------
# Tests 1–3: constants
# ---------------------------------------------------------------------------


def test_frozen_universe_has_15_tickers():
    assert len(FROZEN_UNIVERSE) == 15


def test_frozen_universe_contains_required_tickers():
    required = {"AAPL", "MSFT", "NVDA", "AMD", "META", "AMZN", "GOOGL",
                "TSLA", "NFLX", "AVGO", "CRM", "ORCL", "INTC", "CSCO", "IBM"}
    assert set(FROZEN_UNIVERSE) == required


def test_split_spec_constants():
    assert SPLIT_SPEC_VERSION == "RSR_V1_SPLIT_SPEC_v1"
    assert TRAIN_YEARS == 3
    assert TEST_YEARS == 1
    assert STEP_YEARS == 1
    assert WINDOW_START == "2015-01-01"
    assert WINDOW_END == "2024-12-31"


# ---------------------------------------------------------------------------
# Tests 4–10: generate_walk_forward_splits
# ---------------------------------------------------------------------------


def test_generate_splits_returns_list():
    splits = generate_walk_forward_splits(
        window_start="2015-01-01", window_end="2024-12-31",
        train_years=3, test_years=1, step_years=1,
    )
    assert isinstance(splits, list)
    assert len(splits) > 0


def test_generate_splits_produces_7_splits_for_frozen_spec():
    splits = generate_walk_forward_splits()
    # 10-year window, train=3, test=1, step=1 => 7 splits (WF-01 to WF-07)
    assert len(splits) == 7


def test_generate_splits_ids():
    splits = generate_walk_forward_splits()
    ids = [s.split_id for s in splits]
    assert ids == [f"WF-{i:02d}" for i in range(1, 8)]


def test_generate_splits_no_train_test_overlap():
    splits = generate_walk_forward_splits()
    for s in splits:
        assert pd.Timestamp(s.train_end) < pd.Timestamp(s.test_start), (
            f"{s.split_id}: train_end >= test_start"
        )


def test_generate_splits_windows_are_contiguous():
    splits = generate_walk_forward_splits()
    for s in splits:
        # test_start should be exactly 1 day after train_end
        train_end = pd.Timestamp(s.train_end)
        test_start = pd.Timestamp(s.test_start)
        assert (test_start - train_end).days == 1, (
            f"{s.split_id}: gap between train_end and test_start is not 1 day"
        )


def test_generate_splits_first_split_dates():
    splits = generate_walk_forward_splits()
    wf01 = splits[0]
    assert pd.Timestamp(wf01.train_start) == pd.Timestamp("2015-01-01")
    assert pd.Timestamp(wf01.train_end) == pd.Timestamp("2017-12-31")
    assert pd.Timestamp(wf01.test_start) == pd.Timestamp("2018-01-01")
    assert pd.Timestamp(wf01.test_end) == pd.Timestamp("2018-12-31")


def test_generate_splits_raises_on_impossible_window():
    with pytest.raises(ValueError, match="No valid splits"):
        generate_walk_forward_splits(
            window_start="2015-01-01", window_end="2016-12-31",
            train_years=3, test_years=1, step_years=1,
        )


# ---------------------------------------------------------------------------
# Tests 11–14: load_universe_csvs
# ---------------------------------------------------------------------------


def test_load_universe_csvs_returns_dict_with_dataframes():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_toy_csvs(tmp_path)
        result = load_universe_csvs(tmp_path, _TOY_TICKERS)
    assert isinstance(result, dict)
    assert set(result.keys()) == set(_TOY_TICKERS)
    for t, df in result.items():
        assert isinstance(df, pd.DataFrame), f"{t} not a DataFrame"
        assert isinstance(df.index, pd.DatetimeIndex), f"{t} index not DatetimeIndex"


def test_load_universe_csvs_has_close_column():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_toy_csvs(tmp_path)
        result = load_universe_csvs(tmp_path, _TOY_TICKERS)
    for t, df in result.items():
        assert "close" in df.columns, f"{t} missing 'close'"


def test_load_universe_csvs_raises_on_missing_ticker():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_toy_csvs(tmp_path)
        with pytest.raises(FileNotFoundError, match="ZZZ"):
            load_universe_csvs(tmp_path, ["ZZZ"])


def test_load_universe_csvs_date_filter():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_toy_csvs(tmp_path)
        result = load_universe_csvs(
            tmp_path, _TOY_TICKERS,
            start_date="2021-01-01", end_date="2021-12-31",
        )
    for t, df in result.items():
        assert df.index.min() >= pd.Timestamp("2021-01-01"), f"{t} has rows before filter"
        assert df.index.max() <= pd.Timestamp("2021-12-31"), f"{t} has rows after filter"


# ---------------------------------------------------------------------------
# Tests 15–17: build_returns_by_ticker
# ---------------------------------------------------------------------------


def test_build_returns_by_ticker_returns_dict_of_series():
    data = _toy_universe_data()
    result = build_returns_by_ticker(data)
    assert isinstance(result, dict)
    for t in _TOY_TICKERS:
        assert t in result
        assert isinstance(result[t], pd.Series)


def test_build_returns_by_ticker_first_value_is_zero():
    data = _toy_universe_data()
    result = build_returns_by_ticker(data)
    for t in _TOY_TICKERS:
        assert result[t].iloc[0] == 0.0, f"{t} first return not 0"


def test_build_returns_by_ticker_values_finite():
    data = _toy_universe_data()
    result = build_returns_by_ticker(data)
    for t in _TOY_TICKERS:
        assert np.isfinite(result[t].values).all(), f"{t} has non-finite returns"


# ---------------------------------------------------------------------------
# Tests 18–20: extract_eligible_by_date
# ---------------------------------------------------------------------------


def _small_feature_matrix():
    dates = list(pd.bdate_range("2022-01-03", periods=5))
    rows = []
    for d in dates:
        rows.append({"date": pd.Timestamp(d), "ticker": "AAA", "is_rotation_eligible": True})
        rows.append({"date": pd.Timestamp(d), "ticker": "BBB", "is_rotation_eligible": False})
    return pd.DataFrame(rows), dates


def test_extract_eligible_by_date_returns_dict():
    fm, dates = _small_feature_matrix()
    result = extract_eligible_by_date(fm, [pd.Timestamp(d) for d in dates])
    assert isinstance(result, dict)


def test_extract_eligible_by_date_filters_correctly():
    fm, dates = _small_feature_matrix()
    rd = pd.Timestamp(dates[0])
    result = extract_eligible_by_date(fm, [rd])
    assert result[rd] == ["AAA"]


def test_extract_eligible_by_date_empty_when_none_eligible():
    fm = pd.DataFrame([
        {"date": pd.Timestamp("2022-01-03"), "ticker": "AAA", "is_rotation_eligible": False}
    ])
    result = extract_eligible_by_date(fm, [pd.Timestamp("2022-01-03")])
    assert result[pd.Timestamp("2022-01-03")] == []


# ---------------------------------------------------------------------------
# Tests 21–23: compute_aggregate_b1
# ---------------------------------------------------------------------------


def test_compute_aggregate_b1_returns_b1_result():
    from rotation_benchmark_b1 import B1BuyHoldBenchmarkResult
    data = _toy_universe_data()
    test_dates = _TEST_WINDOW_DATES
    result = compute_aggregate_b1(
        data,
        test_start=test_dates[0],
        test_end=test_dates[-1],
        universe=_TOY_TICKERS,
    )
    assert isinstance(result, B1BuyHoldBenchmarkResult)


def test_compute_aggregate_b1_equity_curve_non_empty():
    data = _toy_universe_data()
    test_dates = _TEST_WINDOW_DATES
    result = compute_aggregate_b1(
        data,
        test_start=test_dates[0],
        test_end=test_dates[-1],
        universe=_TOY_TICKERS,
    )
    assert len(result.equity_curve) > 0


def test_compute_aggregate_b1_raises_when_no_data_in_window():
    data = _toy_universe_data()
    with pytest.raises(ValueError):
        compute_aggregate_b1(
            data,
            test_start="2030-01-01",
            test_end="2030-12-31",
            universe=_TOY_TICKERS,
        )


# ---------------------------------------------------------------------------
# Tests 24–30: run_single_split (toy universe)
# ---------------------------------------------------------------------------


def _make_toy_split_inputs():
    """Build all inputs needed for run_single_split with toy data."""
    test_dates = list(pd.bdate_range("2022-01-03", periods=20))
    all_dates = _TOY_DATES  # warmup + train + test

    split = RotationWalkForwardSplit(
        split_id="WF-TOY",
        train_start=pd.Timestamp("2019-01-01"),
        train_end=pd.Timestamp("2021-12-31"),
        test_start=test_dates[0],
        test_end=test_dates[-1],
    )

    universe_data = _toy_universe_data(all_dates)
    feature_matrix = _toy_feature_matrix(all_dates, _TOY_TICKERS)
    returns = build_returns_by_ticker(universe_data)

    return split, universe_data, feature_matrix, returns


def test_run_single_split_returns_orchestrator_split_result():
    split, ud, fm, ret = _make_toy_split_inputs()
    result = run_single_split(
        split=split,
        universe_data=ud,
        feature_matrix=fm,
        returns_by_ticker=ret,
        universe=_TOY_TICKERS,
    )
    assert isinstance(result, OrchestratorSplitResult)


def test_run_single_split_split_id_preserved():
    split, ud, fm, ret = _make_toy_split_inputs()
    result = run_single_split(
        split=split, universe_data=ud, feature_matrix=fm,
        returns_by_ticker=ret, universe=_TOY_TICKERS,
    )
    assert result.split.split_id == "WF-TOY"


def test_run_single_split_diagnostics_has_no_live_go():
    split, ud, fm, ret = _make_toy_split_inputs()
    result = run_single_split(
        split=split, universe_data=ud, feature_matrix=fm,
        returns_by_ticker=ret, universe=_TOY_TICKERS,
    )
    diag = result.diagnostics
    assert diag.get("live_go_emitted") is False
    assert diag.get("research_go_emitted") is False


def test_run_single_split_research_authorized_false():
    split, ud, fm, ret = _make_toy_split_inputs()
    result = run_single_split(
        split=split, universe_data=ud, feature_matrix=fm,
        returns_by_ticker=ret, universe=_TOY_TICKERS,
    )
    assert result.diagnostics.get("research_authorized") is False


def test_run_single_split_b1_result_not_none():
    from rotation_benchmark_b1 import B1BuyHoldBenchmarkResult
    split, ud, fm, ret = _make_toy_split_inputs()
    result = run_single_split(
        split=split, universe_data=ud, feature_matrix=fm,
        returns_by_ticker=ret, universe=_TOY_TICKERS,
    )
    assert isinstance(result.b1_result, B1BuyHoldBenchmarkResult)


def test_run_single_split_b2_result_not_none():
    from rotation_benchmark_b2 import EqualWeightBenchmarkResult
    split, ud, fm, ret = _make_toy_split_inputs()
    result = run_single_split(
        split=split, universe_data=ud, feature_matrix=fm,
        returns_by_ticker=ret, universe=_TOY_TICKERS,
    )
    assert isinstance(result.b2_result, EqualWeightBenchmarkResult)


def test_run_single_split_p95_result_not_none():
    from rotation_random_selection_comparator import RandomSelectionComparatorResult
    split, ud, fm, ret = _make_toy_split_inputs()
    result = run_single_split(
        split=split, universe_data=ud, feature_matrix=fm,
        returns_by_ticker=ret, universe=_TOY_TICKERS,
    )
    assert isinstance(result.p95_result, RandomSelectionComparatorResult)


# ---------------------------------------------------------------------------
# Tests 31–36: run_full_pipeline (toy data, temp dir)
# ---------------------------------------------------------------------------


def _toy_pipeline_config(tmp_dir: Path) -> OrchestratorConfig:
    """Config for a small 3-ticker, 2+1 year walk-forward on toy data."""
    return OrchestratorConfig(
        data_dir=str(tmp_dir),
        output_dir=str(tmp_dir / "out"),
        universe=_TOY_TICKERS,
        window_start="2018-01-01",
        window_end="2022-12-31",
        train_years=2,
        test_years=1,
        step_years=1,
        n_random_simulations=50,
        random_seed=42,
        report_filename="test_report.csv",
    )


def test_run_full_pipeline_returns_orchestrator_run_result():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_toy_csvs(tmp_path)
        cfg = _toy_pipeline_config(tmp_path)
        result = run_full_pipeline(cfg)
    assert isinstance(result, OrchestratorRunResult)


def test_run_full_pipeline_produces_2_splits():
    # window 2018-2022 (5 years), train=2, test=1, step=1 => 3 splits
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_toy_csvs(tmp_path)
        cfg = _toy_pipeline_config(tmp_path)
        result = run_full_pipeline(cfg)
    # 5-year window, train=2, test=1, step=1 => 3 splits
    assert len(result.split_results) == 3


def test_run_full_pipeline_all_research_authorized_false():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_toy_csvs(tmp_path)
        cfg = _toy_pipeline_config(tmp_path)
        result = run_full_pipeline(cfg)
    assert result.diagnostics.get("research_authorized") is False
    for sr in result.split_results:
        assert sr.diagnostics.get("research_authorized") is False


def test_run_full_pipeline_no_live_go_in_diagnostics():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_toy_csvs(tmp_path)
        cfg = _toy_pipeline_config(tmp_path)
        result = run_full_pipeline(cfg)
    assert result.diagnostics.get("live_go_emitted") is False
    assert result.diagnostics.get("research_go_emitted") is False


def test_run_full_pipeline_writes_csv_report():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_toy_csvs(tmp_path)
        cfg = _toy_pipeline_config(tmp_path)
        result = run_full_pipeline(cfg)
        assert result.report_path is not None
        assert Path(result.report_path).exists()


def test_run_full_pipeline_csv_report_has_rows():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_toy_csvs(tmp_path)
        cfg = _toy_pipeline_config(tmp_path)
        result = run_full_pipeline(cfg)
        with open(result.report_path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) >= 1


# ---------------------------------------------------------------------------
# Tests 37–39: source-level safety checks
# ---------------------------------------------------------------------------

_ORCHESTRATOR_SRC = Path(__file__).parent.parent / "rotation_research_orchestrator.py"


def test_source_contains_no_live_go_token():
    src = _ORCHESTRATOR_SRC.read_text()
    assert "LIVE-GO" not in src, "LIVE-GO token found in orchestrator source"


def test_source_contains_no_research_go_token():
    src = _ORCHESTRATOR_SRC.read_text()
    assert "RESEARCH-GO" not in src, "RESEARCH-GO token found in orchestrator source"


def test_orchestrator_config_research_authorized_not_in_defaults():
    # research_authorized should never appear as a True default in the module
    src = _ORCHESTRATOR_SRC.read_text()
    assert "research_authorized=True" not in src
