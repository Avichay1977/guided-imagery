"""
NaN / dirty-data validation tests for DataLoader.

One test per cleaning rule.  Every test runs the full load_from_csv pipeline
using a minimal tmp_path CSV — nothing is mocked or monkey-patched.

pandas behavior this relies on:
  pd.to_datetime(errors="coerce")   → invalid dates become NaT → dropped
  pd.to_numeric(errors="coerce")    → invalid numeric parsing becomes NaN
  pd.isna                           → detects NaN / None / NaT
"""

import pandas as pd
import pytest

from data_loader import DataLoader


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _csv(tmp_path, content: str) -> object:
    p = tmp_path / "test.csv"
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_invalid_timestamp_is_dropped(tmp_path):
    """
    pd.to_datetime(errors="coerce") turns unparseable strings into NaT.
    Rows with NaT index are removed; valid rows are kept.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,101,99,100,1000\n"
        "NOT_A_DATE,100,101,99,100,1000\n"
        "2020-01-03,100,101,99,100,1000\n"
    ))
    loader = DataLoader()
    df = loader.load_from_csv(p)
    report = loader.get_last_report()

    assert report["invalid_timestamps_removed"] == 1
    assert len(df) == 2
    assert report["rows_after_cleaning"] == 2


def test_duplicate_timestamp_keeps_last_row(tmp_path):
    """
    When two rows share a timestamp, only the last one is kept.
    duplicate_timestamps_removed == 1.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,101,99,100,1000\n"
        "2020-01-02,200,201,199,200,2000\n"   # duplicate — last → survives
        "2020-01-03,100,101,99,100,1000\n"
    ))
    loader = DataLoader()
    df = loader.load_from_csv(p)
    report = loader.get_last_report()

    assert report["duplicate_timestamps_removed"] == 1
    assert len(df) == 2
    assert df.at[pd.Timestamp("2020-01-02"), "close"] == 200.0


def test_invalid_numeric_ohlc_becomes_nan_and_row_is_dropped(tmp_path):
    """
    pd.to_numeric(errors="coerce") converts non-numeric strings (e.g. "abc")
    to NaN.  Rows with NaN in any OHLC column are then dropped.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,101,99,100,1000\n"
        "2020-01-03,100,101,abc,100,1000\n"   # "abc" in low → NaN → row dropped
        "2020-01-06,100,101,99,100,1000\n"
    ))
    loader = DataLoader()
    df = loader.load_from_csv(p)
    report = loader.get_last_report()

    assert report["missing_ohlc_rows_removed"] == 1
    assert len(df) == 2


def test_missing_ohlc_row_is_dropped(tmp_path):
    """
    A row with an empty (blank) OHLC field is parsed as NaN and dropped.
    No forward-fill or backward-fill is applied.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,101,99,100,1000\n"
        "2020-01-03,,101,99,100,1000\n"        # open missing
        "2020-01-06,100,101,99,100,1000\n"
    ))
    loader = DataLoader()
    df = loader.load_from_csv(p)
    report = loader.get_last_report()

    assert report["missing_ohlc_rows_removed"] == 1
    assert len(df) == 2


def test_missing_volume_becomes_zero(tmp_path):
    """
    Missing volume is filled with 0.0 so the OHLC row is preserved.
    The missing_volume_filled counter increments.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,101,99,100,\n"         # volume blank
        "2020-01-03,100,101,99,100,2000\n"
    ))
    loader = DataLoader()
    df = loader.load_from_csv(p)
    report = loader.get_last_report()

    assert report["missing_volume_filled"] == 1
    assert len(df) == 2
    assert df.iloc[0]["volume"] == 0.0
    assert df.iloc[1]["volume"] == 2000.0


def test_zero_or_negative_ohlc_row_is_dropped(tmp_path):
    """
    Rows where any OHLC value is <= 0 are removed.
    negative_or_zero_price_rows_removed counts both zero and negative cases.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,101,99,100,1000\n"
        "2020-01-03,0,101,99,100,1000\n"       # zero open
        "2020-01-06,-5,101,99,100,1000\n"      # negative open
        "2020-01-07,100,101,99,100,1000\n"
    ))
    loader = DataLoader()
    df = loader.load_from_csv(p)
    report = loader.get_last_report()

    assert report["negative_or_zero_price_rows_removed"] == 2
    assert len(df) == 2


