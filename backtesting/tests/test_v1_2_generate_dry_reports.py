"""
v1.2 Dry Report Generation tests.

Toy deterministic CSVs only. No market data, no backtests, no strategy_lab_runner.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from v1_2_generate_dry_reports import main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _write_toy_csv(path: Path, *, p75_only: bool = True) -> pd.DataFrame:
    """Write a toy v1.1 summary CSV (mirrors strategy_lab row shape)."""
    rows = [
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
            "v1_1_verdict": "V1_1_NO_GO",
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
            "v1_1_verdict": "V1_1_INSUFFICIENT_DATA",
        },
    ]
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    return df


# ---------------------------------------------------------------------------
# 1. Creates output directory
# ---------------------------------------------------------------------------

def test_generate_dry_reports_creates_output_dir(tmp_path):
    inp = tmp_path / "in.csv"
    _write_toy_csv(inp)
    out_dir = tmp_path / "reports" / "nested"

    rc = main(["--inputs", str(inp), "--output-dir", str(out_dir)])
    assert rc == 0
    assert out_dir.exists() and out_dir.is_dir()


# ---------------------------------------------------------------------------
# 2. One output per input
# ---------------------------------------------------------------------------

def test_generate_dry_reports_writes_one_output_per_input(tmp_path):
    inp = tmp_path / "in.csv"
    _write_toy_csv(inp)
    out_dir = tmp_path / "reports"

    rc = main(["--inputs", str(inp), "--output-dir", str(out_dir)])
    assert rc == 0

    produced = list(out_dir.glob("*.csv"))
    assert len(produced) == 1


# ---------------------------------------------------------------------------
# 3. Row count preserved
# ---------------------------------------------------------------------------

def test_generate_dry_reports_preserves_row_count(tmp_path):
    inp = tmp_path / "in.csv"
    original = _write_toy_csv(inp)
    out_dir = tmp_path / "reports"

    main(["--inputs", str(inp), "--output-dir", str(out_dir)])
    out = pd.read_csv(out_dir / "in_v1_2.csv")
    assert len(out) == len(original)


# ---------------------------------------------------------------------------
# 4. Original v1.1 status column preserved
# ---------------------------------------------------------------------------

def test_generate_dry_reports_preserves_original_v1_1_status_column(tmp_path):
    inp = tmp_path / "in.csv"
    original = _write_toy_csv(inp)
    out_dir = tmp_path / "reports"

    main(["--inputs", str(inp), "--output-dir", str(out_dir)])
    out = pd.read_csv(out_dir / "in_v1_2.csv")
    assert list(out["status"]) == list(original["status"])


# ---------------------------------------------------------------------------
# 5. Original columns preserved
# ---------------------------------------------------------------------------

def test_generate_dry_reports_preserves_original_columns(tmp_path):
    inp = tmp_path / "in.csv"
    original = _write_toy_csv(inp)
    out_dir = tmp_path / "reports"

    main(["--inputs", str(inp), "--output-dir", str(out_dir)])
    out = pd.read_csv(out_dir / "in_v1_2.csv")
    for col in original.columns:
        assert col in out.columns, f"original column '{col}' missing in output"


# ---------------------------------------------------------------------------
# 6. Required v1.2 columns added
# ---------------------------------------------------------------------------

def test_generate_dry_reports_adds_required_v1_2_columns(tmp_path):
    inp = tmp_path / "in.csv"
    _write_toy_csv(inp)
    out_dir = tmp_path / "reports"

    main(["--inputs", str(inp), "--output-dir", str(out_dir)])
    out = pd.read_csv(out_dir / "in_v1_2.csv")
    for col in ("exposure_edge_label", "timing_edge_label",
                "v1_2_diagnostic_label", "protocol_version"):
        assert col in out.columns


# ---------------------------------------------------------------------------
# 7. Never overwrites input
# ---------------------------------------------------------------------------

def test_generate_dry_reports_never_overwrites_input(tmp_path):
    inp = tmp_path / "in.csv"
    _write_toy_csv(inp)
    before = inp.read_bytes()
    out_dir = tmp_path / "reports"

    main(["--inputs", str(inp), "--output-dir", str(out_dir)])
    after = inp.read_bytes()
    assert before == after, "input CSV was modified"


# ---------------------------------------------------------------------------
# 8. Missing metrics -> INSUFFICIENT_DATA
# ---------------------------------------------------------------------------

def test_generate_dry_reports_missing_metrics_yield_insufficient_data(tmp_path):
    inp = tmp_path / "in.csv"
    _write_toy_csv(inp)
    out_dir = tmp_path / "reports"

    main(["--inputs", str(inp), "--output-dir", str(out_dir)])
    out = pd.read_csv(out_dir / "in_v1_2.csv")
    assert (out["exposure_edge_label"] == "EXPOSURE_EDGE_INSUFFICIENT_DATA").all()
    assert (out["timing_edge_label"] == "TIMING_EDGE_INSUFFICIENT_DATA").all()


# ---------------------------------------------------------------------------
# 9. p75 not aliased to p95
# ---------------------------------------------------------------------------

def test_generate_dry_reports_does_not_alias_p75_to_p95(tmp_path):
    inp = tmp_path / "in.csv"
    _write_toy_csv(inp)  # has test_random_p75_calmar present
    out_dir = tmp_path / "reports"

    main(["--inputs", str(inp), "--output-dir", str(out_dir)])
    out = pd.read_csv(out_dir / "in_v1_2.csv")

    # p95 fields must be empty/NaN despite p75 being present
    assert out["randomized_timing_p95_calmar"].isna().all()
    assert out["randomized_timing_p95_total_return"].isna().all()
    # timing edge stays insufficient (no real p95 data)
    assert (out["timing_edge_label"] == "TIMING_EDGE_INSUFFICIENT_DATA").all()


# ---------------------------------------------------------------------------
# 10. No LIVE-GO output
# ---------------------------------------------------------------------------

def test_generate_dry_reports_no_live_go_output(tmp_path):
    inp = tmp_path / "in.csv"
    _write_toy_csv(inp)
    out_dir = tmp_path / "reports"

    main(["--inputs", str(inp), "--output-dir", str(out_dir)])
    out = pd.read_csv(out_dir / "in_v1_2.csv")
    for col in out.columns:
        for val in out[col].tolist():
            assert "LIVE-GO" not in str(val) and "LIVE_GO" not in str(val)


# ---------------------------------------------------------------------------
# 11. No v1.1 NO-GO converted to RESEARCH-GO
# ---------------------------------------------------------------------------

def test_generate_dry_reports_no_v1_1_no_go_converted_to_research_go(tmp_path):
    inp = tmp_path / "in.csv"
    _write_toy_csv(inp)
    out_dir = tmp_path / "reports"

    main(["--inputs", str(inp), "--output-dir", str(out_dir)])
    out = pd.read_csv(out_dir / "in_v1_2.csv")

    nogo = out[out["v1_1_verdict"] == "V1_1_NO_GO"]
    for label in nogo["v1_2_diagnostic_label"].tolist():
        assert "RESEARCH" not in str(label).upper()
    # The diagnostic label is always PORTFOLIO_DIAGNOSTIC_ONLY
    assert (out["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY").all()


# ---------------------------------------------------------------------------
# 12. Multiple inputs
# ---------------------------------------------------------------------------

def test_generate_dry_reports_supports_multiple_inputs(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    _write_toy_csv(a)
    _write_toy_csv(b)
    out_dir = tmp_path / "reports"

    rc = main(["--inputs", str(a), str(b), "--output-dir", str(out_dir)])
    assert rc == 0
    assert (out_dir / "a_v1_2.csv").exists()
    assert (out_dir / "b_v1_2.csv").exists()


# ---------------------------------------------------------------------------
# 13. Default suffix
# ---------------------------------------------------------------------------

def test_generate_dry_reports_default_suffix(tmp_path):
    inp = tmp_path / "in.csv"
    _write_toy_csv(inp)
    out_dir = tmp_path / "reports"

    main(["--inputs", str(inp), "--output-dir", str(out_dir)])
    assert (out_dir / "in_v1_2.csv").exists()


# ---------------------------------------------------------------------------
# 14. Custom suffix
# ---------------------------------------------------------------------------

def test_generate_dry_reports_custom_suffix(tmp_path):
    inp = tmp_path / "in.csv"
    _write_toy_csv(inp)
    out_dir = tmp_path / "reports"

    main(["--inputs", str(inp), "--output-dir", str(out_dir), "--suffix", "_exposurefair"])
    assert (out_dir / "in_exposurefair.csv").exists()


# ---------------------------------------------------------------------------
# 15. Fails on missing input
# ---------------------------------------------------------------------------

def test_generate_dry_reports_fails_on_missing_input(tmp_path):
    out_dir = tmp_path / "reports"
    rc = main(["--inputs", str(tmp_path / "nope.csv"), "--output-dir", str(out_dir)])
    assert rc == 1


# ---------------------------------------------------------------------------
# 16. Fails on empty CSV
# ---------------------------------------------------------------------------

def test_generate_dry_reports_fails_on_empty_csv(tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    out_dir = tmp_path / "reports"

    rc = main(["--inputs", str(empty), "--output-dir", str(out_dir)])
    assert rc == 1


# ---------------------------------------------------------------------------
# 17. Prints summary
# ---------------------------------------------------------------------------

def test_generate_dry_reports_prints_summary(tmp_path, capsys):
    inp = tmp_path / "in.csv"
    _write_toy_csv(inp)
    out_dir = tmp_path / "reports"

    main(["--inputs", str(inp), "--output-dir", str(out_dir)])
    captured = capsys.readouterr()
    out = captured.out
    assert "exposure_edge_label distribution" in out
    assert "timing_edge_label distribution" in out
    assert "LIVE-GO occurrences" in out
    assert str(inp) in out


# ---------------------------------------------------------------------------
# 18. Roundtrip CSV preserves v1.1 verdicts
# ---------------------------------------------------------------------------

def test_generate_dry_reports_roundtrip_csv_contains_preserved_v1_1_verdicts(tmp_path):
    inp = tmp_path / "in.csv"
    _write_toy_csv(inp)
    out_dir = tmp_path / "reports"

    main(["--inputs", str(inp), "--output-dir", str(out_dir)])
    out = pd.read_csv(out_dir / "in_v1_2.csv")

    # Original verdict column preserved
    assert list(out["v1_1_verdict"]) == ["V1_1_NO_GO", "V1_1_INSUFFICIENT_DATA"]
    # Preserved verdict column matches
    assert list(out["v1_1_verdict_preserved"]) == ["V1_1_NO_GO", "V1_1_INSUFFICIENT_DATA"]


# ---------------------------------------------------------------------------
# 19. Deterministic
# ---------------------------------------------------------------------------

def test_generate_dry_reports_is_deterministic(tmp_path):
    inp = tmp_path / "in.csv"
    _write_toy_csv(inp)
    out1 = tmp_path / "r1"
    out2 = tmp_path / "r2"

    main(["--inputs", str(inp), "--output-dir", str(out1)])
    main(["--inputs", str(inp), "--output-dir", str(out2)])

    df1 = pd.read_csv(out1 / "in_v1_2.csv")
    df2 = pd.read_csv(out2 / "in_v1_2.csv")
    assert df1.equals(df2)


# ---------------------------------------------------------------------------
# 20. Exit code zero on valid inputs
# ---------------------------------------------------------------------------

def test_generate_dry_reports_exit_code_zero_on_valid_inputs(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    _write_toy_csv(a)
    _write_toy_csv(b)
    out_dir = tmp_path / "reports"

    rc = main(["--inputs", str(a), str(b), "--output-dir", str(out_dir)])
    assert rc == 0
