"""
Protocol v1.2 dry reporting smoke test.

End-to-end of the REPORTING layer only: take a toy v1.1-style summary table,
append v1.2 side-by-side columns, round-trip through CSV, and confirm nothing
breaks. No backtests, no market data, no fetching, no full runner.

The toy rows are reporting fixtures — NOT real market data and NOT research
evidence.
"""

import pandas as pd

from protocol_v1_2_exposure_fair import REQUIRED_V1_2_OUTPUT_COLUMNS
from protocol_v1_2_reporting import add_v1_2_columns


# ---------------------------------------------------------------------------
# Toy v1.1 summary table (reporting fixture only)
# ---------------------------------------------------------------------------

def _toy_v1_1_summary() -> pd.DataFrame:
    """
    Three deterministic rows mimicking existing strategy-lab summary rows:
    one NO-GO, one INSUFFICIENT-DATA, one RESEARCH-GO.
    """
    return pd.DataFrame([
        {
            "ticker": "TOY_NOGO",
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
            "ticker": "TOY_INSUF",
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
        {
            "ticker": "TOY_RGO",
            "strategy_name": "TrendPullbackConfluence",
            "strategy_version": "v1",
            "test_start": "2020-01-01",
            "test_end": "2021-01-01",
            "test_total_trades": 25,
            "test_calmar": 1.50,
            "test_benchmark_calmar": 1.10,
            "test_exposure_matched_calmar": 0.90,
            "test_random_p75_calmar": 0.80,
            "status": "OK",
            "failure_reasons": "",
            "v1_1_verdict": "V1_1_RESEARCH_GO",
        },
    ])


# ---------------------------------------------------------------------------
# Smoke: structure, preservation, separation
# ---------------------------------------------------------------------------

def test_v1_2_dry_reporting_structure_and_preservation():
    df = _toy_v1_1_summary()
    out = add_v1_2_columns(df)

    # Row count preserved
    assert len(out) == len(df) == 3

    # Original v1.1 columns unchanged (status + verdict + failure_reasons)
    assert (out["status"] == df["status"].values).all()
    assert (out["v1_1_verdict"] == df["v1_1_verdict"].values).all()
    assert (out["failure_reasons"] == df["failure_reasons"].values).all()

    # v1.2 side-by-side columns present
    assert "v1_1_verdict_preserved" in out.columns
    assert "protocol_version" in out.columns
    assert "v1_2_diagnostic_label" in out.columns
    assert "exposure_edge_label" in out.columns
    assert "timing_edge_label" in out.columns

    # Preserved verdict matches original verdict
    assert (out["v1_1_verdict_preserved"] == df["v1_1_verdict"].values).all()

    # protocol_version and diagnostic label fixed
    assert (out["protocol_version"] == "v1.2").all()
    assert (out["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY").all()

    # All required v1.2 columns present (directly or under v1_2_ prefix)
    for col in REQUIRED_V1_2_OUTPUT_COLUMNS:
        assert col in out.columns or f"v1_2_{col}" in out.columns, f"missing {col}"

    # Labels are separate from the v1.1 verdict namespace
    for _, row in out.iterrows():
        assert str(row["exposure_edge_label"]).startswith("EXPOSURE_EDGE_")
        assert str(row["timing_edge_label"]).startswith("TIMING_EDGE_")
        assert str(row["v1_1_verdict_preserved"]).startswith("V1_1_")


def test_v1_2_dry_reporting_no_live_go_and_no_research_go_creation():
    df = _toy_v1_1_summary()
    out = add_v1_2_columns(df)

    # LIVE-GO appears nowhere (str() per element; all-None columns coerce to
    # float NaN, so astype(str) is not reliable across pandas versions)
    for col in out.columns:
        for val in out[col].tolist():
            assert "LIVE-GO" not in str(val) and "LIVE_GO" not in str(val)

    # v1.2 never creates RESEARCH-GO; the only RESEARCH-GO present is the
    # preserved v1.1 verdict, never a v1.2 diagnostic label
    assert (out["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY").all()
    # The NO-GO row stays NO-GO
    nogo = out[out["ticker"] == "TOY_NOGO"].iloc[0]
    assert nogo["v1_1_verdict_preserved"] == "V1_1_NO_GO"
    assert "RESEARCH" not in str(nogo["v1_2_diagnostic_label"]).upper()


def test_v1_2_dry_reporting_failure_reasons_explicit_when_insufficient():
    # No explicit return / p95 metrics supplied -> INSUFFICIENT_DATA edges
    df = _toy_v1_1_summary()
    out = add_v1_2_columns(df)

    # failure_reasons for v1.2 lives under v1_2_failure_reasons (collision prefix)
    assert "v1_2_failure_reasons" in out.columns
    for val in out["v1_2_failure_reasons"].astype(str):
        assert "INSUFFICIENT_DATA" in val
    # And the edge labels reflect insufficiency
    assert (out["exposure_edge_label"] == "EXPOSURE_EDGE_INSUFFICIENT_DATA").all()
    assert (out["timing_edge_label"] == "TIMING_EDGE_INSUFFICIENT_DATA").all()


# ---------------------------------------------------------------------------
# Smoke: CSV roundtrip
# ---------------------------------------------------------------------------

def test_v1_2_dry_reporting_csv_roundtrip(tmp_path):
    df = _toy_v1_1_summary()
    out = add_v1_2_columns(df)

    csv_path = tmp_path / "v1_2_dry_report.csv"
    out.to_csv(csv_path, index=False)
    reloaded = pd.read_csv(csv_path)

    # Row count survives
    assert len(reloaded) == 3

    # Preserved v1.1 verdicts survive the roundtrip
    assert list(reloaded["v1_1_verdict_preserved"]) == [
        "V1_1_NO_GO", "V1_1_INSUFFICIENT_DATA", "V1_1_RESEARCH_GO",
    ]
    # Original v1.1 verdict column survives unchanged
    assert list(reloaded["v1_1_verdict"]) == [
        "V1_1_NO_GO", "V1_1_INSUFFICIENT_DATA", "V1_1_RESEARCH_GO",
    ]

    # v1.2 diagnostic labels survive
    assert (reloaded["v1_2_diagnostic_label"] == "PORTFOLIO_DIAGNOSTIC_ONLY").all()
    assert (reloaded["protocol_version"] == "v1.2").all()
    assert (reloaded["exposure_edge_label"] == "EXPOSURE_EDGE_INSUFFICIENT_DATA").all()
    assert (reloaded["timing_edge_label"] == "TIMING_EDGE_INSUFFICIENT_DATA").all()

    # No LIVE-GO survived either
    for col in reloaded.columns:
        for val in reloaded[col].tolist():
            assert "LIVE-GO" not in str(val)


# ---------------------------------------------------------------------------
# Smoke: determinism
# ---------------------------------------------------------------------------

def test_v1_2_dry_reporting_is_deterministic():
    df = _toy_v1_1_summary()
    out1 = add_v1_2_columns(df)
    out2 = add_v1_2_columns(df)

    # Identical inputs -> identical outputs (NaN-aware)
    assert out1.equals(out2)

    # The source DataFrame was not mutated by the adapter
    assert "exposure_edge_label" not in df.columns
    assert "protocol_version" not in df.columns
