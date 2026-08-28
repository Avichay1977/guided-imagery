"""
Contract tests for RESEARCH_SPLIT_SPEC_RELATIVE_STRENGTH_ROTATION_V1.md.

These tests treat the markdown spec as a frozen contract. They check that
the canonical clauses are present and verbatim. They do not exercise any
research run.
"""

from pathlib import Path

import pytest


_SPEC_PATH = (
    Path(__file__).resolve().parent.parent
    / "RESEARCH_SPLIT_SPEC_RELATIVE_STRENGTH_ROTATION_V1.md"
)

_FROZEN_UNIVERSE_LIST = (
    "AAPL, MSFT, NVDA, AMD, META, AMZN, GOOGL, TSLA, NFLX, AVGO, "
    "CRM, ORCL, INTC, CSCO, IBM"
)


@pytest.fixture(scope="module")
def spec_text() -> str:
    assert _SPEC_PATH.exists(), f"spec file not found: {_SPEC_PATH}"
    return _SPEC_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Contract tests (12 required clauses)
# ---------------------------------------------------------------------------

def test_file_exists():
    assert _SPEC_PATH.exists(), f"spec file missing at {_SPEC_PATH}"


def test_declares_specification_only(spec_text):
    assert "SPECIFICATION ONLY" in spec_text


def test_contains_frozen_15_ticker_universe(spec_text):
    assert _FROZEN_UNIVERSE_LIST in spec_text


def test_contains_date_range_2015_to_2024(spec_text):
    assert "2015-01-01" in spec_text
    assert "2024-12-31" in spec_text


def test_contains_train_years_3(spec_text):
    assert "train_years = 3" in spec_text or "train_years=3" in spec_text


def test_contains_test_years_1(spec_text):
    assert "test_years = 1" in spec_text or "test_years=1" in spec_text


def test_contains_step_years_1(spec_text):
    assert "step_years = 1" in spec_text or "step_years=1" in spec_text


def test_says_no_optimization(spec_text):
    lower = spec_text.lower()
    assert "no parameter optimization" in lower or "no optimization" in lower


def test_says_no_research_authorization_by_itself(spec_text):
    lower = spec_text.lower()
    assert (
        "does not authorize a research run" in lower
        or "does not authorize research" in lower
    )


def test_says_changing_splits_requires_new_rdr(spec_text):
    lower = spec_text.lower()
    assert "new rdr" in lower
    assert "changing" in lower or "change" in lower


def test_says_auto_adjust_false(spec_text):
    assert "auto_adjust=False" in spec_text


def test_says_daily_ohlcv_only(spec_text):
    assert "Daily OHLCV only" in spec_text


def test_split_spec_mentions_first_trading_day_on_or_after(spec_text):
    lower = spec_text.lower()
    assert "first available trading day on or after" in lower or \
           "first trading day on or after" in lower
