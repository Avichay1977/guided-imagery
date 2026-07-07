"""
Unit tests for RelativeStrengthRotation_v1 scaffold.

Uses deterministic toy dicts only.
No market data. No backtests. No runner execution.
"""

import math
import subprocess
import sys

import pytest

from strategy_variants import (
    BreakoutVolumeConfluence_v1,
    MomentumContinuationConfluence_v1,
    RelativeStrengthRotation_v1,
    TrendPullbackConfluence_v1,
    get_variant,
)


# ---------------------------------------------------------------------------
# Shared toy row helpers
# ---------------------------------------------------------------------------

def _valid_row() -> dict:
    return {
        "relative_strength_126d": 1.10,
        "relative_strength_252d": 1.05,
        "benchmark_relative_strength": 1.02,
    }


def _variant() -> RelativeStrengthRotation_v1:
    return RelativeStrengthRotation_v1()


# ---------------------------------------------------------------------------
# 1. Class existence and registry
# ---------------------------------------------------------------------------

def test_strategy_class_exists():
    v = _variant()
    assert v is not None


def test_strategy_class_in_registry():
    v = get_variant("RelativeStrengthRotation_v1")
    assert isinstance(v, RelativeStrengthRotation_v1)


# ---------------------------------------------------------------------------
# 2. Identity
# ---------------------------------------------------------------------------

def test_strategy_id_is_relative_strength_rotation_v1():
    v = _variant()
    assert v.STRATEGY_ID == "RelativeStrengthRotation_v1"


def test_strategy_family_is_rotation_not_entry_timing():
    v = _variant()
    family = v.STRATEGY_FAMILY.lower()
    assert "rotation" in family
    assert "entry-timing" not in family
    assert "asset-selection" in family


# ---------------------------------------------------------------------------
# 3. Universe
# ---------------------------------------------------------------------------

def test_fixed_universe_has_exactly_15_tickers():
    v = _variant()
    assert len(v.UNIVERSE) == 15


def test_fixed_universe_matches_spec_order():
    v = _variant()
    expected = [
        "AAPL", "MSFT", "NVDA", "AMD", "META",
        "AMZN", "GOOGL", "TSLA", "NFLX", "AVGO",
        "CRM", "ORCL", "INTC", "CSCO", "IBM",
    ]
    assert v.UNIVERSE == expected


# ---------------------------------------------------------------------------
# 4. Frozen parameters
# ---------------------------------------------------------------------------

def test_top_n_is_3():
    assert _variant().TOP_N == 3


def test_rebalance_frequency_is_monthly():
    assert _variant().REBALANCE_FREQUENCY == "monthly"


def test_ranking_weights_are_40_40_20():
    v = _variant()
    assert v.WEIGHT_RS_126D == pytest.approx(0.40)
    assert v.WEIGHT_RS_252D == pytest.approx(0.40)
    assert v.WEIGHT_BENCHMARK_RS == pytest.approx(0.20)


def test_weight_sum_equals_1():
    v = _variant()
    total = v.WEIGHT_RS_126D + v.WEIGHT_RS_252D + v.WEIGHT_BENCHMARK_RS
    assert total == pytest.approx(1.0)


def test_hysteresis_threshold_is_050():
    assert _variant().HYSTERESIS_THRESHOLD == pytest.approx(0.50)


def test_volatility_threshold_is_008():
    assert _variant().VOLATILITY_ATR_PCT_MAX == pytest.approx(0.08)


def test_liquidity_threshold_is_1000000():
    assert _variant().LIQUIDITY_VOLUME_AVG_20_MIN == 1_000_000


# ---------------------------------------------------------------------------
# 5. Required features
# ---------------------------------------------------------------------------

def test_required_features_include_all_rs_fields():
    feats = _variant().required_features
    for f in ("relative_strength_63d", "relative_strength_126d",
              "relative_strength_252d", "benchmark_relative_strength"):
        assert f in feats, f"Missing required feature: {f}"


def test_required_features_include_filters():
    feats = _variant().required_features
    for f in ("trend_filter_ema200", "volatility_filter_atr_pct",
              "liquidity_filter_volume_avg_20", "rank_percentile"):
        assert f in feats, f"Missing required feature: {f}"


# ---------------------------------------------------------------------------
# 6. calculate_score — correct computation
# ---------------------------------------------------------------------------

def test_calculate_score_uses_fixed_weights():
    v = _variant()
    row = _valid_row()
    expected = 0.40 * 1.10 + 0.40 * 1.05 + 0.20 * 1.02
    result = v.calculate_score(row)
    assert result == pytest.approx(expected)


def test_calculate_score_is_deterministic():
    v = _variant()
    row = _valid_row()
    assert v.calculate_score(row) == v.calculate_score(row)


def test_calculate_score_with_equal_values():
    v = _variant()
    row = {"relative_strength_126d": 1.0,
           "relative_strength_252d": 1.0,
           "benchmark_relative_strength": 1.0}
    assert v.calculate_score(row) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 7. calculate_score — rejection of invalid inputs
