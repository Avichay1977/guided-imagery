"""
Protocol v1.2 — Metric Source Integration (non-invasive extraction/mapping).

Bridges between future result objects / summary rows that may contain richer
metrics and the v1.2 reporting adapter, which needs explicit total-return and
p95 comparator fields to classify exposure / timing edges.

Diagnostic plumbing only. This module:
  - Never runs a backtest.
  - Never fetches or reads market data.
  - Never emits RESEARCH-GO or LIVE-GO.
  - Never overwrites or derives a v1.1 verdict.
  - Never aliases p75 metrics as p95 (a p75 comparator is NOT a p95 comparator).

The eight v1.2 metric fields produced here are exactly the override fields the
reporting adapter (protocol_v1_2_reporting.build_v1_2_report_row) accepts:

    strategy_total_return
    strategy_calmar
    buy_hold_total_return
    buy_hold_calmar
    exposure_matched_bh_total_return
    exposure_matched_bh_calmar
    randomized_timing_p95_total_return
    randomized_timing_p95_calmar

Anything not present in the source dict stays None and surfaces downstream as
*_INSUFFICIENT_DATA. Missing data is reported, never fabricated.
"""

from __future__ import annotations

from typing import Optional

# Canonical v1.2 metric override field names (the keys the adapter consumes).
V1_2_METRIC_FIELDS: tuple[str, ...] = (
    "strategy_total_return",
    "strategy_calmar",
    "buy_hold_total_return",
    "buy_hold_calmar",
    "exposure_matched_bh_total_return",
    "exposure_matched_bh_calmar",
    "randomized_timing_p95_total_return",
    "randomized_timing_p95_calmar",
)

# Source-key aliases per canonical field, in precedence order. The canonical
# name is always tried first, then common alternative spellings.
#
# IMPORTANT: p95 fields accept ONLY explicit p95 source keys. p75 keys are
# deliberately absent here — p75 is a different (looser) threshold and must
# never be promoted to p95.
_SOURCE_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "strategy_total_return": (
        "strategy_total_return",
        "total_return",
    ),
    "strategy_calmar": (
        "strategy_calmar",
        "calmar",
    ),
    "buy_hold_total_return": (
        "buy_hold_total_return",
        "benchmark_total_return",
    ),
    "buy_hold_calmar": (
        "buy_hold_calmar",
        "benchmark_calmar",
    ),
    "exposure_matched_bh_total_return": (
        "exposure_matched_bh_total_return",
        "exposure_matched_total_return",
    ),
    "exposure_matched_bh_calmar": (
        "exposure_matched_bh_calmar",
        "exposure_matched_calmar",
    ),
    "randomized_timing_p95_total_return": (
        "randomized_timing_p95_total_return",
    ),
    "randomized_timing_p95_calmar": (
        "randomized_timing_p95_calmar",
    ),
}

# Source keys that must NEVER be mapped into any v1.2 field. Explicitly the
# p75 comparator keys: p75 is not p95.
_FORBIDDEN_P95_ALIASES: frozenset[str] = frozenset({
    "randomized_timing_p75_total_return",
    "randomized_timing_p75_calmar",
})

# v1.1 fields that must never be overwritten by a merge.
_PROTECTED_V1_1_KEYS: tuple[str, ...] = (
    "v1_1_verdict",
    "v1_1_verdict_preserved",
    "status",
    "failure_reasons",
)


def extract_v1_2_metric_overrides(source: dict) -> dict:
    """
    Pull the eight v1.2 metric override fields out of a source dict.

    Returns a dict keyed by V1_2_METRIC_FIELDS. A field is set only when a
    recognized, non-None source key is present; otherwise it is None.

    p75 source keys are never used: a p75 comparator is not a p95 comparator,
    so p95 fields stay None unless an explicit p95 source key is present.
    """
    if source is None:
        source = {}

    overrides: dict[str, Optional[float]] = {}
    for field in V1_2_METRIC_FIELDS:
        value = None
        for alias in _SOURCE_KEY_ALIASES[field]:
            # Defensive: never honor a forbidden p75->p95 alias even if it
            # somehow appeared in the alias table.
            if alias in _FORBIDDEN_P95_ALIASES:
                continue
            if alias in source and source[alias] is not None:
                value = source[alias]
                break
        overrides[field] = value
    return overrides


def merge_v1_2_metric_overrides(summary_row: dict, overrides: dict) -> dict:
    """
    Merge extracted v1.2 metric overrides into a copy of a v1.1 summary row.

    - Returns a NEW dict; the input summary_row is not mutated.
    - Protected v1.1 keys (verdict / status / failure_reasons) are never
      overwritten, even if present in `overrides`.
    - Only non-None override values are written; None overrides are dropped so
      they never clobber an existing source value.
    """
    merged = dict(summary_row or {})
    for key, value in (overrides or {}).items():
        if key in _PROTECTED_V1_1_KEYS:
            continue
        if value is None:
            continue
        merged[key] = value
    return merged


def has_required_v1_2_metrics(row: dict) -> bool:
    """
    True only when ALL eight v1.2 metric fields are present and non-None.

    This is the condition under which both the exposure edge and the timing
    edge can be classified PASS/FAIL (rather than INSUFFICIENT_DATA).
    """
    if not row:
        return False
    for field in V1_2_METRIC_FIELDS:
        if row.get(field) is None:
            return False
    return True


def build_summary_row_with_v1_2_metrics(
    base_summary_row: dict,
    metric_sources: "list[dict] | None" = None,
) -> dict:
    """
    Return a new summary row that includes v1.2 metric source fields alongside
    existing v1.1 fields.

    Parameters
    ----------
    base_summary_row : existing v1.1 summary/split row (not mutated)
    metric_sources   : optional list of source dicts to mine for v1.2 metrics.
                       Sources are tried in order; the first non-None value for
                       each field wins.

    Returns a NEW dict that:
    - Preserves every key from base_summary_row unchanged.
    - Adds all eight V1_2_METRIC_FIELDS (None when no source supplied a value).
    - Never overwrites protected v1.1 keys (verdict / status / failure_reasons).
    - Never aliases p75 source keys to p95 metric fields.
    - Does NOT add v1.2 diagnostic labels — use the reporting adapter for that.
    - Never emits RESEARCH-GO or LIVE-GO.
    """
    combined: dict[str, Optional[float]] = {field: None for field in V1_2_METRIC_FIELDS}

    for src in (metric_sources or []):
        extracted = extract_v1_2_metric_overrides(src or {})
        for field in V1_2_METRIC_FIELDS:
            if combined[field] is None and extracted[field] is not None:
                combined[field] = extracted[field]

    # merge_v1_2_metric_overrides drops None values (to avoid clobbering
    # existing v1.1 calmar fields with None), so after the merge we must
    # re-fill any V1_2_METRIC_FIELDS that weren't provided, setting them to
    # None so callers always find a consistent key set.
    result = merge_v1_2_metric_overrides(base_summary_row, combined)
    for field in V1_2_METRIC_FIELDS:
        if field not in result:
            result[field] = None
    return result


__all__ = [
    "V1_2_METRIC_FIELDS",
    "extract_v1_2_metric_overrides",
    "merge_v1_2_metric_overrides",
    "has_required_v1_2_metrics",
    "build_summary_row_with_v1_2_metrics",
]
