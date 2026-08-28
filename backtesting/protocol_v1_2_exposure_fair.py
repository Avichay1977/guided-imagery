"""
Protocol v1.2 — Exposure-Fair Diagnostic Layer (production logic).

Diagnostic only. This module never produces a trading decision. It cannot
emit RESEARCH-GO or LIVE-GO, cannot overwrite a v1.1 verdict, and cannot
recommend capital allocation.

See PROTOCOL_V1_2_EXPOSURE_FAIR_DIAGNOSTIC.md for the contract.

All math here is deterministic; no market data is fetched or read.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Required output columns (exact order)
# ---------------------------------------------------------------------------

REQUIRED_V1_2_OUTPUT_COLUMNS = [
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
# Allowed labels
# ---------------------------------------------------------------------------

# v1.1 verdict labels (read-only, copied through; never created here)
V1_1_LABELS = [
    "V1_1_NO_GO",
    "V1_1_RESEARCH_GO",
    "V1_1_INSUFFICIENT_DATA",
]

EXPOSURE_EDGE_LABELS = [
    "EXPOSURE_EDGE_PASS",
    "EXPOSURE_EDGE_FAIL",
    "EXPOSURE_EDGE_INSUFFICIENT_DATA",
]

TIMING_EDGE_LABELS = [
    "TIMING_EDGE_PASS",
    "TIMING_EDGE_FAIL",
    "TIMING_EDGE_INSUFFICIENT_DATA",
]

PORTFOLIO_LABEL = "PORTFOLIO_DIAGNOSTIC_ONLY"

# Complete set of labels this module is permitted to OUTPUT.
# Note: RESEARCH-GO/LIVE-GO are intentionally absent. V1_1_RESEARCH_GO is a
# preserved v1.1 verdict value that may be copied through unchanged, but it is
# never *created* by this layer.
ALLOWED_OUTPUT_LABELS = (
    EXPOSURE_EDGE_LABELS
    + TIMING_EDGE_LABELS
    + [PORTFOLIO_LABEL]
)

PROTOCOL_VERSION = "v1.2"


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def _is_meaningful(value) -> bool:
    """True when value is a real, finite number (not None / NaN / inf)."""
    if value is None:
        return False
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(v)


def calculate_exposure_matched_benchmark(
    benchmark_returns: Sequence[float],
    exposure_pct: float,
    cash_return: float = 0.0,
) -> list[float]:
    """
    Blend benchmark returns down to the strategy's market-exposure fraction.

    exposure_matched_return[t] =
        benchmark_returns[t] * f + cash_return * (1 - f)
    where f = exposure_pct / 100.

    No leverage. Cash yield is zero unless explicitly passed.
    """
    if not (0.0 <= exposure_pct <= 100.0):
        raise ValueError(
            f"exposure_pct must be between 0 and 100, got {exposure_pct}"
        )

    f = exposure_pct / 100.0
    arr = np.asarray(list(benchmark_returns), dtype=float)
    if arr.size == 0:
        return []
    blended = arr * f + cash_return * (1.0 - f)
    return [float(x) for x in blended]


def total_return(returns: Sequence[float]) -> float:
    """
    Compound a series of per-period simple returns into a total return.

    total_return = prod(1 + r_t) - 1.   Empty input -> 0.0.
    """
    arr = np.asarray(list(returns), dtype=float)
    if arr.size == 0:
        return 0.0
    return float(np.prod(1.0 + arr) - 1.0)


def equity_curve(returns: Sequence[float], initial: float = 1.0) -> list[float]:
    """Cumulative equity from per-period returns (starts at `initial`)."""
    arr = np.asarray(list(returns), dtype=float)
    if arr.size == 0:
        return [float(initial)]
    eq = initial * np.cumprod(1.0 + arr)
    return [float(initial)] + [float(x) for x in eq]


def max_drawdown(returns: Sequence[float]) -> float:
    """
    Maximum drawdown as a non-negative fraction (0.20 == 20% peak-to-trough).

    Computed from the cumulative equity curve. Empty input -> 0.0.
    """
    eq = np.asarray(equity_curve(returns), dtype=float)
    if eq.size < 2:
        return 0.0
    peak = np.maximum.accumulate(eq)
    with np.errstate(divide="ignore", invalid="ignore"):
        dd = np.where(peak > 0, (peak - eq) / peak, 0.0)
    return float(np.max(dd))


def calmar_ratio(returns: Sequence[float], periods_per_year: int = 252) -> float:
    """
    Calmar = annualized return / abs(max_drawdown).

    - If max_drawdown == 0: returns inf only when annualized return > 0,
      else 0.0.
    - Empty input -> 0.0.
    """
    arr = np.asarray(list(returns), dtype=float)
    if arr.size == 0:
        return 0.0

    tr = total_return(arr)
    n = arr.size
    years = n / periods_per_year if periods_per_year > 0 else 0.0
    if years > 0:
        annualized = (1.0 + tr) ** (1.0 / years) - 1.0
    else:
        annualized = tr

    mdd = max_drawdown(arr)
    if mdd > 0:
        return float(annualized / abs(mdd))
    return float("inf") if annualized > 0 else 0.0


# ---------------------------------------------------------------------------
# Edge classification
# ---------------------------------------------------------------------------

def classify_exposure_edge(
    strategy_total_return,
    strategy_calmar,
    exposure_matched_bh_total_return,
    exposure_matched_bh_calmar,
) -> str:
    """
    EXPOSURE_EDGE_PASS only if the strategy beats the exposure-matched
    Buy & Hold on BOTH total return AND Calmar. FAIL if both metrics are
    available but either comparison fails. INSUFFICIENT_DATA if any required
    metric is missing / NaN / inf.
    """
    metrics = [
        strategy_total_return,
        strategy_calmar,
        exposure_matched_bh_total_return,
        exposure_matched_bh_calmar,
    ]
    if not all(_is_meaningful(m) for m in metrics):
        return "EXPOSURE_EDGE_INSUFFICIENT_DATA"

    beats_return = float(strategy_total_return) > float(exposure_matched_bh_total_return)
    beats_calmar = float(strategy_calmar) > float(exposure_matched_bh_calmar)
    return "EXPOSURE_EDGE_PASS" if (beats_return and beats_calmar) else "EXPOSURE_EDGE_FAIL"


def classify_timing_edge(
    strategy_total_return,
    strategy_calmar,
    randomized_timing_p95_total_return,
    randomized_timing_p95_calmar,
) -> str:
    """
    TIMING_EDGE_PASS only if the strategy exceeds the randomized p95 on BOTH
    total return AND Calmar. FAIL if both metrics are available but either
    comparison fails. INSUFFICIENT_DATA if any required metric is missing /
    NaN / inf.
    """
    metrics = [
        strategy_total_return,
        strategy_calmar,
        randomized_timing_p95_total_return,
        randomized_timing_p95_calmar,
    ]
    if not all(_is_meaningful(m) for m in metrics):
        return "TIMING_EDGE_INSUFFICIENT_DATA"

    beats_return = float(strategy_total_return) > float(randomized_timing_p95_total_return)
    beats_calmar = float(strategy_calmar) > float(randomized_timing_p95_calmar)
    return "TIMING_EDGE_PASS" if (beats_return and beats_calmar) else "TIMING_EDGE_FAIL"


# ---------------------------------------------------------------------------
# Diagnostic row builder
# ---------------------------------------------------------------------------

def build_v1_2_diagnostic_row(
    *,
    strategy_name: str,
    strategy_version: str,
    ticker: str,
    test_window: str,
    strategy_exposure_pct,
    strategy_total_return,
    strategy_calmar,
    buy_hold_total_return,
    buy_hold_calmar,
    exposure_matched_bh_total_return,
    exposure_matched_bh_calmar,
    randomized_timing_p95_total_return,
    randomized_timing_p95_calmar,
    v1_1_verdict_preserved: str,
    extra_failure_reasons: Optional[list[str]] = None,
) -> dict:
    """
    Build a single v1.2 diagnostic row with exactly REQUIRED_V1_2_OUTPUT_COLUMNS.

    - protocol_version is fixed to "v1.2".
    - v1_1_verdict_preserved is copied through unchanged.
    - v1_2_diagnostic_label is always PORTFOLIO_DIAGNOSTIC_ONLY (never a
      go/no-go decision, never RESEARCH-GO or LIVE-GO).
    """
    exposure_label = classify_exposure_edge(
        strategy_total_return,
        strategy_calmar,
        exposure_matched_bh_total_return,
        exposure_matched_bh_calmar,
    )
    timing_label = classify_timing_edge(
        strategy_total_return,
        strategy_calmar,
        randomized_timing_p95_total_return,
        randomized_timing_p95_calmar,
    )

    failure_reasons: list[str] = list(extra_failure_reasons or [])
    if exposure_label == "EXPOSURE_EDGE_FAIL":
        failure_reasons.append("EXPOSURE_EDGE_FAIL")
    elif exposure_label == "EXPOSURE_EDGE_INSUFFICIENT_DATA":
        failure_reasons.append("EXPOSURE_EDGE_INSUFFICIENT_DATA")
    if timing_label == "TIMING_EDGE_FAIL":
        failure_reasons.append("TIMING_EDGE_FAIL")
    elif timing_label == "TIMING_EDGE_INSUFFICIENT_DATA":
        failure_reasons.append("TIMING_EDGE_INSUFFICIENT_DATA")

    row = {
        "strategy_name": strategy_name,
        "strategy_version": strategy_version,
        "protocol_version": PROTOCOL_VERSION,
        "ticker": ticker,
        "test_window": test_window,
        "strategy_exposure_pct": strategy_exposure_pct,
        "strategy_total_return": strategy_total_return,
        "strategy_calmar": strategy_calmar,
        "buy_hold_total_return": buy_hold_total_return,
        "buy_hold_calmar": buy_hold_calmar,
        "exposure_matched_bh_total_return": exposure_matched_bh_total_return,
        "exposure_matched_bh_calmar": exposure_matched_bh_calmar,
        "randomized_timing_p95_total_return": randomized_timing_p95_total_return,
        "randomized_timing_p95_calmar": randomized_timing_p95_calmar,
        "exposure_edge_label": exposure_label,
        "timing_edge_label": timing_label,
        "v1_1_verdict_preserved": v1_1_verdict_preserved,
        "v1_2_diagnostic_label": PORTFOLIO_LABEL,
        "failure_reasons": "; ".join(failure_reasons),
    }

    # Hard guarantee: never emit RESEARCH-GO / LIVE-GO as a v1.2 decision.
    assert row["v1_2_diagnostic_label"] == PORTFOLIO_LABEL
    assert row["v1_2_diagnostic_label"] not in ("RESEARCH-GO", "LIVE-GO")
    return row
