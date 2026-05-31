"""
Unit tests for rotation_data_audit.

Deterministic toy CSVs only. No network. No real market data fetch.
No strategy_lab_runner.
"""

import inspect
import json

import numpy as np
import pandas as pd
import pytest

import rotation_data_audit as _audit_mod
from rotation_data_audit import (
    RotationDataAuditConfig,
    RotationTickerDataAudit,
    RotationUniverseDataAuditResult,
    audit_frozen_universe_data,
    audit_ticker_csv,
    find_local_ticker_csvs,
    write_data_audit_report,
)


_FROZEN_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMD", "META",
    "AMZN", "GOOGL", "TSLA", "NFLX", "AVGO",
    "CRM", "ORCL", "INTC", "CSCO", "IBM",
]


# ---------------------------------------------------------------------------
# CSV factory
# ---------------------------------------------------------------------------

def _good_csv_df(start="2015-01-01", end="2024-12-31", with_adjusted=True):
    dates = pd.bdate_range(start, end)
    n = len(dates)
    prices = np.linspace(50.0, 200.0, n)
    df = pd.DataFrame({
        "timestamp": dates.strftime("%Y-%m-%d"),
        "open": prices,
        "high": prices + 0.5,
        "low": prices - 0.5,
        "close": prices + 0.1,
        "volume": np.arange(1_000_000, 1_000_000 + n),
    })
    if with_adjusted:
        df["adjusted_close"] = prices + 0.05
    return df


def _write_csv(tmp_path, ticker, df, suffix="_2015-01-01_2024-12-31.csv"):
    path = tmp_path / f"{ticker}{suffix}"
    df.to_csv(path, index=False)
    return path


def _all_good_universe(tmp_path):
    paths = {}
    for t in _FROZEN_UNIVERSE:
        paths[t] = _write_csv(tmp_path, t, _good_csv_df())
    return paths


# ---------------------------------------------------------------------------
# Tests 1–5: shape + forbidden imports
# ---------------------------------------------------------------------------

def test_config_defaults_match_spec():
    c = RotationDataAuditConfig()
    assert c.start_date == "2015-01-01"
    assert c.end_date == "2024-12-31"
    assert c.required_columns == ("timestamp", "open", "high", "low", "close", "volume")
    assert c.allow_adjusted_close is True
    assert c.require_all_tickers is True
    assert c.data_source_label == "LOCAL_CSV_AUDIT_ONLY"
    assert c.auto_adjust_required is False


def test_ticker_audit_dataclass_has_required_fields():
    t = RotationTickerDataAudit(ticker="X", found=False, path=None)
    for f in (
        "ticker", "found", "path", "row_count", "start_date", "end_date",
        "missing_required_columns", "has_adjusted_close",
        "has_nan_ohlc", "has_inf_ohlc", "has_non_positive_ohlc",
        "has_negative_volume", "coverage_ok", "valid_for_research",
        "failure_reasons",
    ):
        assert hasattr(t, f), f"missing field {f!r}"


def test_universe_audit_dataclass_has_required_fields():
    r = RotationUniverseDataAuditResult(
        universe=[], required_start_date="", required_end_date="",
        ticker_results={},
    )
    for f in (
        "universe", "required_start_date", "required_end_date",
        "ticker_results", "missing_tickers", "valid_tickers",
        "invalid_tickers", "all_required_tickers_present",
        "all_required_tickers_valid", "research_ready", "diagnostics",
    ):
        assert hasattr(r, f), f"missing field {f!r}"


def test_module_does_not_import_yfinance():
    src = inspect.getsource(_audit_mod)
    assert "yfinance" not in src
    assert "import yfinance" not in src
    assert "from yfinance" not in src


def test_module_does_not_import_strategy_lab_runner():
    src = inspect.getsource(_audit_mod)
    assert "strategy_lab_runner" not in src


# ---------------------------------------------------------------------------
# Tests 6–7: file discovery
# ---------------------------------------------------------------------------

def test_find_local_ticker_csvs_finds_ticker_files_deterministically(tmp_path):
    _write_csv(tmp_path, "AAPL", _good_csv_df())
    _write_csv(tmp_path, "AAPL", _good_csv_df(), suffix="_alt.csv")
    found = find_local_ticker_csvs([tmp_path], ["AAPL"])
    assert "AAPL" in found
    # Deterministic: same call returns same path
    found2 = find_local_ticker_csvs([tmp_path], ["AAPL"])
    assert found == found2


