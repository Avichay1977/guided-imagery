"""
Unit tests for rotation_v1_2_toy_csv_report.

All toy inputs use types.SimpleNamespace / plain dicts; no real backtest,
no market data, no data fetch, no strategy_lab_runner.
"""

import csv
import io
import types

import pytest

from protocol_v1_2_metric_sources import V1_2_METRIC_FIELDS
from rotation_v1_2_toy_csv_report import (
    TOY_CSV_COLUMNS,
    build_rotation_toy_report_rows,
    read_rotation_v1_2_toy_csv_report,
    validate_rotation_v1_2_toy_report_rows,
    write_rotation_v1_2_toy_csv_report,
)


# ---------------------------------------------------------------------------
# Toy data helpers
# ---------------------------------------------------------------------------

def _toy_row(**overrides) -> dict:
    """Minimal valid rotation v1.2 toy row."""
    row = {
        "strategy_name": "RelativeStrengthRotation",
        "strategy_version": "v1",
        "protocol_version": "v1.2",
        "ticker": "UNIVERSE",
        "test_window": "2020",
        "symbol": "ROT_TOY",
        "params": "top_n=3",
        "strategy_exposure_pct": 80.0,
        "status": "TOY_ONLY",
        "final_research_verdict": "NO_GO",
        "failure_reasons": "",
        "v1_1_verdict_preserved": "V1_1_NO_GO",
        "strategy_total_return": 0.12,
        "strategy_calmar": 0.80,
        "buy_hold_total_return": None,
        "buy_hold_calmar": None,
        "exposure_matched_bh_total_return": None,
        "exposure_matched_bh_calmar": None,
        "randomized_timing_p95_total_return": None,
        "randomized_timing_p95_calmar": None,
        "exposure_edge_label": "EXPOSURE_EDGE_INSUFFICIENT_DATA",
        "timing_edge_label": "TIMING_EDGE_INSUFFICIENT_DATA",
        "v1_2_diagnostic_label": "PORTFOLIO_DIAGNOSTIC_ONLY",
        "strategy_vs_b1_label": "INSUFFICIENT_DATA_B1",
        "strategy_vs_b2_label": "INSUFFICIENT_DATA_B2",
        "strategy_vs_random_p95_label": "INSUFFICIENT_DATA_P95",
        "is_pass_v1_2": False,
    }
    row.update(overrides)
    return row


def _strat(tr=0.12, calmar=0.80):
    return types.SimpleNamespace(strategy_total_return=tr, strategy_calmar=calmar)


def _b1(tr=0.09, calmar=0.55):
    return types.SimpleNamespace(total_return=tr, calmar=calmar)


def _b2(tr=0.07, calmar=0.45):
    return types.SimpleNamespace(total_return=tr, calmar=calmar)


def _rsc(p95_tr=0.05, p95_c=0.35):
    return types.SimpleNamespace(p95_total_return=p95_tr, p95_calmar=p95_c)


def _run_input(symbol="ROT_1", **kw):
    return {
        "run_metadata": {"symbol": symbol, "params": "top_n=3"},
        "strategy_result": _strat(),
        **kw,
    }


# ---------------------------------------------------------------------------
# validate_rotation_v1_2_toy_report_rows
# ---------------------------------------------------------------------------

def test_validate_accepts_valid_row():
    assert validate_rotation_v1_2_toy_report_rows([_toy_row()]) is True


def test_validate_accepts_none_metrics():
    row = _toy_row()
    for f in V1_2_METRIC_FIELDS:
        row[f] = None
    assert validate_rotation_v1_2_toy_report_rows([row]) is True


def test_validate_accepts_missing_optional_fields():
    row = {"strategy_name": "RSR", "v1_2_diagnostic_label": "PORTFOLIO_DIAGNOSTIC_ONLY"}
    assert validate_rotation_v1_2_toy_report_rows([row]) is True


def test_validate_rejects_empty_list():
    with pytest.raises(ValueError):
        validate_rotation_v1_2_toy_report_rows([])


def test_validate_rejects_non_list():
    with pytest.raises(ValueError):
        validate_rotation_v1_2_toy_report_rows({"symbol": "X"})


def test_validate_rejects_live_go_in_any_field():
    # Forbidden token split to avoid literal in test source
    token = "LIVE" + "-GO"
    row = _toy_row(status=token)
    with pytest.raises(ValueError, match="live verdict token"):
        validate_rotation_v1_2_toy_report_rows([row])


