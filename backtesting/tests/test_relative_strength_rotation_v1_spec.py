"""
Contract tests for RESEARCH_SPEC_RELATIVE_STRENGTH_ROTATION_V1.md.

These tests read the spec document and assert that required content is present.
No strategy code, no backtests, no market data.
"""

import pathlib
import pytest

SPEC_PATH = (
    pathlib.Path(__file__).parent.parent
    / "RESEARCH_SPEC_RELATIVE_STRENGTH_ROTATION_V1.md"
)


@pytest.fixture(scope="module")
def spec_text():
    assert SPEC_PATH.exists(), f"Spec file not found: {SPEC_PATH}"
    return SPEC_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Section existence (all 20 sections must be present)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("section_heading", [
    "## 1. Strategy Name",
    "## 2. Research Question",
    "## 3. Why This Is A Different Family",
    "## 4. Hypothesis",
    "## 5. Universe Definition",
    "## 6. Benchmark Definition",
    "## 7. Required Data",
    "## 8. Required Features",
    "## 9. Feature Integrity Rules",
    "## 10. Ranking Logic",
    "## 11. Entry Logic",
    "## 12. Exit / Rotation Logic",
    "## 13. Position Sizing Rules",
    "## 14. Risk Controls",
    "## 15. Protocol v1.1 Evaluation",
    "## 16. Protocol v1.2 Exposure-Fair Diagnostic Evaluation",
    "## 17. Falsification Criteria",
    "## 18. Anti-Overfit Rules",
    "## 19. Forbidden Research Moves",
    "## 20. Implementation Checklist",
])
def test_section_present(spec_text, section_heading):
    assert section_heading in spec_text, f"Missing section: {section_heading!r}"


# ---------------------------------------------------------------------------
# Strategy identity — asset-selection / rotation, NOT entry-timing
# ---------------------------------------------------------------------------

def test_family_identity_asset_selection(spec_text):
    assert "asset-selection / rotation" in spec_text or "asset-selection/rotation" in spec_text


def test_family_identity_not_entry_timing(spec_text):
    # "NOT" and "entry-timing" appear on consecutive lines in the spec
    assert "NOT" in spec_text and "entry-timing" in spec_text


def test_strategy_name_present(spec_text):
    assert "RelativeStrengthRotation_v1" in spec_text


# ---------------------------------------------------------------------------
# Universe — all 15 tickers frozen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ticker", [
    "AAPL", "MSFT", "NVDA", "AMD", "META",
    "AMZN", "GOOGL", "TSLA", "NFLX", "AVGO",
    "CRM", "ORCL", "INTC", "CSCO", "IBM",
])
def test_universe_ticker_present(spec_text, ticker):
    assert ticker in spec_text, f"Universe ticker missing: {ticker}"


def test_universe_size_15(spec_text):
    assert "15 tickers" in spec_text


def test_universe_frozen_statement(spec_text):
    assert "frozen" in spec_text.lower()


def test_universe_no_fallback_clause(spec_text):
    assert "There is no fallback universe" in spec_text


def test_anti_cherry_pick_clause(spec_text):
    assert "Anti-cherry-pick" in spec_text or "anti-cherry-pick" in spec_text.lower()


# ---------------------------------------------------------------------------
# Composite score weights (frozen: 0.40 / 0.40 / 0.20)
# ---------------------------------------------------------------------------

def test_composite_weight_126d(spec_text):
    assert "0.40 * rank(relative_strength_126d)" in spec_text


def test_composite_weight_252d(spec_text):
    assert "0.40 * rank(relative_strength_252d)" in spec_text


def test_composite_weight_benchmark(spec_text):
    assert "0.20 * rank(benchmark_relative_strength)" in spec_text


def test_weights_frozen_statement(spec_text):
    assert "0.40 / 0.40 / 0.20" in spec_text


# ---------------------------------------------------------------------------
# Hard-coded thresholds (frozen)
# ---------------------------------------------------------------------------

def test_n_equals_3(spec_text):
    assert "N = 3" in spec_text


def test_hysteresis_threshold_050(spec_text):
    assert "0.50" in spec_text


def test_hysteresis_cap_at_n_statement(spec_text):
    assert "> N" in spec_text or "more than N" in spec_text


