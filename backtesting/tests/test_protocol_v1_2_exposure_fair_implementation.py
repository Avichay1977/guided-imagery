"""
Protocol v1.2 implementation unit tests.

Deterministic arithmetic fixtures only. No market data, no fetching, no
backtests. Toy data here is NOT research evidence.
"""

import math

import pytest

from protocol_v1_2_exposure_fair import (
    ALLOWED_OUTPUT_LABELS,
    EXPOSURE_EDGE_LABELS,
    PORTFOLIO_LABEL,
    PROTOCOL_VERSION,
    REQUIRED_V1_2_OUTPUT_COLUMNS,
    TIMING_EDGE_LABELS,
    build_v1_2_diagnostic_row,
    calculate_exposure_matched_benchmark,
    calmar_ratio,
    classify_exposure_edge,
    classify_timing_edge,
    max_drawdown,
    total_return,
)


EXPECTED_COLUMNS = [
    "strategy_name",
    "strategy_version",
    "protocol_version",
    "ticker",
    "test_window",
    "strategy_exposure_pct",
    "strategy_total_return",
    "strategy_calmar",
    "buy_hold_total_return",
    "buy_hold_calmar",
    "exposure_matched_bh_total_return",
    "exposure_matched_bh_calmar",
    "randomized_timing_p95_total_return",
    "randomized_timing_p95_calmar",
    "exposure_edge_label",
    "timing_edge_label",
    "v1_1_verdict_preserved",
    "v1_2_diagnostic_label",
    "failure_reasons",
]


def _row(**overrides):
    """A passing-by-default diagnostic row, with override hooks."""
    base = dict(
        strategy_name="TrendPullbackConfluence",
        strategy_version="v1",
        ticker="TOY",
        test_window="2018-2019",
        strategy_exposure_pct=40.0,
        strategy_total_return=0.30,
        strategy_calmar=0.80,
        buy_hold_total_return=0.50,
        buy_hold_calmar=0.90,
        exposure_matched_bh_total_return=0.20,
        exposure_matched_bh_calmar=0.60,
        randomized_timing_p95_total_return=0.25,
        randomized_timing_p95_calmar=0.70,
        v1_1_verdict_preserved="V1_1_NO_GO",
    )
    base.update(overrides)
    return build_v1_2_diagnostic_row(**base)


# ---------------------------------------------------------------------------
# 1. Required output columns exact
# ---------------------------------------------------------------------------

def test_required_output_columns_exact():
    assert REQUIRED_V1_2_OUTPUT_COLUMNS == EXPECTED_COLUMNS


# ---------------------------------------------------------------------------
# 2. Allowed labels exclude LIVE-GO
# ---------------------------------------------------------------------------

def test_allowed_labels_exclude_live_go():
    assert "LIVE-GO" not in ALLOWED_OUTPUT_LABELS
    assert "LIVE_GO" not in ALLOWED_OUTPUT_LABELS
    # RESEARCH-GO is also never an output label created by v1.2
    assert "RESEARCH-GO" not in ALLOWED_OUTPUT_LABELS
    assert "RESEARCH_GO" not in ALLOWED_OUTPUT_LABELS


# ---------------------------------------------------------------------------
# 3. Exposure-matched benchmark uses exposure fraction
# ---------------------------------------------------------------------------

def test_exposure_matched_benchmark_uses_exposure_fraction():
    returns = [0.10, -0.05, 0.02]
    out = calculate_exposure_matched_benchmark(returns, exposure_pct=50.0)
    # f = 0.5, cash_return = 0 -> each return halved
    assert out == pytest.approx([0.05, -0.025, 0.01])


# ---------------------------------------------------------------------------
# 4. Cash return defaults to zero
# ---------------------------------------------------------------------------

def test_exposure_matched_benchmark_cash_return_defaults_to_zero():
    returns = [0.10, 0.10]
    out_default = calculate_exposure_matched_benchmark(returns, exposure_pct=40.0)
    # f = 0.4, cash = 0 -> 0.04 each
    assert out_default == pytest.approx([0.04, 0.04])

    # Explicit non-zero cash return changes the blend
    out_cash = calculate_exposure_matched_benchmark(
        returns, exposure_pct=40.0, cash_return=0.01
    )
    # 0.10*0.4 + 0.01*0.6 = 0.04 + 0.006 = 0.046
    assert out_cash == pytest.approx([0.046, 0.046])


# ---------------------------------------------------------------------------
# 5-6. Exposure pct validation
# ---------------------------------------------------------------------------

def test_exposure_pct_validation_rejects_negative():
    with pytest.raises(ValueError):
        calculate_exposure_matched_benchmark([0.01], exposure_pct=-1.0)


def test_exposure_pct_validation_rejects_above_100():
    with pytest.raises(ValueError):
        calculate_exposure_matched_benchmark([0.01], exposure_pct=100.01)


# ---------------------------------------------------------------------------
# 7. Total return compounds
# ---------------------------------------------------------------------------