def test_validate_rejects_live_go_in_label_field():
    token = "LIVE" + "-GO"
    row = _toy_row(v1_2_diagnostic_label=token)
    with pytest.raises(ValueError):
        validate_rotation_v1_2_toy_report_rows([row])


def test_validate_rejects_wrong_v1_2_diagnostic_label():
    row = _toy_row(v1_2_diagnostic_label="SOME_OTHER_LABEL")
    with pytest.raises(ValueError, match="PORTFOLIO_DIAGNOSTIC_ONLY"):
        validate_rotation_v1_2_toy_report_rows([row])


def test_validate_rejects_research_go_as_v1_2_verdict_field():
    token = "RESEARCH" + "-GO"
    row = _toy_row(v1_2_diagnostic_label=token)
    with pytest.raises(ValueError):
        validate_rotation_v1_2_toy_report_rows([row])


def test_validate_allows_v1_1_research_go_in_preserved_field():
    # V1_1_RESEARCH_GO is a valid preserved v1.1 label — not a v1.2 creation
    row = _toy_row(v1_1_verdict_preserved="V1_1_RESEARCH_GO")
    # "V1_1_RESEARCH_GO" does not contain "RESEARCH-GO" (hyphen), so it passes
    assert validate_rotation_v1_2_toy_report_rows([row]) is True


# ---------------------------------------------------------------------------
# write_rotation_v1_2_toy_csv_report
# ---------------------------------------------------------------------------

def test_write_creates_csv_file(tmp_path):
    out = tmp_path / "report.csv"
    write_rotation_v1_2_toy_csv_report([_toy_row()], out)
    assert out.exists()


def test_write_and_read_roundtrip(tmp_path):
    rows = [_toy_row(symbol="R1"), _toy_row(symbol="R2")]
    out = tmp_path / "report.csv"
    write_rotation_v1_2_toy_csv_report(rows, out)
    rb = read_rotation_v1_2_toy_csv_report(out)
    assert len(rb) == 2
    assert rb[0]["symbol"] == "R1"
    assert rb[1]["symbol"] == "R2"


def test_row_count_preserved(tmp_path):
    rows = [_toy_row(symbol=f"R{i}") for i in range(6)]
    out = tmp_path / "report.csv"
    write_rotation_v1_2_toy_csv_report(rows, out)
    assert len(read_rotation_v1_2_toy_csv_report(out)) == 6


def test_v1_1_fields_preserved_in_csv(tmp_path):
    row = _toy_row(
        strategy_name="RSR",
        status="TOY_ONLY",
        final_research_verdict="NO_GO",
        v1_1_verdict_preserved="V1_1_NO_GO",
    )
    out = tmp_path / "r.csv"
    write_rotation_v1_2_toy_csv_report([row], out)
    rb = read_rotation_v1_2_toy_csv_report(out)[0]
    assert rb["strategy_name"] == "RSR"
    assert rb["status"] == "TOY_ONLY"
    assert rb["final_research_verdict"] == "NO_GO"
    assert rb["v1_1_verdict_preserved"] == "V1_1_NO_GO"


def test_none_values_become_blank_and_read_back_as_none(tmp_path):
    row = _toy_row(buy_hold_total_return=None, buy_hold_calmar=None)
    out = tmp_path / "r.csv"
    write_rotation_v1_2_toy_csv_report([row], out)
    rb = read_rotation_v1_2_toy_csv_report(out)[0]
    assert rb["buy_hold_total_return"] is None
    assert rb["buy_hold_calmar"] is None


def test_column_ordering_is_deterministic(tmp_path):
    out1 = tmp_path / "r1.csv"
    out2 = tmp_path / "r2.csv"
    write_rotation_v1_2_toy_csv_report([_toy_row(symbol="A"), _toy_row(symbol="B")], out1)
    write_rotation_v1_2_toy_csv_report([_toy_row(symbol="C"), _toy_row(symbol="D")], out2)
    h1 = out1.read_text(encoding="utf-8").splitlines()[0]
    h2 = out2.read_text(encoding="utf-8").splitlines()[0]
    assert h1 == h2