def test_volatility_threshold_008(spec_text):
    assert "<= 0.08" in spec_text or "≤ 0.08" in spec_text


def test_liquidity_threshold_1m(spec_text):
    assert "1_000_000" in spec_text or "1,000,000" in spec_text


def test_rebalance_cadence_monthly(spec_text):
    assert "monthly" in spec_text.lower()


# ---------------------------------------------------------------------------
# Hysteresis 4-step algorithm with hard cap
# ---------------------------------------------------------------------------

def test_hysteresis_4_step_algorithm(spec_text):
    assert "1. Keep all existing" in spec_text or "keep-set" in spec_text


def test_hysteresis_never_exceeds_n(spec_text):
    assert "never more than N" in spec_text


# ---------------------------------------------------------------------------
# Concentration cap default 25%
# ---------------------------------------------------------------------------

def test_concentration_cap_default_25(spec_text):
    assert "25%" in spec_text


def test_concentration_cap_default_keyword(spec_text):
    assert "Default is" in spec_text or "default 25%" in spec_text.lower() or "default is" in spec_text.lower()


# ---------------------------------------------------------------------------
# Benchmark definitions (B1, B2, B3)
# ---------------------------------------------------------------------------

def test_benchmark_b1_present(spec_text):
    assert "B1" in spec_text


def test_benchmark_b2_present(spec_text):
    assert "B2" in spec_text


def test_benchmark_b3_present(spec_text):
    assert "B3" in spec_text


def test_b1_is_primary_v11(spec_text):
    assert "Protocol v1.1 primary" in spec_text


def test_b3_is_diagnostic_only(spec_text):
    assert "diagnostic" in spec_text.lower() and "B3" in spec_text


# ---------------------------------------------------------------------------
# Core verdict labels (decision-level) — §15
# ---------------------------------------------------------------------------

def test_verdict_research_go_present(spec_text):
    assert "RESEARCH-GO" in spec_text


def test_verdict_no_go_present(spec_text):
    assert "NO-GO" in spec_text


def test_verdict_insufficient_data_present(spec_text):
    assert "INSUFFICIENT-DATA" in spec_text


def test_v1_1_verdict_labels_are_reporting_only(spec_text):
    assert "V1_1_NO_GO" in spec_text
    assert "V1_1_RESEARCH_GO" in spec_text
    assert "V1_1_INSUFFICIENT_DATA" in spec_text


def test_v1_1_labels_not_decision_level_statement(spec_text):
    assert "NOT decision-level" in spec_text or "not decision-level" in spec_text.lower()


def test_core_verdicts_are_decision_level(spec_text):
    assert "decision-level" in spec_text


# ---------------------------------------------------------------------------
# p75 / p95 separation — §15 and §16
# ---------------------------------------------------------------------------

def test_p95_comparator_present(spec_text):
    assert "p95" in spec_text


def test_p75_comparator_present(spec_text):
    assert "p75" in spec_text


def test_p75_not_p95_statement(spec_text):
    assert "p75 ≠ p95" in spec_text or "p75 is not" in spec_text.lower() or "p75 != p95" in spec_text


def test_p75_not_promoted_statement(spec_text):
    assert "not promote" in spec_text.lower() or "NOT a p95" in spec_text or "p75 is not" in spec_text.lower()


def test_hard_separation_of_p75_p95(spec_text):
    assert "Hard separation of p75 and p95" in spec_text


def test_p95_1000_simulations(spec_text):
    assert "1000" in spec_text or "1,000" in spec_text


# ---------------------------------------------------------------------------
# v1.2 diagnostic label — always PORTFOLIO_DIAGNOSTIC_ONLY
# ---------------------------------------------------------------------------

def test_portfolio_diagnostic_only_label(spec_text):
    assert "PORTFOLIO_DIAGNOSTIC_ONLY" in spec_text


def test_v1_2_never_decision_gate(spec_text):
    assert "never as a decision gate" in spec_text or "never a decision gate" in spec_text


def test_v1_2_never_overrides_v1_1(spec_text):
    assert "never overrides v1.1" in spec_text or "never override" in spec_text.lower()


# ---------------------------------------------------------------------------
# v1.2 edge labels
# ---------------------------------------------------------------------------

