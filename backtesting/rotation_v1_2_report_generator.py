"""
Rotation v1.2 report row generator.

Implements the full "row lifecycle" for a Rotation strategy:
  Rotation Results
    -> v1.2 Metric Adapter  (build_rotation_summary_row_with_v1_2_metrics)
    -> v1.2 Reporting Logic (apply_protocol_v1_2_reporting_logic)
    -> Final Summary Row

Diagnostic only.
No backtests, no market data, no research or live verdict tokens emitted.
"""

from __future__ import annotations

from protocol_v1_2_metric_sources import V1_2_METRIC_FIELDS
from protocol_v1_2_reporting import apply_protocol_v1_2_reporting_logic
from rotation_v1_2_metric_adapter import build_rotation_summary_row_with_v1_2_metrics


# Rotation-specific diagnostic label column names
ROTATION_LABEL_COLUMNS: tuple[str, ...] = (
    "strategy_vs_b1_label",
    "strategy_vs_b2_label",
    "strategy_vs_random_p95_label",
    "is_pass_v1_2",
)

# Preferred column order for CSV output (metadata → metrics → labels)
ROTATION_REPORT_COLUMNS: tuple[str, ...] = (
    "symbol",
    "params",
    "test_window",
    "strategy_exposure_pct",
) + tuple(V1_2_METRIC_FIELDS) + ROTATION_LABEL_COLUMNS


def generate_rotation_v1_2_summary_row(
    run_metadata: dict,
    strategy_result,
    b1_result=None,
    b2_result=None,
    random_result=None,
) -> dict:
    """
    Build a complete v1.2 rotation summary row.

    Steps:
      1. Starts from run_metadata (e.g. {'symbol': 'ROT_TOY_1', 'params': '...'}).
      2. Calls build_rotation_summary_row_with_v1_2_metrics to add the eight
         v1.2 metric source fields via rotation_v1_2_metric_adapter.
      3. Calls apply_protocol_v1_2_reporting_logic (from protocol_v1_2_reporting)
         to add: strategy_vs_b1_label, strategy_vs_b2_label,
         strategy_vs_random_p95_label, is_pass_v1_2.
      4. Returns the complete row dict.

    Returns a new dict; all inputs are unchanged.
    """
    enriched = build_rotation_summary_row_with_v1_2_metrics(
        dict(run_metadata),
        strategy_result,
        b1_buy_hold_result=b1_result,
        b2_equal_weight_result=b2_result,
        random_selection_result=random_result,
    )
    return apply_protocol_v1_2_reporting_logic(enriched)


def generate_rotation_v1_2_toy_report(results_list: list[dict]) -> list[dict]:
    """
    Generate a list of v1.2 summary rows from a list of run-input dicts.

    Each input dict may contain:
      run_metadata    : dict  — e.g. {'symbol': 'ROT_TOY_1', 'params': 'top_n=3'}
      strategy_result : result object with .strategy_total_return / .strategy_calmar
      b1_result       : (optional) buy-and-hold benchmark result
      b2_result       : (optional) equal-weight benchmark result
      random_result   : (optional) randomized-selection comparator result

    Returns a list of rows in consistent ROTATION_REPORT_COLUMNS order (any
    extra keys from run_metadata are appended after the canonical columns).
    """
    rows = []
    for item in results_list:
        row = generate_rotation_v1_2_summary_row(
            run_metadata=item.get("run_metadata", {}),
            strategy_result=item.get("strategy_result"),
            b1_result=item.get("b1_result"),
            b2_result=item.get("b2_result"),
            random_result=item.get("random_result"),
        )
        rows.append(_order_row(row))
    return rows


def _order_row(row: dict) -> dict:
    """Return a copy of row with preferred column order; extra keys appended."""
    ordered: dict = {}
    for col in ROTATION_REPORT_COLUMNS:
        if col in row:
            ordered[col] = row[col]
    for k, v in row.items():
        if k not in ordered:
            ordered[k] = v
    return ordered