def test_find_local_ticker_csvs_is_case_insensitive(tmp_path):
    # File with lowercase name; ticker stays as canonical uppercase
    path = tmp_path / "aapl_2015-01-01_2024-12-31.csv"
    _good_csv_df().to_csv(path, index=False)
    found = find_local_ticker_csvs([tmp_path], ["AAPL"])
    assert "AAPL" in found


# ---------------------------------------------------------------------------
# Tests 8–14: per-ticker validation
# ---------------------------------------------------------------------------

def test_audit_ticker_csv_rejects_missing_file(tmp_path):
    audit = audit_ticker_csv("AAPL", tmp_path / "nope.csv")
    assert audit.found is False
    assert any("FILE_NOT_FOUND" in r for r in audit.failure_reasons)
    assert audit.valid_for_research is False


def test_audit_ticker_csv_rejects_missing_required_columns(tmp_path):
    df = _good_csv_df()
    df = df.drop(columns=["volume"])
    path = _write_csv(tmp_path, "AAPL", df)
    audit = audit_ticker_csv("AAPL", path)
    assert "volume" in audit.missing_required_columns
    assert audit.valid_for_research is False


def test_audit_ticker_csv_rejects_invalid_timestamp(tmp_path):
    df = _good_csv_df()
    df.loc[3, "timestamp"] = "not-a-date"
    path = _write_csv(tmp_path, "AAPL", df)
    audit = audit_ticker_csv("AAPL", path)
    assert any("TIMESTAMP" in r for r in audit.failure_reasons)
    assert audit.valid_for_research is False


def test_audit_ticker_csv_rejects_nan_ohlc(tmp_path):
    df = _good_csv_df()
    df.loc[5, "close"] = float("nan")
    path = _write_csv(tmp_path, "AAPL", df)
    audit = audit_ticker_csv("AAPL", path)
    assert audit.has_nan_ohlc is True
    assert audit.valid_for_research is False


def test_audit_ticker_csv_rejects_inf_ohlc(tmp_path):
    df = _good_csv_df()
    df.loc[5, "high"] = float("inf")
    path = _write_csv(tmp_path, "AAPL", df)
    audit = audit_ticker_csv("AAPL", path)
    assert audit.has_inf_ohlc is True
    assert audit.valid_for_research is False


def test_audit_ticker_csv_rejects_non_positive_ohlc(tmp_path):
    df = _good_csv_df()
    df.loc[5, "low"] = -1.0
    path = _write_csv(tmp_path, "AAPL", df)
    audit = audit_ticker_csv("AAPL", path)
    assert audit.has_non_positive_ohlc is True
    assert audit.valid_for_research is False


def test_audit_ticker_csv_rejects_negative_volume(tmp_path):
    df = _good_csv_df()
    df.loc[5, "volume"] = -100
    path = _write_csv(tmp_path, "AAPL", df)
    audit = audit_ticker_csv("AAPL", path)
    assert audit.has_negative_volume is True
    assert audit.valid_for_research is False


# ---------------------------------------------------------------------------
# Tests 15–18: adjusted_close + coverage
# ---------------------------------------------------------------------------

def test_audit_ticker_csv_records_adjusted_close_presence(tmp_path):
    df_with = _good_csv_df(with_adjusted=True)
    path_with = _write_csv(tmp_path, "AAPL", df_with)
    audit_with = audit_ticker_csv("AAPL", path_with)
    assert audit_with.has_adjusted_close is True

    df_without = _good_csv_df(with_adjusted=False)
    path_without = _write_csv(tmp_path, "MSFT", df_without)
    audit_without = audit_ticker_csv("MSFT", path_without)
    assert audit_without.has_adjusted_close is False


def test_audit_ticker_csv_marks_coverage_ok_true_when_range_covered(tmp_path):
    path = _write_csv(tmp_path, "AAPL", _good_csv_df("2014-12-30", "2025-01-05"))
    audit = audit_ticker_csv("AAPL", path)
    assert audit.coverage_ok is True
    assert audit.valid_for_research is True


def test_audit_ticker_csv_marks_coverage_ok_false_when_start_missing(tmp_path):
    path = _write_csv(tmp_path, "AAPL", _good_csv_df("2018-01-02", "2024-12-31"))
    audit = audit_ticker_csv("AAPL", path)
    assert audit.coverage_ok is False
    assert any("COVERAGE_MISS_START" in r for r in audit.failure_reasons)