def test_exposure_edge_pass_label(spec_text):
    assert "EXPOSURE_EDGE_PASS" in spec_text


def test_exposure_edge_fail_label(spec_text):
    assert "EXPOSURE_EDGE_FAIL" in spec_text


def test_exposure_edge_insufficient_data_label(spec_text):
    assert "EXPOSURE_EDGE_INSUFFICIENT_DATA" in spec_text


def test_timing_edge_pass_label(spec_text):
    assert "TIMING_EDGE_PASS" in spec_text


def test_timing_edge_fail_label(spec_text):
    assert "TIMING_EDGE_FAIL" in spec_text


def test_timing_edge_insufficient_data_label(spec_text):
    assert "TIMING_EDGE_INSUFFICIENT_DATA" in spec_text


# ---------------------------------------------------------------------------
# Forbidden moves — §19
# ---------------------------------------------------------------------------

def test_no_live_go_forbidden(spec_text):
    assert "LIVE-GO" in spec_text
    assert "No `LIVE-GO`" in spec_text or "No LIVE-GO" in spec_text


def test_no_auto_adjust_true(spec_text):
    assert "auto_adjust=False" in spec_text
    assert "auto_adjust=True" in spec_text


def test_no_p75_as_p95_aliasing_forbidden(spec_text):
    assert "aliasing of p75" in spec_text.lower() or "p75 results as p95" in spec_text.lower()


def test_no_post_hoc_ticker_selection_forbidden(spec_text):
    assert "post-hoc" in spec_text.lower()


def test_no_synthetic_data_as_research_evidence(spec_text):
    assert "Synthetic data" in spec_text or "synthetic" in spec_text.lower()


def test_no_live_trading_recommendation(spec_text):
    assert "No live trading" in spec_text or "live trading recommendation" in spec_text.lower()


def test_no_research_go_from_v1_2_alone(spec_text):
    assert "v1.2 alone can never approve" in spec_text


# ---------------------------------------------------------------------------
# Falsification criteria F1–F10
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("criterion", ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10"])
def test_falsification_criterion_present(spec_text, criterion):
    assert f"{criterion} —" in spec_text or f"{criterion}:" in spec_text or criterion in spec_text


# ---------------------------------------------------------------------------
# Implementation checklist — Step 8 authorization gate
# ---------------------------------------------------------------------------

def test_step_8_research_run_requires_authorization(spec_text):
    assert "Step 8" in spec_text
    assert "explicit user authorization" in spec_text or "explicit" in spec_text


def test_step_8_not_implied_by_reaching_step(spec_text):
    assert "NOT implied by reaching this step" in spec_text


# ---------------------------------------------------------------------------
# Required data constraints
# ---------------------------------------------------------------------------

def test_auto_adjust_false_required(spec_text):
    assert "auto_adjust=False" in spec_text


def test_no_fundamental_data(spec_text):
    assert "No fundamental data" in spec_text or "no fundamentals" in spec_text.lower()


def test_no_intraday_data(spec_text):
    assert "No intraday data" in spec_text


# ---------------------------------------------------------------------------
# Anti-overfit rules
# ---------------------------------------------------------------------------

def test_no_grid_search(spec_text):
    assert "grid search" in spec_text.lower()


def test_no_parameter_tuning_after_results(spec_text):
    assert "after results" in spec_text.lower() or "after seeing results" in spec_text.lower()


# ---------------------------------------------------------------------------
# Position sizing — no leverage, no shorting, no options
# ---------------------------------------------------------------------------

def test_no_leverage(spec_text):
    assert "No leverage" in spec_text


def test_no_shorting(spec_text):
    assert "No shorting" in spec_text


def test_no_options(spec_text):
    assert "No options" in spec_text


# ---------------------------------------------------------------------------
# Required v1.2 metric source fields (all 8)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field", [
    "strategy_total_return",
    "strategy_calmar",
    "buy_hold_total_return",
    "buy_hold_calmar",
    "exposure_matched_bh_total_return",
    "exposure_matched_bh_calmar",
    "randomized_timing_p95_total_return",
    "randomized_timing_p95_calmar",
])
def test_v1_2_metric_field_present(spec_text, field):
    assert field in spec_text, f"Missing v1.2 metric field: {field}"
