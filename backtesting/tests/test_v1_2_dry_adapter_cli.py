"""
Unit tests for v1_2_dry_adapter_cli.

Deterministic toy CSVs only. No market data, no backtests, no fetching,
no full-runner execution.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from v1_2_dry_adapter_cli import main, _print_summary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _toy_v1_1_csv(path: Path) -> pd.DataFrame:
    """Write a minimal v1.1-shaped CSV to `path` and return the DataFrame."""
    df = pd.DataFrame([
        {
            "split_id": 0,
            "ticker": "TOY_A",
            "strategy_name": "TrendPullbackConfluence",
            "strategy_version": "v1",
            "test_start": "2018-01-01",
            "test_end": "2019-01-01",
            "test_total_trades": 10,
            "test_calmar": 0.40,
            "test_benchmark_calmar": 0.90,
            "test_exposure_matched_calmar": 0.60,
            "test_random_p75_calmar": 0.70,
            "status": "OK",
            "failure_reasons": "CALMAR_BELOW_BENCHMARK",
        },
        {
            "split_id": 1,
            "ticker": "TOY_B",
            "strategy_name": "TrendPullbackConfluence",
            "strategy_version": "v1",
            "test_start": "2019-01-01",
            "test_end": "2020-01-01",
            "test_total_trades": 2,
            "test_calmar": None,
            "test_benchmark_calmar": None,
            "test_exposure_matched_calmar": None,
            "test_random_p75_calmar": None,
            "status": "INSUFFICIENT_TEST_TRADES",
            "failure_reasons": "INSUFFICIENT_TEST_TRADES: 2 < 5",
        },
    ])
    df.to_csv(path, index=False)
    return df


# ---------------------------------------------------------------------------
# 1. Basic: writes output CSV with v1.2 columns
# ---------------------------------------------------------------------------

def test_cli_writes_output_csv(tmp_path):
    input_csv = tmp_path / "v1_1.csv"
    output_csv = tmp_path / "v1_2_out.csv"
    _toy_v1_1_csv(input_csv)

    rc = main(["--input", str(input_csv), "--output", str(output_csv), "--no-summary"])
    assert rc == 0
    assert output_csv.exists()

    result = pd.read_csv(output_csv)
    assert "exposure_edge_label" in result.columns
    assert "timing_edge_label" in result.columns
    assert "v1_2_diagnostic_label" in result.columns
    assert "protocol_version" in result.columns


# ---------------------------------------------------------------------------
# 2. Default output path: <stem>_v1_2.csv
# ---------------------------------------------------------------------------

def test_cli_default_output_path(tmp_path):
    input_csv = tmp_path / "v1_1_data.csv"
    _toy_v1_1_csv(input_csv)

    rc = main(["--input", str(input_csv), "--no-summary"])
    assert rc == 0

    expected_out = tmp_path / "v1_1_data_v1_2.csv"
    assert expected_out.exists()


# ---------------------------------------------------------------------------
# 3. v1.1 columns are preserved unchanged
# ---------------------------------------------------------------------------

def test_cli_v1_1_columns_preserved(tmp_path):
    input_csv = tmp_path / "v1_1.csv"
    output_csv = tmp_path / "out.csv"
    original = _toy_v1_1_csv(input_csv)

    main(["--input", str(input_csv), "--output", str(output_csv), "--no-summary"])
    result = pd.read_csv(output_csv)

    # All original columns present in output
    for col in original.columns:
        assert col in result.columns, f"v1.1 column '{col}' missing from output"

    # status and failure_reasons unchanged
    assert list(result["status"]) == list(original["status"])
    # failure_reasons has NaN for None rows — compare via str()
    for orig_val, out_val in zip(original["failure_reasons"].tolist(),
                                  result["failure_reasons"].tolist()):
        assert str(orig_val) == str(out_val)


# ---------------------------------------------------------------------------
# 4. No LIVE-GO anywhere in output
# ---------------------------------------------------------------------------

def test_cli_no_live_go_in_output(tmp_path):
    input_csv = tmp_path / "v1_1.csv"
    output_csv = tmp_path / "out.csv"
    _toy_v1_1_csv(input_csv)

    main(["--input", str(input_csv), "--output", str(output_csv), "--no-summary"])
    result = pd.read_csv(output_csv)

    for col in result.columns:
        for val in result[col].tolist():
            assert "LIVE-GO" not in str(val) and "LIVE_GO" not in str(val), (
                f"LIVE-GO found in column '{col}': {val!r}"
            )


# ---------------------------------------------------------------------------
# 5. v1_2_diagnostic_label is always PORTFOLIO_DIAGNOSTIC_ONLY
# ---------------------------------------------------------------------------

def test_cli_diagnostic_label_is_portfolio_only(tmp_path):
    input_csv = tmp_path / "v1_1.csv"
    output_csv = tmp_path / "out.csv"
    _toy_v1_1_csv(input_csv)

    main(["--input", str(input_csv), "--output", str(output_csv), "--no-summary"])
    result = pd.read_csv(output_csv)

    assert (result["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY").all()


# ---------------------------------------------------------------------------
# 6. INSUFFICIENT_DATA edges on raw v1.1 CSVs (missing total returns)
# ---------------------------------------------------------------------------

def test_cli_insufficient_data_edges_on_v1_1_csv(tmp_path):
    input_csv = tmp_path / "v1_1.csv"
    output_csv = tmp_path / "out.csv"
    _toy_v1_1_csv(input_csv)

    main(["--input", str(input_csv), "--output", str(output_csv), "--no-summary"])
    result = pd.read_csv(output_csv)

    # v1.1 CSVs lack total returns → edges must be INSUFFICIENT_DATA
    assert (result["exposure_edge_label"] == "EXPOSURE_EDGE_INSUFFICIENT_DATA").all()
    assert (result["timing_edge_label"] == "TIMING_EDGE_INSUFFICIENT_DATA").all()


# ---------------------------------------------------------------------------
# 7. protocol_version is v1.2
# ---------------------------------------------------------------------------

def test_cli_protocol_version(tmp_path):
    input_csv = tmp_path / "v1_1.csv"
    output_csv = tmp_path / "out.csv"
    _toy_v1_1_csv(input_csv)

    main(["--input", str(input_csv), "--output", str(output_csv), "--no-summary"])
    result = pd.read_csv(output_csv)

    assert (result["protocol_version"] == "v1.2").all()


# ---------------------------------------------------------------------------
# 8. Row count preserved
# ---------------------------------------------------------------------------

def test_cli_row_count_preserved(tmp_path):
    input_csv = tmp_path / "v1_1.csv"
    output_csv = tmp_path / "out.csv"
    original = _toy_v1_1_csv(input_csv)

    main(["--input", str(input_csv), "--output", str(output_csv), "--no-summary"])
    result = pd.read_csv(output_csv)

    assert len(result) == len(original)


# ---------------------------------------------------------------------------
# 9. v1_2_failure_reasons column present (collision prefix for failure_reasons)
# ---------------------------------------------------------------------------

def test_cli_v1_2_failure_reasons_column_present(tmp_path):
    input_csv = tmp_path / "v1_1.csv"
    output_csv = tmp_path / "out.csv"
    _toy_v1_1_csv(input_csv)

    main(["--input", str(input_csv), "--output", str(output_csv), "--no-summary"])
    result = pd.read_csv(output_csv)

    # failure_reasons already exists in v1.1 → v1.2 uses prefixed column
    assert "v1_2_failure_reasons" in result.columns
    # Original v1.1 failure_reasons column untouched
    assert "failure_reasons" in result.columns


# ---------------------------------------------------------------------------
# 10. Returns 1 on missing input file
# ---------------------------------------------------------------------------

def test_cli_returns_1_on_missing_input(tmp_path):
    rc = main(["--input", str(tmp_path / "nonexistent.csv"), "--no-summary"])
    assert rc == 1


# ---------------------------------------------------------------------------
# 11. Returns 1 on empty input file
# ---------------------------------------------------------------------------

def test_cli_returns_1_on_empty_input(tmp_path):
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("")

    rc = main(["--input", str(empty_csv), "--no-summary"])
    assert rc == 1


# ---------------------------------------------------------------------------
# 12. Metric overrides enable PASS classification
# ---------------------------------------------------------------------------

def test_cli_metric_overrides_enable_pass_classification(tmp_path):
    input_csv = tmp_path / "v1_1.csv"
    output_csv = tmp_path / "out.csv"
    # Only the OK-status row has meaningful calmars; INSUFFICIENT row stays insufficient
    _toy_v1_1_csv(input_csv)

    rc = main([
        "--input", str(input_csv),
        "--output", str(output_csv),
        "--no-summary",
        # strategy beats exposure-matched: 0.40 calmar > 0.60 EM? No — need to
        # make strategy win. Use obvious overrides.
        "--strategy-total-return", "0.99",
        "--exposure-matched-total-return", "0.10",
        "--p95-total-return", "0.05",
        "--p95-calmar", "0.10",
    ])
    assert rc == 0
    result = pd.read_csv(output_csv)

    # The row with status OK has test_calmar=0.40 → strategy_calmar=0.40
    # exposure_matched_bh_calmar=0.60 → strategy 0.40 < 0.60 → FAIL on calmar
    # But wait: TOY_A has test_calmar=0.40, EM=0.60 → calmar FAIL even with
    # good total returns. So exposure edge = FAIL for TOY_A.
    # TOY_B has None calmars → INSUFFICIENT.
    ok_row = result[result["ticker"] == "TOY_A"].iloc[0]
    insuf_row = result[result["ticker"] == "TOY_B"].iloc[0]

    assert ok_row["exposure_edge_label"] == "EXPOSURE_EDGE_FAIL"
    assert insuf_row["exposure_edge_label"] == "EXPOSURE_EDGE_INSUFFICIENT_DATA"

    # Timing edge: strategy_total_return=0.99 > p95_total_return=0.05,
    # strategy_calmar=0.40 > p95_calmar=0.10 → PASS for TOY_A
    assert ok_row["timing_edge_label"] == "TIMING_EDGE_PASS"
    assert insuf_row["timing_edge_label"] == "TIMING_EDGE_INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# 13. Idempotent: running twice produces identical outputs
# ---------------------------------------------------------------------------

def test_cli_idempotent(tmp_path):
    input_csv = tmp_path / "v1_1.csv"
    out1 = tmp_path / "out1.csv"
    out2 = tmp_path / "out2.csv"
    _toy_v1_1_csv(input_csv)

    main(["--input", str(input_csv), "--output", str(out1), "--no-summary"])
    main(["--input", str(input_csv), "--output", str(out2), "--no-summary"])

    df1 = pd.read_csv(out1)
    df2 = pd.read_csv(out2)
    assert df1.equals(df2)


# ---------------------------------------------------------------------------
# 14. Works on the actual strategy_lab_trendpullback_v1 CSV
# ---------------------------------------------------------------------------

def test_cli_works_on_actual_trendpullback_csv(tmp_path):
    actual_csv = Path(__file__).parent.parent / "strategy_lab_trendpullback_v1_momentum10y.csv"
    if not actual_csv.exists():
        pytest.skip("strategy_lab_trendpullback_v1_momentum10y.csv not present")

    output_csv = tmp_path / "out.csv"
    rc = main(["--input", str(actual_csv), "--output", str(output_csv), "--no-summary"])
    assert rc == 0

    result = pd.read_csv(output_csv)

    # Row count preserved
    original = pd.read_csv(actual_csv)
    assert len(result) == len(original)

    # v1.1 columns intact
    for col in original.columns:
        assert col in result.columns

    # No LIVE-GO
    for col in result.columns:
        for val in result[col].tolist():
            assert "LIVE-GO" not in str(val) and "LIVE_GO" not in str(val)

    # Diagnostic label fixed
    assert (result["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY").all()

    # All INSUFFICIENT_DATA (v1.1 CSV lacks total returns)
    assert (result["exposure_edge_label"] == "EXPOSURE_EDGE_INSUFFICIENT_DATA").all()
    assert (result["timing_edge_label"] == "TIMING_EDGE_INSUFFICIENT_DATA").all()


# ---------------------------------------------------------------------------
# 15. Works on the actual strategy_lab_momentum_v1 CSV
# ---------------------------------------------------------------------------

def test_cli_works_on_actual_momentum_csv(tmp_path):
    actual_csv = Path(__file__).parent.parent / "strategy_lab_momentum_v1_momentum10y.csv"
    if not actual_csv.exists():
        pytest.skip("strategy_lab_momentum_v1_momentum10y.csv not present")

    output_csv = tmp_path / "out.csv"
    rc = main(["--input", str(actual_csv), "--output", str(output_csv), "--no-summary"])
    assert rc == 0

    result = pd.read_csv(output_csv)
    original = pd.read_csv(actual_csv)

    assert len(result) == len(original)
    assert (result["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY").all()
    assert (result["protocol_version"] == "v1.2").all()
