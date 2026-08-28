"""
Protocol v1.2 contract tests.

These are DOCUMENT contract tests. They verify that
PROTOCOL_V1_2_EXPOSURE_FAIR_DIAGNOSTIC.md declares the required guarantees,
labels, columns, and prohibitions. They do NOT import production v1.2 logic
(none exists yet), do NOT run backtests, and do NOT use market data.
"""

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Locate the protocol document
# ---------------------------------------------------------------------------

DOC_NAME = "PROTOCOL_V1_2_EXPOSURE_FAIR_DIAGNOSTIC.md"


def _find_doc() -> Path:
    """
    Locate the protocol document robustly. It lives alongside the backtesting
    package; we also check the repository root as a fallback.
    """
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent / DOC_NAME,        # backtesting/
        here.parent.parent.parent / DOC_NAME,  # repo root
        here.parent / DOC_NAME,                # tests/
    ]
    for c in candidates:
        if c.exists():
            return c
    # Fall back to the first candidate for a clear failure message
    return candidates[0]


DOC_PATH = _find_doc()


@pytest.fixture(scope="module")
def doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def doc_lower(doc_text) -> str:
    return doc_text.lower()


# Required labels (case-sensitive, must appear verbatim)
REQUIRED_LABELS = [
    "V1_1_NO_GO",
    "V1_1_RESEARCH_GO",
    "V1_1_INSUFFICIENT_DATA",
    "EXPOSURE_EDGE_PASS",
    "EXPOSURE_EDGE_FAIL",
    "EXPOSURE_EDGE_INSUFFICIENT_DATA",
    "TIMING_EDGE_PASS",
    "TIMING_EDGE_FAIL",
    "TIMING_EDGE_INSUFFICIENT_DATA",
    "PORTFOLIO_DIAGNOSTIC_ONLY",
]