def test_total_return_compounds_returns():
    # (1.1)(1.1) - 1 = 0.21
    assert total_return([0.10, 0.10]) == pytest.approx(0.21)
    # empty -> 0
    assert total_return([]) == 0.0


# ---------------------------------------------------------------------------
# 8. Max drawdown detects drawdown
# ---------------------------------------------------------------------------

def test_max_drawdown_detects_drawdown():
    # up 20%, then down 50% -> from peak 1.2 to 0.6 = 50% drawdown
    dd = max_drawdown([0.20, -0.50])
    assert dd == pytest.approx(0.50)
    # monotonic up -> no drawdown
    assert max_drawdown([0.10, 0.10, 0.10]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 9. Calmar handles zero drawdown safely
# ---------------------------------------------------------------------------

def test_calmar_handles_zero_drawdown_safely():
    # No drawdown, positive return -> inf
    c_pos = calmar_ratio([0.01, 0.01, 0.01])
    assert c_pos == float("inf")

    # No drawdown, zero/empty -> 0.0
    assert calmar_ratio([]) == 0.0
    assert calmar_ratio([0.0, 0.0]) == 0.0

    # Drawdown present -> finite number
    c_fin = calmar_ratio([0.20, -0.50, 0.10])
    assert math.isfinite(c_fin)


# ---------------------------------------------------------------------------
# 10-13. Exposure edge classification
# ---------------------------------------------------------------------------

def test_exposure_edge_pass_requires_return_and_calmar_superiority():
    label = classify_exposure_edge(
        strategy_total_return=0.30,
        strategy_calmar=0.80,
        exposure_matched_bh_total_return=0.20,
        exposure_matched_bh_calmar=0.60,
    )
    assert label == "EXPOSURE_EDGE_PASS"


def test_exposure_edge_fails_when_only_return_beats():
    label = classify_exposure_edge(
        strategy_total_return=0.30,   # beats 0.20
        strategy_calmar=0.50,         # below 0.60
        exposure_matched_bh_total_return=0.20,
        exposure_matched_bh_calmar=0.60,
    )
    assert label == "EXPOSURE_EDGE_FAIL"


def test_exposure_edge_fails_when_only_calmar_beats():
    label = classify_exposure_edge(
        strategy_total_return=0.10,   # below 0.20
        strategy_calmar=0.80,         # beats 0.60
        exposure_matched_bh_total_return=0.20,
        exposure_matched_bh_calmar=0.60,
    )
    assert label == "EXPOSURE_EDGE_FAIL"


def test_exposure_edge_insufficient_on_nan():
    label = classify_exposure_edge(
        strategy_total_return=float("nan"),
        strategy_calmar=0.80,
        exposure_matched_bh_total_return=0.20,
        exposure_matched_bh_calmar=0.60,
    )
    assert label == "EXPOSURE_EDGE_INSUFFICIENT_DATA"

    label_none = classify_exposure_edge(0.30, 0.80, None, 0.60)
    assert label_none == "EXPOSURE_EDGE_INSUFFICIENT_DATA"

    label_inf = classify_exposure_edge(0.30, float("inf"), 0.20, 0.60)
    assert label_inf == "EXPOSURE_EDGE_INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# 14-16. Timing edge classification
# ---------------------------------------------------------------------------

def test_timing_edge_pass_requires_return_and_calmar_above_p95():
    label = classify_timing_edge(
        strategy_total_return=0.40,
        strategy_calmar=0.90,
        randomized_timing_p95_total_return=0.25,
        randomized_timing_p95_calmar=0.70,
    )
    assert label == "TIMING_EDGE_PASS"


def test_timing_edge_fail_when_below_random_p95():
    label = classify_timing_edge(
        strategy_total_return=0.10,   # below p95 0.25
        strategy_calmar=0.90,
        randomized_timing_p95_total_return=0.25,
        randomized_timing_p95_calmar=0.70,
    )
    assert label == "TIMING_EDGE_FAIL"


def test_timing_edge_insufficient_on_missing_metric():
    label = classify_timing_edge(0.40, 0.90, None, 0.70)
    assert label == "TIMING_EDGE_INSUFFICIENT_DATA"

    label_nan = classify_timing_edge(0.40, float("nan"), 0.25, 0.70)
    assert label_nan == "TIMING_EDGE_INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# 17. Diagnostic row has exact required columns
# ---------------------------------------------------------------------------

def test_diagnostic_row_has_exact_required_columns():
    row = _row()
    assert list(row.keys()) == REQUIRED_V1_2_OUTPUT_COLUMNS


# ---------------------------------------------------------------------------
# 18. Diagnostic row preserves v1.1 verdict
# ---------------------------------------------------------------------------

def test_diagnostic_row_preserves_v1_1_verdict():
    row = _row(v1_1_verdict_preserved="V1_1_NO_GO")
    assert row["v1_1_verdict_preserved"] == "V1_1_NO_GO"

    row2 = _row(v1_1_verdict_preserved="V1_1_INSUFFICIENT_DATA")
    assert row2["v1_1_verdict_preserved"] == "V1_1_INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# 19. Exposure edge pass does NOT create RESEARCH-GO
# ---------------------------------------------------------------------------

def test_exposure_edge_pass_does_not_create_research_go():
    # Strategy clears exposure-matched on both metrics, but v1.1 said NO-GO.
    row = _row(
        strategy_total_return=0.99,
        strategy_calmar=9.9,
        exposure_matched_bh_total_return=0.10,
        exposure_matched_bh_calmar=0.20,
        v1_1_verdict_preserved="V1_1_NO_GO",
    )
    assert row["exposure_edge_label"] == "EXPOSURE_EDGE_PASS"
    # v1.1 verdict is untouched, diagnostic label is not a research approval
    assert row["v1_1_verdict_preserved"] == "V1_1_NO_GO"
    assert row["v1_2_diagnostic_label"] == PORTFOLIO_LABEL
    assert row["v1_2_diagnostic_label"] not in ("RESEARCH-GO", "RESEARCH_GO")


# ---------------------------------------------------------------------------
# 20. Timing edge pass does NOT create LIVE-GO
# ---------------------------------------------------------------------------

def test_timing_edge_pass_does_not_create_live_go():
    row = _row(
        strategy_total_return=0.99,
        strategy_calmar=9.9,
        randomized_timing_p95_total_return=0.10,
        randomized_timing_p95_calmar=0.20,
    )
    assert row["timing_edge_label"] == "TIMING_EDGE_PASS"
    assert row["v1_2_diagnostic_label"] == PORTFOLIO_LABEL
    assert row["v1_2_diagnostic_label"] not in ("LIVE-GO", "LIVE_GO")


# ---------------------------------------------------------------------------
# 21. Failure reasons present when any edge fails
# ---------------------------------------------------------------------------

def test_failure_reasons_present_when_any_edge_fails():
    # Make timing fail (return below p95), exposure pass
    row = _row(
        strategy_total_return=0.22,           # beats EM 0.20, below p95 0.25
        strategy_calmar=0.80,                 # beats EM 0.60 and p95 0.70
    )
    assert row["exposure_edge_label"] == "EXPOSURE_EDGE_PASS"
    assert row["timing_edge_label"] == "TIMING_EDGE_FAIL"
    assert "TIMING_EDGE_FAIL" in row["failure_reasons"]

    # Both pass -> no failure reasons
    row_ok = _row(
        strategy_total_return=0.99,
        strategy_calmar=9.9,
        exposure_matched_bh_total_return=0.10,
        exposure_matched_bh_calmar=0.20,
        randomized_timing_p95_total_return=0.10,
        randomized_timing_p95_calmar=0.20,
    )
    assert row_ok["exposure_edge_label"] == "EXPOSURE_EDGE_PASS"
    assert row_ok["timing_edge_label"] == "TIMING_EDGE_PASS"
    assert row_ok["failure_reasons"] == ""


# ---------------------------------------------------------------------------
# 22. Protocol version is v1.2
# ---------------------------------------------------------------------------

def test_protocol_version_is_v1_2():
    assert PROTOCOL_VERSION == "v1.2"
    row = _row()
    assert row["protocol_version"] == "v1.2"


# ---------------------------------------------------------------------------
# 23. No LIVE-GO in output labels
# ---------------------------------------------------------------------------

def test_no_live_go_in_output_labels():
    for lab in ALLOWED_OUTPUT_LABELS:
        assert "LIVE" not in lab.upper(), f"LIVE found in output label: {lab}"


# ---------------------------------------------------------------------------
# 24. No RESEARCH-GO created by v1.2 diagnostic
# ---------------------------------------------------------------------------

def test_no_research_go_created_by_v1_2_diagnostic():
    # Across many metric permutations the diagnostic label is always PORTFOLIO_DIAGNOSTIC_ONLY
    for s_ret, s_cal in [(0.99, 9.9), (-0.5, -0.5), (0.0, 0.0)]:
        row = _row(strategy_total_return=s_ret, strategy_calmar=s_cal)
        assert row["v1_2_diagnostic_label"] == PORTFOLIO_LABEL
        assert "RESEARCH" not in row["v1_2_diagnostic_label"].upper()


# ---------------------------------------------------------------------------
# 25. PORTFOLIO_DIAGNOSTIC_ONLY label available
# ---------------------------------------------------------------------------

def test_portfolio_diagnostic_only_label_available():
    assert PORTFOLIO_LABEL == "PORTFOLIO_DIAGNOSTIC_ONLY"
    assert PORTFOLIO_LABEL in ALLOWED_OUTPUT_LABELS
    # The three label groups are exactly as specified
    assert EXPOSURE_EDGE_LABELS == [
        "EXPOSURE_EDGE_PASS", "EXPOSURE_EDGE_FAIL", "EXPOSURE_EDGE_INSUFFICIENT_DATA",
    ]
    assert TIMING_EDGE_LABELS == [
        "TIMING_EDGE_PASS", "TIMING_EDGE_FAIL", "TIMING_EDGE_INSUFFICIENT_DATA",
    ]