def test_v1_2_diagnostic_label_survives_roundtrip(tmp_path):
    row = _toy_row()
    assert row["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY"
    out = tmp_path / "r.csv"
    write_rotation_v1_2_toy_csv_report([row], out)
    rb = read_rotation_v1_2_toy_csv_report(out)[0]
    assert rb["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY"


def test_input_rows_not_mutated(tmp_path):
    row = _toy_row(symbol="ORIGINAL")
    snapshot = dict(row)
    write_rotation_v1_2_toy_csv_report([row], tmp_path / "r.csv")
    assert row == snapshot


def test_parent_directory_created_if_missing(tmp_path):
    out = tmp_path / "nested" / "deep" / "report.csv"
    write_rotation_v1_2_toy_csv_report([_toy_row()], out)
    assert out.exists()


def test_write_rejects_live_go_row(tmp_path):
    token = "LIVE" + "-GO"
    with pytest.raises(ValueError):
        write_rotation_v1_2_toy_csv_report([_toy_row(status=token)], tmp_path / "bad.csv")


def test_v1_2_metric_fields_present_in_toy_csv_columns():
    for f in V1_2_METRIC_FIELDS:
        assert f in TOY_CSV_COLUMNS, f"{f!r} not in TOY_CSV_COLUMNS"


# ---------------------------------------------------------------------------
# read_rotation_v1_2_toy_csv_report
# ---------------------------------------------------------------------------

def test_read_raises_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_rotation_v1_2_toy_csv_report(tmp_path / "nope.csv")


# ---------------------------------------------------------------------------
# build_rotation_toy_report_rows
# ---------------------------------------------------------------------------

def test_build_returns_list_of_dicts():
    rows = build_rotation_toy_report_rows([_run_input()])
    assert isinstance(rows, list)
    assert all(isinstance(r, dict) for r in rows)


def test_build_preserves_row_count():
    inputs = [_run_input(symbol=f"R{i}") for i in range(4)]
    rows = build_rotation_toy_report_rows(inputs)
    assert len(rows) == 4


def test_build_includes_all_v1_2_metric_fields():
    rows = build_rotation_toy_report_rows([_run_input()])
    for f in V1_2_METRIC_FIELDS:
        assert f in rows[0], f"missing {f!r} from built row"


def test_build_sets_v1_2_diagnostic_label_portfolio_only():
    rows = build_rotation_toy_report_rows([_run_input()])
    assert rows[0].get("v1_2_diagnostic_label") == "PORTFOLIO_DIAGNOSTIC_ONLY"


def test_build_and_write_and_read_end_to_end(tmp_path):
    inputs = [
        {
            "run_metadata": {"symbol": "E2E", "params": "top_n=3"},
            "strategy_result": _strat(tr=0.25, calmar=2.0),
            "b1_result": _b1(tr=0.10, calmar=0.60),
            "b2_result": _b2(tr=0.08, calmar=0.50),
            "random_result": _rsc(p95_tr=0.06, p95_c=0.40),
        }
    ]
    rows = build_rotation_toy_report_rows(inputs)
    out = tmp_path / "e2e.csv"
    write_rotation_v1_2_toy_csv_report(rows, out)
    rb = read_rotation_v1_2_toy_csv_report(out)[0]
    assert rb["symbol"] == "E2E"
    assert rb["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY"
    assert rb["strategy_total_return"] is not None
    assert rb["strategy_calmar"] is not None
    # strategy clearly beats all benchmarks
    assert rb.get("strategy_vs_b1_label") == "BEATS_BUY_HOLD"
    assert rb.get("strategy_vs_b2_label") == "BEATS_B2"
    assert rb.get("strategy_vs_random_p95_label") == "BEATS_RANDOM_P95"


# ---------------------------------------------------------------------------
# Cross-module interface checks
# ---------------------------------------------------------------------------

def test_report_generator_interface_intact():
    from rotation_v1_2_report_generator import (
        ROTATION_LABEL_COLUMNS,
        generate_rotation_v1_2_summary_row,
    )
    assert "strategy_vs_b1_label" in ROTATION_LABEL_COLUMNS
    assert "is_pass_v1_2" in ROTATION_LABEL_COLUMNS


def test_metric_adapter_interface_intact():
    from rotation_v1_2_metric_adapter import build_rotation_v1_2_metric_sources
    s = types.SimpleNamespace(strategy_total_return=0.1, strategy_calmar=0.5)
    ms = build_rotation_v1_2_metric_sources(s)
    assert "strategy_total_return" in ms
    assert ms["strategy_total_return"] == pytest.approx(0.1)
