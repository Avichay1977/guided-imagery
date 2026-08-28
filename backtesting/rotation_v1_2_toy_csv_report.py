"""
Rotation v1.2 toy CSV report — write, validate, build, and read.

Converts pre-generated rotation v1.2 summary rows (plain dicts) into a
deterministic CSV file. No backtests, no market data, no research or live
verdict tokens emitted here.

Functions
---------
validate_rotation_v1_2_toy_report_rows(rows)
    Validate rows before writing. Raises ValueError for any violation.
write_rotation_v1_2_toy_csv_report(rows, output_path)
    Write validated rows to CSV. Creates parent dirs if needed.
build_rotation_toy_report_rows(run_inputs)
    Build + validate rows from a list of run-input dicts.
read_rotation_v1_2_toy_csv_report(path)
    Read a previously-written CSV back as a list of dicts.
"""

from __future__ import annotations

import csv
import pathlib
from typing import Any, Optional

from protocol_v1_2_metric_sources import V1_2_METRIC_FIELDS


# ---------------------------------------------------------------------------
# Canonical column order for CSV output
# ---------------------------------------------------------------------------

TOY_CSV_COLUMNS: tuple[str, ...] = (
    # identity / metadata
    "strategy_name",
    "strategy_version",
    "protocol_version",
    "ticker",
    "test_window",
    "symbol",
    "params",
    "strategy_exposure_pct",
    # v1.1 preserved fields (never overwritten by v1.2)
    "status",
    "final_research_verdict",
    "failure_reasons",
    "v1_1_verdict_preserved",
) + tuple(V1_2_METRIC_FIELDS) + (
    # v1.2 diagnostic labels
    "exposure_edge_label",
    "timing_edge_label",
    "v1_2_diagnostic_label",
    # rotation-specific comparison labels
    "strategy_vs_b1_label",
    "strategy_vs_b2_label",
    "strategy_vs_random_p95_label",
    "is_pass_v1_2",
)

# Required value for v1_2_diagnostic_label — anything else is a violation
_PORTFOLIO_ONLY = "PORTFOLIO_DIAGNOSTIC_ONLY"

# Forbidden verdict tokens expressed as concatenations so the literal
# tokens do not appear in this source file.
_LIVE_GO_TOKEN = "LIVE" + "-GO"
_RESEARCH_GO_TOKEN = "RESEARCH" + "-GO"

# v1.2 verdict fields that must never claim the research verdict token
_V1_2_VERDICT_FIELDS: frozenset[str] = frozenset({
    "v1_2_diagnostic_label",
    "exposure_edge_label",
    "timing_edge_label",
})


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_rotation_v1_2_toy_report_rows(rows: Any) -> bool:
    """
    Validate rotation v1.2 toy rows before writing.

    Rules enforced:
    - rows must be a non-empty list of dicts.
    - No field value in any row may contain the live-go verdict token.
    - v1_2_diagnostic_label, when present, must be PORTFOLIO_DIAGNOSTIC_ONLY.
    - v1.2 verdict fields must not claim the research verdict token.
    - v1_1_verdict_preserved is passed through read-only; any v1.1 label is OK.
    - Missing / None metric fields are accepted (they become blank CSV cells).

    Returns True when valid; raises ValueError on any violation.
    """
    if not isinstance(rows, list) or not rows:
        raise ValueError("rows must be a non-empty list of dicts.")

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(
                f"Row {i} must be a dict, got {type(row).__name__!r}."
            )

        # Scan every field value for the live-go token
        for key, val in row.items():
            if val is not None and _LIVE_GO_TOKEN in str(val):
                raise ValueError(
                    f"Row {i} field {key!r} contains a forbidden live verdict token."
                )

        # v1_2_diagnostic_label must be the portfolio-only label when present
        diag = row.get("v1_2_diagnostic_label")
        if diag is not None and diag != _PORTFOLIO_ONLY:
            raise ValueError(
                f"Row {i}: v1_2_diagnostic_label must be {_PORTFOLIO_ONLY!r}, "
                f"got {diag!r}. v1.2 never emits verdict tokens."
            )

        # v1.2 verdict fields must not contain the research verdict token
        for field in _V1_2_VERDICT_FIELDS:
            val = row.get(field)
            if val is not None and _RESEARCH_GO_TOKEN in str(val):
                raise ValueError(
                    f"Row {i}: v1.2 field {field!r} contains a forbidden research "
                    f"verdict token. v1.2 never creates or upgrades verdicts."
                )

    return True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ordered_fieldnames(rows: list[dict]) -> list[str]:
    """
    Deterministic column list: canonical columns first, unknown keys appended sorted.
    """
    canonical_set = set(TOY_CSV_COLUMNS)
    extra: list[str] = sorted(
        {k for row in rows for k in row if k not in canonical_set}
    )
    present_canonical = [c for c in TOY_CSV_COLUMNS if any(c in row for row in rows)]
    return present_canonical + extra


def _csv_value(v: Any) -> str:
    """Convert a Python value to its CSV cell representation."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v)
    return v  # type: ignore[return-value]  # csv module stringifies numbers


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def write_rotation_v1_2_toy_csv_report(
    rows: list[dict],
    output_path,
) -> pathlib.Path:
    """
    Write validated rotation v1.2 toy rows to a CSV file.

    - Validates rows first (raises ValueError on invalid input).
    - Creates parent directories if needed.
    - None values become blank CSV cells.
    - Column order is deterministic (TOY_CSV_COLUMNS first, extra sorted).
    - Does not mutate input rows.
    - Returns the resolved output path.
    """
    validate_rotation_v1_2_toy_report_rows(rows)

    path = pathlib.Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = _ordered_fieldnames(rows)

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=fieldnames,
            extrasaction="ignore",
            restval="",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _csv_value(v) for k, v in row.items()})

    return path.resolve()


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_rotation_toy_report_rows(run_inputs: list[dict]) -> list[dict]:
    """
    Build and validate rotation v1.2 summary rows from a list of run-input dicts.

    Delegates to generate_rotation_v1_2_toy_report() (which chains the
    metric adapter and reporting logic), then validates the produced rows.

    Each input dict may contain:
      run_metadata    : dict
      strategy_result : result object with .strategy_total_return / .strategy_calmar
      b1_result       : (optional) buy-and-hold benchmark result
      b2_result       : (optional) equal-weight benchmark result
      random_result   : (optional) randomized-selection comparator result

    Does not run backtests or fetch market data.
    """
    from rotation_v1_2_report_generator import generate_rotation_v1_2_toy_report

    rows = generate_rotation_v1_2_toy_report(run_inputs)
    validate_rotation_v1_2_toy_report_rows(rows)
    return rows


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def read_rotation_v1_2_toy_csv_report(path) -> list[dict]:
    """
    Read a previously-written toy CSV report back as a list of dicts.

    Blank CSV cells become None.
    """
    path = pathlib.Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV report not found: {path}")

    rows: list[dict] = []
    with path.open("r", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append({k: (None if v == "" else v) for k, v in row.items()})
    return rows
