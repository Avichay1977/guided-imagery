"""
Contract tests for RESEARCH_DATA_ACQUISITION_PLAN_RELATIVE_STRENGTH_ROTATION_V1.md.

These tests treat the markdown plan as a frozen contract. They check that
the canonical clauses are present and verbatim. They do not exercise data
acquisition or fetch any market data.
"""

from pathlib import Path

import pytest


_PLAN_PATH = (
    Path(__file__).resolve().parent.parent
    / "RESEARCH_DATA_ACQUISITION_PLAN_RELATIVE_STRENGTH_ROTATION_V1.md"
)

_FROZEN_UNIVERSE_LIST = (
    "AAPL, MSFT, NVDA, AMD, META, AMZN, GOOGL, TSLA, NFLX, AVGO, "
    "CRM, ORCL, INTC, CSCO, IBM"
)

_MISSING_TICKERS = ("AMD", "TSLA", "NFLX", "AVGO", "CRM", "INTC", "CSCO", "IBM")


@pytest.fixture(scope="module")
def plan_text() -> str:
    assert _PLAN_PATH.exists(), f"plan file not found: {_PLAN_PATH}"
    return _PLAN_PATH.read_text(encoding="utf-8")


def test_file_exists():
    assert _PLAN_PATH.exists(), f"plan file missing at {_PLAN_PATH}"


def test_declares_plan_only(plan_text):
    assert "PLAN ONLY" in plan_text


def test_says_no_market_data_fetched(plan_text):
    lower = plan_text.lower()
    assert "no market data is fetched" in lower or "no market data fetched" in lower


def test_says_no_research_run_authorized(plan_text):
    lower = plan_text.lower()
    assert "no research run is authorized" in lower or "does not authorize a research run" in lower


def test_contains_frozen_15_ticker_universe(plan_text):
    assert _FROZEN_UNIVERSE_LIST in plan_text


def test_contains_date_range_2015_to_2024(plan_text):
    assert "2015-01-01" in plan_text
    assert "2024-12-31" in plan_text


def test_contains_required_ohlcv_columns(plan_text):
    for col in ("timestamp", "open", "high", "low", "close", "volume"):
        assert col in plan_text, f"missing required column reference: {col!r}"


def test_says_auto_adjust_false(plan_text):
    assert "auto_adjust=False" in plan_text


def test_forbids_fill_and_interpolation(plan_text):
    lower = plan_text.lower()
    assert "no forward-fill" in lower
    assert "no back-fill" in lower
    assert "no interpolation" in lower


def test_forbids_synthetic_data_as_research_evidence(plan_text):
    lower = plan_text.lower()
    assert "synthetic" in lower
    assert "research evidence" in lower


def test_lists_missing_8_tickers(plan_text):
    for t in _MISSING_TICKERS:
        assert t in plan_text, f"missing ticker reference: {t!r}"


def test_says_acquisition_execution_requires_separate_gate(plan_text):
    lower = plan_text.lower()
    assert "separate gate" in lower
    assert "acquisition execution" in lower or "acquisition" in lower


def test_says_data_provenance_must_be_recorded(plan_text):
    assert "provenance" in plan_text.lower()


def test_acquisition_plan_mentions_first_trading_day_on_or_after(plan_text):
    lower = plan_text.lower()
    assert "first available trading day on or after" in lower or \
           "first trading day on or after" in lower
