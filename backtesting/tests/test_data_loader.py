"""
DataLoader NaN-hardening tests.

Each test exercises one specific cleaning rule.
All tests use tmp_path to write a minimal CSV and run the full
load_from_csv pipeline — nothing is mocked.

Rules verified:
  - invalid timestamps → dropped (pd.to_datetime errors="coerce")
  - invalid numeric OHLC → NaN → row dropped (no ffill/bfill)
  - missing volume → filled with 0.0 (volume signal weakened, price untouched)
  - duplicate timestamps → keep last
  - invalid geometry → corrected via max/min of open/high/low/close
  - non-positive prices → dropped
  - adjusted_close scaling → only when use_adjusted_close=True
"""

import pandas as pd
import pytest

from data_loader import DataLoader


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _csv(tmp_path, content: str, name: str = "test.csv"):
    p = tmp_path / name
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_loader_drops_invalid_timestamp(tmp_path):
    """
    Rows with unparseable timestamps become NaT (errors="coerce") and are dropped.
    Valid rows are preserved.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,101,99,100,1000\n"
        "not-a-date,100,101,99,100,1000\n"
        "2020-01-03,100,101,99,100,1000\n"
    ))
    loader = DataLoader()
    df = loader.load_from_csv(p)
    report = loader.get_last_report()

    assert report["invalid_timestamps_removed"] == 1
    assert len(df) == 2


def test_loader_drops_missing_ohlc(tmp_path):
    """
    A row with a missing (NaN) OHLC value is dropped — never forward-filled.
    This verifies there is no ffill/bfill on price columns.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,101,99,100,1000\n"
        "2020-01-03,,101,99,100,1000\n"    # open is missing
        "2020-01-06,105,106,104,105,1000\n"
    ))
    loader = DataLoader()
    df = loader.load_from_csv(p)
    report = loader.get_last_report()

    assert report["missing_ohlc_rows_removed"] == 1
    assert len(df) == 2

    # The middle row must be gone — not filled with either neighbour
    closes = set(df["close"].tolist())
    assert closes == {100.0, 105.0}, f"unexpected closes: {closes}"


def test_loader_fills_missing_volume_with_zero(tmp_path):
    """
    Missing volume is filled with 0.0 so the row is not discarded.
    Price data remains intact.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,101,99,100,\n"
        "2020-01-03,100,101,99,100,2000\n"
    ))
    loader = DataLoader()
    df = loader.load_from_csv(p)
    report = loader.get_last_report()

    assert report["missing_volume_filled"] == 1
    assert len(df) == 2
    assert df.iloc[0]["volume"] == 0.0
    assert df.iloc[1]["volume"] == 2000.0


def test_loader_duplicate_timestamp_keep_last(tmp_path):
    """
    When two rows share a timestamp, the last one in the file is kept.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,101,99,100,1000\n"
        "2020-01-02,200,201,199,200,2000\n"   # duplicate — this one survives
        "2020-01-03,100,101,99,100,1000\n"
    ))
    loader = DataLoader()
    df = loader.load_from_csv(p)
    report = loader.get_last_report()

    assert report["duplicate_timestamps_removed"] == 1
    assert len(df) == 2
    assert df.at[pd.Timestamp("2020-01-02"), "close"] == 200.0


def test_loader_invalid_geometry_corrected(tmp_path):
    """
    A bar where high < open (e.g. data entry error) is corrected:
    new high = max(O,H,L,C), new low = min(O,H,L,C).
    The row is NOT dropped.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,95,99,100,1000\n"    # high(95) < open(100) — invalid
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


def test_loader_invalid_geometry_dropped_when_correction_disabled(tmp_path):
    """
    With correct_invalid_geometry=False the bad row is dropped rather than fixed.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,95,99,100,1000\n"
        "2020-01-03,100,101,99,100,1000\n"
    ))
    loader = DataLoader(correct_invalid_geometry=False)
    df = loader.load_from_csv(p)
    report = loader.get_last_report()

    assert report["invalid_geometry_rows_corrected"] == 1
    assert len(df) == 1


def test_loader_non_positive_prices_dropped(tmp_path):
    """
    Rows with zero or negative OHLC values are removed.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,volume\n"
        "2020-01-02,100,101,99,100,1000\n"
        "2020-01-03,0,101,99,100,1000\n"      # zero open
        "2020-01-06,-1,101,99,100,1000\n"     # negative open
        "2020-01-07,100,101,99,100,1000\n"
    ))
    loader = DataLoader()
    df = loader.load_from_csv(p)
    report = loader.get_last_report()

    assert report["negative_or_zero_price_rows_removed"] == 2
    assert len(df) == 2


def test_adjusted_ohlc_applied_only_when_adjust_flag_true(tmp_path):
    """
    adjusted_close / close ratio = 0.9.
    use_adjusted_close=False  → prices unchanged (close stays 100.0)
    use_adjusted_close=True   → prices scaled   (close becomes 90.0)
    adjusted_ohlc_applied flag mirrors the setting.
    """
    p = _csv(tmp_path, (
        "timestamp,open,high,low,close,adjusted_close,volume\n"
        "2020-01-02,100,101,99,100,90,1000\n"
        "2020-01-03,100,101,99,100,90,1000\n"
    ))

    loader_off = DataLoader(use_adjusted_close=False)
    df_off = loader_off.load_from_csv(p)
    assert df_off.iloc[0]["close"] == pytest.approx(100.0)
    assert loader_off.get_last_report()["adjusted_ohlc_applied"] is False

    loader_on = DataLoader(use_adjusted_close=True)
    df_on = loader_on.load_from_csv(p)
    assert df_on.iloc[0]["close"] == pytest.approx(90.0)
    assert loader_on.get_last_report()["adjusted_ohlc_applied"] is True