def test_audit_ticker_csv_marks_coverage_ok_false_when_end_missing(tmp_path):
    path = _write_csv(tmp_path, "AAPL", _good_csv_df("2015-01-01", "2022-06-30"))
    audit = audit_ticker_csv("AAPL", path)
    assert audit.coverage_ok is False
    assert any("COVERAGE_MISS_END" in r for r in audit.failure_reasons)


# ---------------------------------------------------------------------------
# Tests 19–21: no fill / no interpolate (NaN must be surfaced, not repaired)
# ---------------------------------------------------------------------------

def test_audit_ticker_csv_does_not_forward_fill(tmp_path):
    df = _good_csv_df()
    df.loc[10, "close"] = float("nan")
    path = _write_csv(tmp_path, "AAPL", df)
    audit = audit_ticker_csv("AAPL", path)
    # If forward-fill were happening, audit would not flag has_nan_ohlc.
    assert audit.has_nan_ohlc is True


def test_audit_ticker_csv_does_not_backfill(tmp_path):
    df = _good_csv_df()
    df.loc[0, "close"] = float("nan")
    path = _write_csv(tmp_path, "AAPL", df)
    audit = audit_ticker_csv("AAPL", path)
    assert audit.has_nan_ohlc is True


def test_audit_ticker_csv_does_not_interpolate(tmp_path):
    df = _good_csv_df()
    df.loc[20, "close"] = float("nan")
    df.loc[21, "close"] = float("nan")
    df.loc[22, "close"] = float("nan")
    path = _write_csv(tmp_path, "AAPL", df)
    audit = audit_ticker_csv("AAPL", path)
    assert audit.has_nan_ohlc is True


# ---------------------------------------------------------------------------
# Tests 22–24: universe-level audit
# ---------------------------------------------------------------------------

def test_audit_frozen_universe_data_reports_missing_tickers(tmp_path):
    # Only write 7 of 15 tickers
    partial = ["AAPL", "MSFT", "NVDA", "META", "AMZN", "GOOGL", "ORCL"]
    for t in partial:
        _write_csv(tmp_path, t, _good_csv_df())
    result = audit_frozen_universe_data([tmp_path], _FROZEN_UNIVERSE)
    expected_missing = set(_FROZEN_UNIVERSE) - set(partial)
    assert set(result.missing_tickers) == expected_missing
    assert result.all_required_tickers_present is False


def test_audit_frozen_universe_data_research_ready_false_when_missing(tmp_path):
    _write_csv(tmp_path, "AAPL", _good_csv_df())  # only one ticker
    result = audit_frozen_universe_data([tmp_path], _FROZEN_UNIVERSE)
    assert result.research_ready is False
    assert result.all_required_tickers_present is False


def test_audit_frozen_universe_data_research_ready_true_when_all_valid(tmp_path):
    _all_good_universe(tmp_path)
    result = audit_frozen_universe_data([tmp_path], _FROZEN_UNIVERSE)
    assert result.all_required_tickers_present is True
    assert result.all_required_tickers_valid is True
    assert result.research_ready is True
    assert set(result.valid_tickers) == set(_FROZEN_UNIVERSE)


# ---------------------------------------------------------------------------
# Tests 25–26: JSON report writer
# ---------------------------------------------------------------------------

def test_write_data_audit_report_writes_json(tmp_path):
    _write_csv(tmp_path, "AAPL", _good_csv_df())
    result = audit_frozen_universe_data([tmp_path], _FROZEN_UNIVERSE)
    out = write_data_audit_report(result, tmp_path / "reports" / "audit.json")
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "research_ready" in payload
    assert "missing_tickers" in payload
    assert "ticker_results" in payload


def test_write_data_audit_report_preserves_missing_tickers(tmp_path):
    _write_csv(tmp_path, "AAPL", _good_csv_df())
    _write_csv(tmp_path, "MSFT", _good_csv_df())
    result = audit_frozen_universe_data([tmp_path], _FROZEN_UNIVERSE)
    out = write_data_audit_report(result, tmp_path / "audit.json")
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert set(payload["missing_tickers"]) == set(_FROZEN_UNIVERSE) - {"AAPL", "MSFT"}
    assert payload["research_ready"] is False


# ---------------------------------------------------------------------------
# Tests 27–28: no live-go / no research-go in source
# ---------------------------------------------------------------------------

def test_data_audit_outputs_no_live_go():
    src = inspect.getsource(_audit_mod)
    assert "LIVE-GO" not in src


def test_data_audit_outputs_no_research_go():
    src = inspect.getsource(_audit_mod)
    assert "RESEARCH-GO" not in src