# Required output columns (case-sensitive, must appear verbatim)
REQUIRED_COLUMNS = [
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


# ---------------------------------------------------------------------------
# 1. Document exists
# ---------------------------------------------------------------------------

def test_protocol_v1_2_doc_exists():
    assert DOC_PATH.exists(), f"Protocol doc not found at {DOC_PATH}"
    assert DOC_PATH.stat().st_size > 0, "Protocol doc is empty"


# ---------------------------------------------------------------------------
# 2. Declares diagnostic-only
# ---------------------------------------------------------------------------

def test_v1_2_doc_declares_diagnostic_only(doc_lower):
    assert "diagnostic layer" in doc_lower
    assert "not a gate replacement" in doc_lower
    assert "diagnostic first" in doc_lower or "diagnostic-first" in doc_lower or "emits diagnostics" in doc_lower


# ---------------------------------------------------------------------------
# 3. Does not overwrite v1.1 verdicts
# ---------------------------------------------------------------------------

def test_v1_2_doc_does_not_overwrite_v1_1_verdicts(doc_lower):
    assert "overwrite" in doc_lower
    # Must state it does not overwrite/delete/alter v1.1 verdicts
    assert ("does **not** overwrite" in doc_lower) or ("does not overwrite" in doc_lower)
    assert "v1.1 verdict" in doc_lower
    assert "read-only" in doc_lower


# ---------------------------------------------------------------------------
# 4. Forbids LIVE-GO (only as forbidden, never as an allowed verdict)
# ---------------------------------------------------------------------------

def test_v1_2_doc_forbids_live_go(doc_text):
    assert "LIVE-GO" in doc_text, "LIVE-GO must be mentioned as forbidden"
    # Every line that mentions LIVE-GO must also forbid it.
    forbidding_tokens = ("not", "never", "forbid", "cannot", "without")
    for line in doc_text.splitlines():
        if "LIVE-GO" in line:
            low = line.lower()
            assert any(tok in low for tok in forbidding_tokens), (
                f"LIVE-GO appears without forbidding language: {line!r}"
            )
    # LIVE-GO must NOT appear inside the v1.2 diagnostic labels list
    assert "LIVE-GO" not in _labels_section(doc_text), (
        "LIVE-GO must not be listed as a v1.2 label"
    )


# ---------------------------------------------------------------------------
# 5. Forbids capital-allocation recommendation
# ---------------------------------------------------------------------------

def test_v1_2_doc_forbids_capital_allocation(doc_lower):
    assert "capital allocation" in doc_lower
    assert ("not recommend" in doc_lower) or ("does **not** recommend" in doc_lower) \
        or ("cannot recommend" in doc_lower)


# ---------------------------------------------------------------------------
# 6. Forbids claiming profitability
# ---------------------------------------------------------------------------

def test_v1_2_doc_forbids_claiming_profitability(doc_lower):
    assert "profitability" in doc_lower
    assert ("not claim profitability" in doc_lower) or ("claim profitability" in doc_lower)
    # Ensure it's a prohibition, not an assertion of profitability
    assert "does **not** claim profitability" in doc_lower or "not claim profitability" in doc_lower


# ---------------------------------------------------------------------------
# 7. Requires BOTH raw BH and exposure-matched BH
# ---------------------------------------------------------------------------

def test_v1_2_doc_requires_raw_bh_and_exposure_matched_bh(doc_lower):
    assert "raw" in doc_lower
    assert "exposure-matched buy & hold" in doc_lower
    assert "never only one" in doc_lower


# ---------------------------------------------------------------------------
# 8. Exposure-matched benchmark requires same window/universe/exposure/capital
# ---------------------------------------------------------------------------

def test_exposure_matched_benchmark_requires_same_window_universe_exposure_capital(doc_lower):
    assert "same test window" in doc_lower
    assert "same ticker / universe" in doc_lower or "same ticker/universe" in doc_lower
    assert "same exposure percentage" in doc_lower
    assert "same starting capital" in doc_lower


# ---------------------------------------------------------------------------
# 9. Cash return defaults to zero
# ---------------------------------------------------------------------------

def test_exposure_matched_benchmark_cash_return_defaults_to_zero(doc_lower):
    assert "cash return assumed zero" in doc_lower
    assert "unless explicitly configured" in doc_lower


# ---------------------------------------------------------------------------
# 10. Random timing requires >= 1000 simulations
# ---------------------------------------------------------------------------

def test_exposure_matched_random_requires_1000_simulations(doc_lower):
    assert "1000" in doc_lower
    assert ("minimum of 1000" in doc_lower) or ("1000 randomized simulations" in doc_lower) \
        or ("min_simulations=1000" in doc_lower)


# ---------------------------------------------------------------------------
# 11. Random timing requires same trade count / holding / window / universe
# ---------------------------------------------------------------------------

def test_exposure_matched_random_requires_same_trade_count_holding_periods_window_universe(doc_lower):
    assert "same trade count" in doc_lower
    assert "same holding periods" in doc_lower
    assert "same test window" in doc_lower
    assert "same ticker / universe" in doc_lower or "same ticker/universe" in doc_lower


# ---------------------------------------------------------------------------
# 12. Random timing compares Calmar and total return
# ---------------------------------------------------------------------------

def test_exposure_matched_random_compares_calmar_and_total_return(doc_lower):
    assert "calmar ratio" in doc_lower
    assert "total return" in doc_lower


# ---------------------------------------------------------------------------
# 13. Default threshold is p95
# ---------------------------------------------------------------------------

def test_exposure_matched_random_default_threshold_is_p95(doc_lower):
    assert "p95" in doc_lower
    assert ("default threshold of p95" in doc_lower) or ("default threshold" in doc_lower and "p95" in doc_lower)


# ---------------------------------------------------------------------------
# 14. Required output columns all present
# ---------------------------------------------------------------------------

def test_v1_2_required_output_columns(doc_text):
    missing = [c for c in REQUIRED_COLUMNS if c not in doc_text]
    assert not missing, f"Missing required output columns: {missing}"


# ---------------------------------------------------------------------------
# 15. Required labels all present
# ---------------------------------------------------------------------------

def test_v1_2_required_labels(doc_text):
    missing = [lab for lab in REQUIRED_LABELS if lab not in doc_text]
    assert not missing, f"Missing required labels: {missing}"


# ---------------------------------------------------------------------------
# 16. Side-by-side reporting preserves v1.1 verdict (read-only)
# ---------------------------------------------------------------------------

def test_v1_2_side_by_side_reporting_preserves_v1_1_verdict(doc_text, doc_lower):
    assert "v1_1_verdict_preserved" in doc_text
    assert "side" in doc_lower and "side" in doc_lower  # "side by side" / "side-by-side"
    assert ("side by side" in doc_lower) or ("side-by-side" in doc_lower)
    assert "read-only" in doc_lower
    assert "no (read-only)" in doc_lower


# ---------------------------------------------------------------------------
# 17. EXPOSURE_EDGE_PASS does not imply RESEARCH-GO
# ---------------------------------------------------------------------------

def test_exposure_edge_pass_does_not_imply_research_go(doc_text, doc_lower):
    assert "EXPOSURE_EDGE_PASS" in doc_text
    assert "V1_1_NO_GO" in doc_text
    # Doc must explicitly state the pass does NOT promote the v1.1 verdict
    assert ("does **not** promote" in doc_lower) or ("not promote the v1.1 verdict" in doc_lower) \
        or ("does not promote" in doc_lower)
    # And that v1.2 cannot convert a NO-GO into RESEARCH-GO
    assert ("convert any no-go into research-go" in doc_lower) or \
        ("convert any no-go" in doc_lower)


# ---------------------------------------------------------------------------
# 18. PORTFOLIO_DIAGNOSTIC_ONLY label exists
# ---------------------------------------------------------------------------

def test_portfolio_diagnostic_only_label_exists(doc_text):
    assert "PORTFOLIO_DIAGNOSTIC_ONLY" in doc_text


# ---------------------------------------------------------------------------
# 19. Forbids winner-picking
# ---------------------------------------------------------------------------

def test_v1_2_forbids_winner_picking(doc_lower):
    assert (
        "select tickers based on which performed well" in doc_lower
        or "no post-hoc ticker selection" in doc_lower
        or "only winning tickers" in doc_lower
    )


# ---------------------------------------------------------------------------
# 20. Forbids threshold changes after results
# ---------------------------------------------------------------------------

def test_v1_2_forbids_threshold_changes_after_results(doc_lower):
    assert (
        "thresholds after results" in doc_lower
        or "change its own thresholds after results" in doc_lower
        or "thresholds were changed after results" in doc_lower
        or "fixed thresholds, set before results" in doc_lower
    )


# ---------------------------------------------------------------------------
# 21. Forbids synthetic data as research evidence
# ---------------------------------------------------------------------------

def test_v1_2_forbids_synthetic_data_as_research_evidence(doc_lower):
    assert "synthetic" in doc_lower
    assert (
        "synthetic market data as research evidence" in doc_lower
        or "never as research evidence" in doc_lower
        or "never as a research result" in doc_lower
    )


# ---------------------------------------------------------------------------
# 22. Forbids "easier" / "will save" language (as an affirmative claim)
# ---------------------------------------------------------------------------

def test_v1_2_doc_forbids_easier_or_will_save_language(doc_text):
    # The prohibition itself must be stated.
    low = doc_text.lower()
    assert (
        "not assumed to be easier or harder" in low
        or "assumed neither easier nor harder" in low
        or "not assumed to save or reject" in low
    )

    # "easier" / "save" / "rescue" may appear ONLY inside a negation/prohibition.
    # This implements the required nuance: forbidden-as-claim vs forbidden-as-
    # prohibited. Any occurrence on a line lacking negation is an affirmative
    # claim and fails.
    sensitive_terms = ["easier", "will save", "saves ", "rescue"]
    negation_tokens = ("not", "never", "neither", "cannot", "no ", "without")

    offending: list[str] = []
    for line in doc_text.splitlines():
        low_line = line.lower()
        for term in sensitive_terms:
            if term in low_line and not any(tok in low_line for tok in negation_tokens):
                offending.append(line.strip())
                break

    assert not offending, (
        f"Sensitive language appears as an affirmative claim (no negation on line): {offending}"
    )


# ---------------------------------------------------------------------------
# 23. Failure conditions are defined
# ---------------------------------------------------------------------------

def test_v1_2_failure_conditions_are_defined(doc_lower):
    assert "failure conditions" in doc_lower
    assert "insufficient_data" in doc_lower
    assert "invalid" in doc_lower


# ---------------------------------------------------------------------------
# 24. Anti-overfit constraints are defined
# ---------------------------------------------------------------------------

def test_v1_2_anti_overfit_constraints_are_defined(doc_lower):
    assert "anti-overfit" in doc_lower
    assert "fixed thresholds" in doc_lower
    assert "pre-specified universe" in doc_lower


# ---------------------------------------------------------------------------
# 25. Implementation checklist exists
# ---------------------------------------------------------------------------

def test_v1_2_implementation_checklist_exists(doc_lower):
    assert "implementation checklist" in doc_lower
    assert "exposurefairconfig" in doc_lower


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _labels_section(doc_text: str) -> str:
    """Return the text of the Pass / Fail Labels section (§9)."""
    lines = doc_text.splitlines()
    start = end = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## 9."):
            start = i
        elif start is not None and line.strip().startswith("## 10."):
            end = i
            break
    if start is None:
        return ""
    return "\n".join(lines[start: end if end is not None else len(lines)])