# ---------------------------------------------------------------------------

def test_calculate_score_rejects_nan():
    v = _variant()
    row = _valid_row()
    row["relative_strength_126d"] = float("nan")
    assert v.calculate_score(row) is None


def test_calculate_score_rejects_inf():
    v = _variant()
    row = _valid_row()
    row["relative_strength_252d"] = float("inf")
    assert v.calculate_score(row) is None


def test_calculate_score_rejects_neg_inf():
    v = _variant()
    row = _valid_row()
    row["benchmark_relative_strength"] = float("-inf")
    assert v.calculate_score(row) is None


def test_calculate_score_rejects_none():
    v = _variant()
    row = _valid_row()
    row["relative_strength_126d"] = None
    assert v.calculate_score(row) is None


def test_calculate_score_rejects_missing_field():
    v = _variant()
    row = {"relative_strength_126d": 1.10}  # missing 252d and benchmark
    assert v.calculate_score(row) is None


def test_calculate_score_rejects_all_fields_missing():
    v = _variant()
    assert v.calculate_score({}) is None


# ---------------------------------------------------------------------------
# 8. generate_signal — must raise NotImplementedError (no Backtester support)
# ---------------------------------------------------------------------------

def test_generate_signal_raises_not_implemented():
    import pandas as pd
    v = _variant()
    df = pd.DataFrame({"close": [100.0, 101.0]})
    with pytest.raises(NotImplementedError):
        v.generate_signal(df)


# ---------------------------------------------------------------------------
# 9. describe() contract
# ---------------------------------------------------------------------------

def test_describe_contains_no_live_go():
    d = _variant().describe()
    text = str(d).lower()
    assert "live-go" not in text
    assert "live_go" not in text


def test_describe_contains_no_research_go():
    d = _variant().describe()
    text = str(d).lower()
    assert "research-go" not in text
    assert "research_go" not in text


def test_describe_declares_long_only_no_leverage():
    d = _variant().describe()
    assert d.get("long_only") is True
    assert d.get("leverage") is False
    assert d.get("shorting") is False
    assert d.get("options") is False


def test_describe_contains_strategy_id():
    d = _variant().describe()
    assert d.get("strategy_id") == "RelativeStrengthRotation_v1"


def test_describe_contains_family():
    d = _variant().describe()
    assert "rotation" in str(d.get("family", "")).lower()


def test_describe_contains_universe_size_15():
    d = _variant().describe()
    assert d.get("universe_size") == 15


def test_describe_contains_weights():
    d = _variant().describe()
    weights = d.get("weights", {})
    assert weights.get("relative_strength_126d") == pytest.approx(0.40)
    assert weights.get("relative_strength_252d") == pytest.approx(0.40)
    assert weights.get("benchmark_relative_strength") == pytest.approx(0.20)


def test_describe_live_execution_false():
    d = _variant().describe()
    assert d.get("live_execution") is False


def test_describe_status_is_scaffold_only():
    d = _variant().describe()
    assert "SCAFFOLD" in str(d.get("status", "")).upper()


# ---------------------------------------------------------------------------
# 10. No Backtester import required for scaffold
# ---------------------------------------------------------------------------

def test_no_backtester_import_required_for_scaffold():
    # Import strategy_variants without importing backtester — must not raise
    import importlib
    import strategy_variants as sv
    v = sv.RelativeStrengthRotation_v1()
    assert v.STRATEGY_ID == "RelativeStrengthRotation_v1"


# ---------------------------------------------------------------------------
# 11. Existing archived variants not modified
# ---------------------------------------------------------------------------

def test_existing_archived_variants_not_modified():
    b = BreakoutVolumeConfluence_v1()
    t = TrendPullbackConfluence_v1()
    m = MomentumContinuationConfluence_v1()
    assert b.strategy_name == "BreakoutVolumeConfluence"
    assert t.strategy_name == "TrendPullbackConfluence"
    assert m.strategy_name == "MomentumContinuationConfluence"


def test_registry_contains_all_four_variants():
    from strategy_variants import REGISTRY
    assert "BreakoutVolumeConfluence_v1" in REGISTRY
    assert "TrendPullbackConfluence_v1" in REGISTRY
    assert "MomentumContinuationConfluence_v1" in REGISTRY
    assert "RelativeStrengthRotation_v1" in REGISTRY


# ---------------------------------------------------------------------------
# 12. Spec contract tests still pass (subprocess guard)
# ---------------------------------------------------------------------------

def test_spec_contract_tests_still_pass():
    result = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/test_relative_strength_rotation_v1_spec.py", "-q", "--tb=short"],
        capture_output=True,
        text=True,
        cwd=str(__import__("pathlib").Path(__file__).parent.parent),
    )
    assert result.returncode == 0, (
        f"Spec contract tests failed:\n{result.stdout}\n{result.stderr}"
    )