def test_invalid_ohlc_geometry_is_corrected(tmp_path):
    """
    A bar where high < open is geometrically invalid.
    Correction: high = max(O,H,L,C), low = min(O,H,L,C).
    The row is NOT dropped; invalid_geometry_rows_corrected increments.
    get_last_invalid_geometry_rows() returns the original bad values.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,90,99,100,1000\n"      # high(90) < open(100) — invalid
        "2020-01-03,100,101,99,100,1000\n"
    ))
    loader = DataLoader(correct_invalid_geometry=True)
    df = loader.load_from_csv(p)
    report = loader.get_last_report()

    assert report["invalid_geometry_rows_corrected"] == 1
    assert len(df) == 2

    row = df.iloc[0]
    assert row["high"] >= row["open"]
    assert row["high"] >= row["close"]
    assert row["low"] <= row["open"]
    assert row["low"] <= row["close"]
    assert row["high"] >= row["low"]

    bad = loader.get_last_invalid_geometry_rows()
    assert bad is not None
    assert len(bad) == 1
    assert bad.iloc[0]["high"] == 90.0    # original value before correction


def test_adjusted_ohlc_not_applied_by_default(tmp_path):
    """
    use_adjusted_close defaults to False.
    When omitted, prices are not adjusted and adjusted_ohlc_applied is False.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,adjusted_close,volume\n"
        "2020-01-02,100,101,99,100,80,1000\n"
        "2020-01-03,100,101,99,100,80,1000\n"
    ))
    loader = DataLoader()   # use_adjusted_close=False by default
    df = loader.load_from_csv(p)
    report = loader.get_last_report()

    assert df.iloc[0]["close"] == pytest.approx(100.0)
    assert report["adjusted_ohlc_applied"] is False


def test_adjusted_ohlc_applied_only_when_explicitly_enabled(tmp_path):
    """
    When use_adjusted_close=True, OHLC is scaled by adjusted_close / close.
    close becomes adjusted_close; other cols scale proportionally.
    adjusted_ohlc_applied is True in the report.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,adjusted_close,volume\n"
        "2020-01-02,100,101,99,100,90,1000\n"   # ratio = 0.9
        "2020-01-03,100,101,99,100,90,1000\n"
    ))
    loader = DataLoader(use_adjusted_close=True)
    df = loader.load_from_csv(p)
    report = loader.get_last_report()

    assert df.iloc[0]["close"] == pytest.approx(90.0)   # 100 * 0.9
    assert df.iloc[0]["open"] == pytest.approx(90.0)    # 100 * 0.9
    assert report["adjusted_ohlc_applied"] is True


def test_no_ohlc_ffill_bfill(tmp_path):
    """
    Explicit proof that missing OHLC is dropped, not filled.

    Row layout:  close=[100, NaN, 200]
    If ffill: surviving closes would be [100, 100, 200] — 3 rows.
    If bfill: surviving closes would be [100, 200, 200] — 3 rows.
    Correct:  row with NaN is dropped → closes are exactly {100, 200} — 2 rows.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,101,99,100,1000\n"
        "2020-01-03,100,101,99,,1000\n"      # close missing
        "2020-01-06,200,201,199,200,1000\n"
    ))
    loader = DataLoader()
    df = loader.load_from_csv(p)

    assert len(df) == 2
    closes = sorted(df["close"].tolist())
    assert closes == [100.0, 200.0]


def test_use_adjusted_close_true_without_column_raises(tmp_path):
    """
    When use_adjusted_close=True but the CSV has no adjusted_close column,
    DataLoader must raise ValueError — not silently skip the adjustment.
    This prevents silent under-adjustment going undetected.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,101,99,100,1000\n"
        "2020-01-03,100,101,99,100,1000\n"
    ))
    loader = DataLoader(use_adjusted_close=True)

    with pytest.raises(ValueError, match="adjusted_close"):
        loader.load_from_csv(p)
