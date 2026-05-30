"""
Protocol v1.2 — Reporting Integration (side-by-side adapter).

Non-invasive adapter that appends v1.2 Exposure-Fair diagnostic columns next
to existing v1.1 result rows WITHOUT mutating, renaming, or removing any v1.1
field. v1.1 verdicts remain preserved and read-only.

Diagnostic only. This layer never emits RESEARCH-GO or LIVE-GO and never
converts a v1.1 NO-GO into an approval.

No market data is read or fetched here. All inputs are plain rows / DataFrames
that the caller already produced.

------------------------------------------------------------------------------
Column mapping (v1.2 metric  <-  v1.1 source column)
------------------------------------------------------------------------------
The existing walk-forward / strategy-lab rows expose Calmar-based fields and a
p75 randomized comparator, but NOT total-return fields and NOT a p95 comparator.
We therefore map only what genuinely exists; metrics the v1.1 runner does not
produce are left as None and surface as *_INSUFFICIENT_DATA in v1.2. Callers
that have richer metrics can supply them via explicit overrides.

    strategy_calmar                 <- "test_calmar"
    exposure_matched_bh_calmar      <- "test_exposure_matched_calmar"
    buy_hold_calmar                 <- "test_benchmark_calmar"
    (total returns)                 <- not present in v1.1 rows -> None
    (randomized p95 metrics)        <- not present in v1.1 rows -> None
                                       (v1.1 uses p75, a different threshold)
------------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Optional

from protocol_v1_2_exposure_fair import (
    REQUIRED_V1_2_OUTPUT_COLUMNS,
    V1_1_LABELS,
    build_v1_2_diagnostic_row,
)


# Default mapping: v1.2 metric name -> v1.1 source column name.
# Only metrics the v1.1 runner actually emits are mapped here.
DEFAULT_METRIC_MAPPING: dict[str, str] = {
    "strategy_calmar": "test_calmar",
    "buy_hold_calmar": "test_benchmark_calmar",
    "exposure_matched_bh_calmar": "test_exposure_matched_calmar",
}

# v1.2 metrics that the current v1.1 runner does NOT produce. Listed for
# documentation; they remain None unless supplied via explicit overrides.
UNMAPPED_V1_2_METRICS: tuple[str, ...] = (
    "strategy_total_return",
    "buy_hold_total_return",
    "exposure_matched_bh_total_return",
    "randomized_timing_p95_total_return",
    "randomized_timing_p95_calmar",
)


def normalize_v1_1_verdict(v1_1_row: dict) -> str:
    """
    Determine the preserved v1.1 verdict for a row, read-only.

    Precedence:
      1. An explicit 'v1_1_verdict' or 'v1_1_verdict_preserved' field, passed
         through verbatim (assumed already one of the V1_1_* labels).
      2. Otherwise derived conservatively from 'status':
         - status == "OK"                     -> V1_1_NO_GO  (family verdict
           under v1.1 is NO-GO; per-row OK never means a research approval)
         - any other / missing status         -> V1_1_INSUFFICIENT_DATA
    """
    for key in ("v1_1_verdict_preserved", "v1_1_verdict"):
        if key in v1_1_row and v1_1_row[key] is not None:
            return str(v1_1_row[key])

    status = str(v1_1_row.get("status", "")).upper()
    if status == "OK":
        return "V1_1_NO_GO"
    return "V1_1_INSUFFICIENT_DATA"


def build_v1_2_report_row(
    v1_1_row: dict,
    *,
    strategy_name: Optional[str] = None,
    strategy_version: Optional[str] = None,
    ticker: Optional[str] = None,
    test_window: Optional[str] = None,
    strategy_exposure_pct=None,
    metric_mapping: Optional[dict[str, str]] = None,
    **metric_overrides,
) -> dict:
    """
    Build a side-by-side v1.2 diagnostic row from a v1.1 result row.

    The v1.1 row is never mutated. The returned dict contains exactly
    REQUIRED_V1_2_OUTPUT_COLUMNS. Any v1.2 metric not present in the v1.1 row
    (and not supplied via **metric_overrides) is None and surfaces as
    *_INSUFFICIENT_DATA.

    Explicit keyword overrides (e.g. randomized_timing_p95_calmar=...) take
    precedence over the mapped v1.1 values, allowing a richer caller to supply
    full metrics.
    """
    mapping = metric_mapping or DEFAULT_METRIC_MAPPING

    def metric(name: str):
        if name in metric_overrides and metric_overrides[name] is not None:
            return metric_overrides[name]
        src = mapping.get(name)
        if src is not None and src in v1_1_row:
            return v1_1_row[src]
        return metric_overrides.get(name)  # may be None

    v1_1_verdict = normalize_v1_1_verdict(v1_1_row)

    row = build_v1_2_diagnostic_row(
        strategy_name=strategy_name if strategy_name is not None
        else v1_1_row.get("strategy_name", ""),
        strategy_version=strategy_version if strategy_version is not None
        else v1_1_row.get("strategy_version", ""),
        ticker=ticker if ticker is not None else v1_1_row.get("ticker", ""),
        test_window=test_window if test_window is not None
        else _derive_window(v1_1_row),
        strategy_exposure_pct=strategy_exposure_pct
        if strategy_exposure_pct is not None
        else v1_1_row.get("strategy_exposure_pct"),
        strategy_total_return=metric("strategy_total_return"),
        strategy_calmar=metric("strategy_calmar"),
        buy_hold_total_return=metric("buy_hold_total_return"),
        buy_hold_calmar=metric("buy_hold_calmar"),
        exposure_matched_bh_total_return=metric("exposure_matched_bh_total_return"),
        exposure_matched_bh_calmar=metric("exposure_matched_bh_calmar"),
        randomized_timing_p95_total_return=metric("randomized_timing_p95_total_return"),
        randomized_timing_p95_calmar=metric("randomized_timing_p95_calmar"),
        v1_1_verdict_preserved=v1_1_verdict,
    )
    return row


def add_v1_2_columns(
    df,
    *,
    metric_mapping: Optional[dict[str, str]] = None,
    **metric_overrides,
):
    """
    Return a NEW DataFrame with v1.2 side-by-side columns appended.

    The input DataFrame is not mutated. Existing columns (including the v1.1
    verdict / status columns) are preserved unchanged. v1.2 columns that would
    collide with an existing name are written under a 'v1_2_' prefix so no v1.1
    column is ever overwritten.
    """
    import pandas as pd  # local import; module stays import-light

    out = df.copy()
    built_rows = [
        build_v1_2_report_row(
            row._asdict() if hasattr(row, "_asdict") else dict(row),
            metric_mapping=metric_mapping,
            **metric_overrides,
        )
        for row in (r for _, r in out.iterrows())
    ]

    v1_2_frame = pd.DataFrame(built_rows, columns=REQUIRED_V1_2_OUTPUT_COLUMNS)

    for col in REQUIRED_V1_2_OUTPUT_COLUMNS:
        target = col if col not in out.columns else f"v1_2_{col}"
        out[target] = v1_2_frame[col].values

    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derive_window(v1_1_row: dict) -> str:
    """Build a 'test_start–test_end' window string when not given explicitly."""
    if "test_window" in v1_1_row and v1_1_row["test_window"]:
        return str(v1_1_row["test_window"])
    start = v1_1_row.get("test_start")
    end = v1_1_row.get("test_end")
    if start and end:
        return f"{start}–{end}"
    return ""


# Defensive: keep the V1_1_LABELS reference available for callers/tests.
__all__ = [
    "DEFAULT_METRIC_MAPPING",
    "UNMAPPED_V1_2_METRICS",
    "normalize_v1_1_verdict",
    "build_v1_2_report_row",
    "add_v1_2_columns",
    "V1_1_LABELS",
]
