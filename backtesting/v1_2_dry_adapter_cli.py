"""
v1.2 Dry Adapter CLI — applies Protocol v1.2 exposure-fair diagnostic columns
to an existing v1.1 result CSV without running any backtest or market data fetch.

Diagnostic only. This script:
  - Never runs a backtest.
  - Never fetches market data.
  - Never emits RESEARCH-GO or LIVE-GO.
  - Never modifies or overrides v1.1 verdicts / status / failure_reasons.
  - Writes only side-by-side v1.2 diagnostic columns next to the originals.

Usage:
    python v1_2_dry_adapter_cli.py --input <v1.1-csv> [--output <path>]

If --output is omitted, the output file is written to the same directory as
the input with "_v1_2" appended before the extension.

Important about edge classification on v1.1 CSVs:
    v1.1 result CSVs (walk_forward / strategy_lab) contain Calmar-based fields
    but NOT total-return fields or p95 comparators.  Because both total return
    AND Calmar are required for a PASS/FAIL verdict, all exposure and timing
    edges will surface as *_INSUFFICIENT_DATA when processing raw v1.1 CSVs.
    This is correct and expected — it documents the data gap, not a failure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from protocol_v1_2_reporting import add_v1_2_columns


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_summary(
    original: pd.DataFrame,
    result: pd.DataFrame,
    input_path: Path,
    output_path: Path,
) -> None:
    added_cols = [c for c in result.columns if c not in original.columns]

    print()
    print("=" * 70)
    print("Protocol v1.2 Dry Adapter — diagnostic summary")
    print("=" * 70)
    print(f"  Input  : {input_path}")
    print(f"  Output : {output_path}")
    print(f"  Rows   : {len(original)} input  →  {len(result)} output (unchanged)")
    print(f"  v1.2 columns added ({len(added_cols)}): {', '.join(added_cols)}")
    print()

    # Exposure edge counts
    if "exposure_edge_label" in result.columns:
        counts = result["exposure_edge_label"].value_counts()
        print("  exposure_edge_label distribution:")
        for label, cnt in counts.items():
            print(f"    {label:45s}  {cnt}")
    print()

    # Timing edge counts
    if "timing_edge_label" in result.columns:
        counts = result["timing_edge_label"].value_counts()
        print("  timing_edge_label distribution:")
        for label, cnt in counts.items():
            print(f"    {label:45s}  {cnt}")
    print()

    # v1.2 diagnostic label (always PORTFOLIO_DIAGNOSTIC_ONLY)
    if "v1_2_diagnostic_label" in result.columns:
        unique_labels = result["v1_2_diagnostic_label"].unique().tolist()
        print(f"  v1_2_diagnostic_label: {unique_labels}")
    if "protocol_version" in result.columns:
        unique_pv = result["protocol_version"].unique().tolist()
        print(f"  protocol_version      : {unique_pv}")
    print()

    # v1.1 columns preserved check
    v1_1_status_cols = [c for c in ("status", "v1_1_verdict", "failure_reasons") if c in original.columns]
    if v1_1_status_cols:
        print("  v1.1 columns preserved (unchanged in output):")
        for col in v1_1_status_cols:
            # NaN-aware equality: use Series.equals() which treats NaN==NaN as True
            match = original[col].reset_index(drop=True).equals(
                result[col].reset_index(drop=True)
            )
            mark = "OK" if match else "MISMATCH"
            print(f"    [{mark}] {col}")
    print()

    # Hard guarantee: no LIVE-GO / RESEARCH-GO created
    live_go_found = False
    for col in result.columns:
        for val in result[col].tolist():
            s = str(val)
            if "LIVE-GO" in s or "LIVE_GO" in s:
                live_go_found = True
                print(f"  [ERROR] LIVE-GO found in column '{col}': {val!r}")
    if not live_go_found:
        print("  [OK] No LIVE-GO found anywhere in output.")

    # v1_2_diagnostic_label must not contain RESEARCH-GO
    if "v1_2_diagnostic_label" in result.columns:
        bad = result["v1_2_diagnostic_label"].apply(
            lambda x: "RESEARCH" in str(x).upper()
        ).any()
        if bad:
            print("  [ERROR] v1_2_diagnostic_label contains RESEARCH label — constraint violated.")
        else:
            print("  [OK] v1_2_diagnostic_label never contains RESEARCH-GO.")

    print()
    print("  NOTE: INSUFFICIENT_DATA edges are expected when processing raw v1.1")
    print("        CSVs — total returns and p95 metrics are not in the v1.1 format.")
    print("        Supply --strategy-total-return / --exposure-matched-total-return /")
    print("        --p95-total-return / --p95-calmar to enable PASS/FAIL classification.")
    print()
    print("=" * 70)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="v1_2_dry_adapter_cli",
        description=(
            "Apply Protocol v1.2 exposure-fair diagnostic columns to a v1.1 "
            "result CSV. Diagnostic only — no backtests, no market data, no "
            "RESEARCH-GO / LIVE-GO."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--input", "-i", required=True, metavar="PATH",
        help="Path to the v1.1 result CSV (walk_forward or strategy_lab output).",
    )
    p.add_argument(
        "--output", "-o", default=None, metavar="PATH",
        help=(
            "Path to write the v1.1+v1.2 combined CSV. "
            "Defaults to <input-stem>_v1_2.csv in the same directory."
        ),
    )
    # Optional explicit metric overrides — allow callers with richer data to
    # supply total-return and p95 figures so PASS/FAIL classification fires.
    p.add_argument(
        "--strategy-total-return", type=float, default=None, metavar="FLOAT",
        help="Strategy total return (applied uniformly to all rows).",
    )
    p.add_argument(
        "--buy-hold-total-return", type=float, default=None, metavar="FLOAT",
        help="Buy-and-hold total return comparator.",
    )
    p.add_argument(
        "--exposure-matched-total-return", type=float, default=None, metavar="FLOAT",
        help="Exposure-matched B&H total return comparator.",
    )
    p.add_argument(
        "--p95-total-return", type=float, default=None, metavar="FLOAT",
        help="Randomized timing p95 total return.",
    )
    p.add_argument(
        "--p95-calmar", type=float, default=None, metavar="FLOAT",
        help="Randomized timing p95 Calmar.",
    )
    p.add_argument(
        "--no-summary", action="store_true", default=False,
        help="Suppress the printed summary (still writes CSV).",
    )
    return p


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        return 1

    # Derive output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_name(input_path.stem + "_v1_2" + input_path.suffix)

    # Load v1.1 CSV
    try:
        df = pd.read_csv(input_path)
    except Exception as exc:
        print(f"ERROR: Could not read {input_path}: {exc}", file=sys.stderr)
        return 1

    if df.empty:
        print(f"ERROR: Input CSV is empty: {input_path}", file=sys.stderr)
        return 1

    # Build optional metric overrides (only supplied non-None values pass through)
    overrides: dict = {}
    _opt_map = {
        "strategy_total_return": args.strategy_total_return,
        "buy_hold_total_return": args.buy_hold_total_return,
        "exposure_matched_bh_total_return": args.exposure_matched_total_return,
        "randomized_timing_p95_total_return": args.p95_total_return,
        "randomized_timing_p95_calmar": args.p95_calmar,
    }
    for k, v in _opt_map.items():
        if v is not None:
            overrides[k] = v

    # Apply v1.2 adapter (non-invasive, never mutates df)
    try:
        result = add_v1_2_columns(df, **overrides)
    except Exception as exc:
        print(f"ERROR: add_v1_2_columns failed: {exc}", file=sys.stderr)
        return 1

    # Write output
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_path, index=False)
    except Exception as exc:
        print(f"ERROR: Could not write {output_path}: {exc}", file=sys.stderr)
        return 1

    # Print summary (unless suppressed)
    if not args.no_summary:
        _print_summary(df, result, input_path, output_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
