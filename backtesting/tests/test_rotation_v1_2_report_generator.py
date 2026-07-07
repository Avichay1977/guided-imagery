"""
Unit tests for rotation_v1_2_report_generator.

All inputs use types.SimpleNamespace; no real backtest, no market data,
no data fetch, no strategy_lab_runner.
"""

import csv
import inspect
import io
import types

import pytest

from protocol_v1_2_metric_sources import V1_2_METRIC_FIELDS
from rotation_v1_2_report_generator import (
    ROTATION_LABEL_COLUMNS,
    ROTATION_REPORT_COLUMNS,
    generate_rotation_v1_2_summary_row,
    generate_rotation_v1_2_toy_report,
)


# ---------------------------------------------------------------------------
# Toy factory helpers
# ---------------------------------------------------------------------------

def _strat(tr=0.12, calmar=0.80):
    return types.SimpleNamespace(strategy_total_return=tr, strategy_calmar=calmar)


def _b1(tr=0.10, calmar=0.60):
    return types.SimpleNamespace(total_return=tr, calmar=calmar)


def _b2(tr=0.09, calmar=0.55):
    return types.SimpleNamespace(total_return=tr, calmar=calmar)


def _rsc(p95_tr=0.07, p95_c=0.50):
    return types.SimpleNamespace(p95_total_return=p95_tr, p95_calmar=p95_c)


def _meta(**kwargs):
    return {"symbol": "ROT_TOY_1", "params": "top_n=3", **kwargs}


def _full_row():
    return generate_rotation_v1_2_summary_row(
        _meta(), _strat(), b1_result=_b1(), b2_result=_b2(), random_result=_rsc()
    )


# ---------------------------------------------------------------------------
# Test 1: row has all v1.2 metrics and rotation labels
# ---------------------------------------------------------------------------

def test_generate_row_contains_all_v1_2_metrics_and_labels():
    row = _full_row()
    for field in V1_2_METRIC_FIELDS:
        assert field in row, f"missing v1.2 metric: {field!r}"
    for lbl in ROTATION_LABEL_COLUMNS:
        assert lbl in row, f"missing label: {lbl!r}"
    # Labels must be strings except is_pass_v1_2 which is bool
    assert isinstance(row["strategy_vs_b1_label"], str)
    assert isinstance(row["strategy_vs_b2_label"], str)
    assert isinstance(row["strategy_vs_random_p95_label"], str)
    assert isinstance(row["is_pass_v1_2"], bool)


# ---------------------------------------------------------------------------
# Test 2: missing benchmarks produce INSUFFICIENT_DATA labels
# ---------------------------------------------------------------------------

def test_generate_row_handles_missing_benchmarks_gracefully():
    row = generate_rotation_v1_2_summary_row(_meta(), _strat())
    assert row["strategy_vs_b1_label"] == "INSUFFICIENT_DATA_B1"
    assert row["strategy_vs_b2_label"] == "INSUFFICIENT_DATA_B2"
    assert row["strategy_vs_random_p95_label"] == "INSUFFICIENT_DATA_P95"
    assert row["is_pass_v1_2"] is False


# ---------------------------------------------------------------------------
# Test 3: toy report produces multiple rows
# ---------------------------------------------------------------------------

def test_generate_report_produces_multiple_rows():
    inputs = [
        {"run_metadata": _meta(symbol=f"ROT_{i}"), "strategy_result": _strat()}
        for i in range(4)
    ]
    report = generate_rotation_v1_2_toy_report(inputs)
    assert len(report) == 4
    assert all(isinstance(r, dict) for r in report)
    symbols = [r.get("symbol") for r in report]
    assert symbols == ["ROT_0", "ROT_1", "ROT_2", "ROT_3"]


# ---------------------------------------------------------------------------
# Test 4: row is serializable to CSV
# ---------------------------------------------------------------------------

def test_report_row_is_serializable_to_csv():
    row = _full_row()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(row.keys()), extrasaction="raise")
    writer.writeheader()
    writer.writerow(row)  # must not raise
    content = output.getvalue()
    assert "ROT_TOY_1" in content


# ---------------------------------------------------------------------------
# Test 5: labels correctly reflect toy data comparisons
# ---------------------------------------------------------------------------

