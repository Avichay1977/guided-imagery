"""
Rotation v1.2 metric-source adapter.

Converts RelativeStrengthRotation_v1 result objects into the eight Protocol
v1.2 metric-source fields consumed by the reporting adapter.

Note on "randomized_timing_p95" naming: the v1.2 generic field names use
"timing" because the original protocol infrastructure targeted entry-timing
strategies. For rotation, the randomized_timing_p95_* fields hold the
randomized-SELECTION p95 comparator values — same significance threshold
(95th percentile), different comparator purpose.

This module:
  - Never runs a backtest.
  - Never fetches or reads market data.
  - Never emits live or research verdict tokens.
  - Never derives or overwrites a v1.1 verdict.
  - Never maps p75 comparator results to p95 fields.
  - Never aliases B1 as B2 or B2 as B1.
  - Never mutates input objects.
  - Never fabricates values for missing sources.
"""

from __future__ import annotations

import math
from typing import Any, Optional

from protocol_v1_2_metric_sources import (
    V1_2_METRIC_FIELDS,
    build_summary_row_with_v1_2_metrics,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> Optional[float]:
    """
    Return a finite float or None.

    None, NaN, inf, non-numeric are all coerced to None so they can never
    silently propagate into a v1.2 metric field.
    """
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


# ---------------------------------------------------------------------------
# Core adapter
# ---------------------------------------------------------------------------

def build_rotation_v1_2_metric_sources(
    strategy_result,
    b1_buy_hold_result=None,
    b2_equal_weight_result=None,
    random_selection_result=None,
) -> dict:
    """
    Extract the eight v1.2 metric source fields from rotation result objects.

    Mapping (one-to-one, no cross-aliasing):
      strategy_total_return                <- strategy_result.strategy_total_return
      strategy_calmar                      <- strategy_result.strategy_calmar
      buy_hold_total_return                <- b1_buy_hold_result.total_return
      buy_hold_calmar                      <- b1_buy_hold_result.calmar
      exposure_matched_bh_total_return     <- b2_equal_weight_result.total_return
      exposure_matched_bh_calmar           <- b2_equal_weight_result.calmar
      randomized_timing_p95_total_return   <- random_selection_result.p95_total_return
      randomized_timing_p95_calmar         <- random_selection_result.p95_calmar

    Missing or invalid (NaN/inf) metrics become None. No value is fabricated.
    Returns a dict keyed by all eight V1_2_METRIC_FIELDS.
    """
    raw: dict[str, Optional[float]] = {}

    # Strategy metrics
    if strategy_result is not None:
        raw["strategy_total_return"] = _safe_float(
            getattr(strategy_result, "strategy_total_return", None)
        )
        raw["strategy_calmar"] = _safe_float(
            getattr(strategy_result, "strategy_calmar", None)
        )

    # B1: raw buy-and-hold benchmark (not the equal-weight B2)
    if b1_buy_hold_result is not None:
        raw["buy_hold_total_return"] = _safe_float(
            getattr(b1_buy_hold_result, "total_return", None)
        )
        raw["buy_hold_calmar"] = _safe_float(
            getattr(b1_buy_hold_result, "calmar", None)
        )

    # B2: monthly equal-weight universe benchmark (exposure-matched)
    if b2_equal_weight_result is not None:
        raw["exposure_matched_bh_total_return"] = _safe_float(
            getattr(b2_equal_weight_result, "total_return", None)
        )
        raw["exposure_matched_bh_calmar"] = _safe_float(
            getattr(b2_equal_weight_result, "calmar", None)
        )

    # Randomized-selection p95 comparator
    if random_selection_result is not None:
        raw["randomized_timing_p95_total_return"] = _safe_float(
            getattr(random_selection_result, "p95_total_return", None)
        )
        raw["randomized_timing_p95_calmar"] = _safe_float(
            getattr(random_selection_result, "p95_calmar", None)
        )

    # Guarantee all eight keys are present; fill missing with None
    return {field: raw.get(field, None) for field in V1_2_METRIC_FIELDS}


# ---------------------------------------------------------------------------
# Summary-row builder
# ---------------------------------------------------------------------------

def build_rotation_summary_row_with_v1_2_metrics(
    base_row: dict,
    strategy_result,
    b1_buy_hold_result=None,
    b2_equal_weight_result=None,
    random_selection_result=None,
) -> dict:
    """
    Build a v1.2-enriched summary row from a v1.1 base row and rotation results.

    - Uses build_rotation_v1_2_metric_sources() to extract the eight fields.
    - Uses build_summary_row_with_v1_2_metrics() from protocol_v1_2_metric_sources
      to merge them into a copy of base_row.
    - Preserves v1.1 fields: status, final_research_verdict, failure_reasons,
      v1_1_verdict (none of these are overwritten).
    - Returns a NEW dict; inputs are not mutated.
    - Does not add v1.2 diagnostic labels (that is the reporting adapter's job).
    """
    metric_sources = build_rotation_v1_2_metric_sources(
        strategy_result,
        b1_buy_hold_result=b1_buy_hold_result,
        b2_equal_weight_result=b2_equal_weight_result,
        random_selection_result=random_selection_result,
    )
    return build_summary_row_with_v1_2_metrics(base_row, [metric_sources])


# ---------------------------------------------------------------------------
# Completeness check + diagnostics
# ---------------------------------------------------------------------------

def rotation_metric_sources_are_complete(metric_sources: dict) -> bool:
    """
    True only when all eight V1_2_METRIC_FIELDS are present and finite numeric.

    False when any field is missing, None, NaN, or infinite.
    """
    if not metric_sources:
        return False
    for field in V1_2_METRIC_FIELDS:
        value = metric_sources.get(field)
        if value is None:
            return False
        try:
            f = float(value)
        except (TypeError, ValueError):
            return False
        if math.isnan(f) or math.isinf(f):
            return False
    return True


def explain_missing_rotation_v1_2_metrics(metric_sources: dict) -> list[str]:
    """
    Return one reason string per invalid or missing v1.2 metric field.

    Output order follows V1_2_METRIC_FIELDS (canonical, deterministic).
    Field names are mentioned verbatim so callers can match them exactly.
    """
    src = metric_sources or {}
    reasons: list[str] = []
    for field in V1_2_METRIC_FIELDS:
        value = src.get(field)
        if value is None:
            reasons.append(f"Field '{field}' is missing or None.")
            continue
        try:
            f = float(value)
        except (TypeError, ValueError):
            reasons.append(f"Field '{field}' is not numeric: {value!r}.")
            continue
        if math.isnan(f):
            reasons.append(f"Field '{field}' is NaN.")
        elif math.isinf(f):
            reasons.append(f"Field '{field}' is infinite.")
    return reasons


__all__ = [
    "build_rotation_v1_2_metric_sources",
    "build_rotation_summary_row_with_v1_2_metrics",
    "rotation_metric_sources_are_complete",
    "explain_missing_rotation_v1_2_metrics",
]