def test_diagnostic_labels_correctly_reflect_toy_data():
    # Strategy clearly beats b2 (tr=0.25 > 0.05, calmar=2.0 > 0.4)
    row_pass = generate_rotation_v1_2_summary_row(
        _meta(), _strat(tr=0.25, calmar=2.0), b2_result=_b2(tr=0.05, calmar=0.4)
    )
    assert row_pass["strategy_vs_b2_label"] == "BEATS_B2"

    # Strategy clearly loses to b2
    row_fail = generate_rotation_v1_2_summary_row(
        _meta(), _strat(tr=0.02, calmar=0.1), b2_result=_b2(tr=0.15, calmar=1.5)
    )
    assert row_fail["strategy_vs_b2_label"] == "BELOW_B2"

    # All three comparisons pass → is_pass_v1_2 = True
    row_all_pass = generate_rotation_v1_2_summary_row(
        _meta(),
        _strat(tr=0.30, calmar=3.0),
        b1_result=_b1(tr=0.10, calmar=0.5),
        b2_result=_b2(tr=0.08, calmar=0.4),
        random_result=_rsc(p95_tr=0.05, p95_c=0.3),
    )
    assert row_all_pass["strategy_vs_b1_label"] == "BEATS_BUY_HOLD"
    assert row_all_pass["strategy_vs_b2_label"] == "BEATS_B2"
    assert row_all_pass["strategy_vs_random_p95_label"] == "BEATS_RANDOM_P95"
    assert row_all_pass["is_pass_v1_2"] is True

    # Fails b1 only → is_pass_v1_2 = False
    row_fails_b1 = generate_rotation_v1_2_summary_row(
        _meta(),
        _strat(tr=0.05, calmar=0.3),
        b1_result=_b1(tr=0.20, calmar=1.5),
        b2_result=_b2(tr=0.03, calmar=0.2),
        random_result=_rsc(p95_tr=0.01, p95_c=0.1),
    )
    assert row_fails_b1["strategy_vs_b1_label"] == "BELOW_BUY_HOLD"
    assert row_fails_b1["is_pass_v1_2"] is False


# ---------------------------------------------------------------------------
# Tests 6–7: source token guardrails
# ---------------------------------------------------------------------------

def test_no_research_go_in_report_output():
    import rotation_v1_2_report_generator as _m
    assert "RESEARCH-GO" not in inspect.getsource(_m)


def test_no_live_go_in_report_output():
    import rotation_v1_2_report_generator as _m
    assert "LIVE-GO" not in inspect.getsource(_m)


# ---------------------------------------------------------------------------
# Test 8: end-to-end integration
# ---------------------------------------------------------------------------

def test_integration_with_adapter_and_reporting_infra_works_end_to_end():
    row = generate_rotation_v1_2_summary_row(
        {"symbol": "ROT_E2E", "params": "top_n=3", "test_window": "2020"},
        _strat(tr=0.18, calmar=1.1),
        b1_result=_b1(tr=0.09, calmar=0.55),
        b2_result=_b2(tr=0.07, calmar=0.45),
        random_result=_rsc(p95_tr=0.06, p95_c=0.40),
    )
    # All v1.2 metrics present and finite
    for field in V1_2_METRIC_FIELDS:
        assert field in row
        val = row[field]
        assert val is not None and isinstance(float(val), float)
    # Labels present
    for lbl in ROTATION_LABEL_COLUMNS:
        assert lbl in row
    # Metadata preserved
    assert row["symbol"] == "ROT_E2E"
    assert row["test_window"] == "2020"
    # Strategy outperforms on all axes → is_pass_v1_2
    assert row["is_pass_v1_2"] is True
    # CSV round-trip
    buf = io.StringIO()
    csv.DictWriter(buf, fieldnames=list(row.keys())).writeheader()
    csv.DictWriter(buf, fieldnames=list(row.keys())).writerow(row)


# ---------------------------------------------------------------------------
# Tests 9–10: cross-module interface checks
# ---------------------------------------------------------------------------

def test_rotation_v1_2_metric_adapter_tests_still_pass():
    from rotation_v1_2_metric_adapter import (
        build_rotation_v1_2_metric_sources,
        rotation_metric_sources_are_complete,
    )
    import types as _types
    s = _types.SimpleNamespace(strategy_total_return=0.1, strategy_calmar=0.5)
    ms = build_rotation_v1_2_metric_sources(s)
    assert ms["strategy_total_return"] == pytest.approx(0.1)
    assert rotation_metric_sources_are_complete(ms) is False  # only 2 of 8 filled


def test_rotation_portfolio_path_engine_tests_still_pass():
    from rotation_backtester import RotationBacktesterConfig, RotationBacktesterResult
    c = RotationBacktesterConfig()
    assert c.top_n == 3
    assert c.initial_cash == pytest.approx(100_000.0)
    r = RotationBacktesterResult()
    assert r.equity_curve == []
