"""
v1.2 Dry Report Generation — batch side-by-side diagnostic reports from
existing CSV summary files only.

Reads one or more existing v1.1 summary CSVs, appends Protocol v1.2
exposure-fair diagnostic columns via protocol_v1_2_reporting.add_v1_2_columns,
and writes the combined CSV to a separate output directory. Never touches the
input files.

Diagnostic only. This script:
  - Never runs a backtest.
  - Never runs strategy_lab_runner.
  - Never fetches or reads market data.
  - Never emits RESEARCH-GO or LIVE-GO.
  - Never modifies the input CSV in place.
  - Never converts a v1.1 NO-GO into an approval.

Missing v1.2 metrics (total returns / p95 comparators) are NOT fabricated —
they surface as *_INSUFFICIENT_DATA, exactly as in the dry adapter CLI.

Usage:
    python v1_2_generate_dry_reports.py --inputs a.csv b.csv \
        [--output-dir v1_2_dry_reports] [--suffix _v1_2]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from protocol_v1_2_reporting import add_v1_2_columns


# ---------------------------------------------------------------------------
# Per-file processing
# ---------------------------------------------------------------------------

def _label_distribution(df: pd.DataFrame, column: str) -> dict:
    if column not in df.columns:
        return {}
    return df[column].value_counts(dropna=False).to_dict()


def _count_live_go(df: pd.DataFrame) -> int:
    count = 0
    for col in df.columns:
        for val in df[col].tolist():
            s = str(val)
            if "LIVE-GO" in s or "LIVE_GO" in s:
                count += 1
    return count


def _count_no_go_converted_to_research_go(original: pd.DataFrame, result: pd.DataFrame) -> int:
    """
    Count rows that were v1.1 NO-GO but whose v1.2 diagnostic label claims a
    RESEARCH approval. Must always be 0 — v1.2 never upgrades a verdict.
    """
    if "v1_2_diagnostic_label" not in result.columns:
        return 0

    # Identify v1.1 NO-GO rows from whatever verdict column is available.
    verdict_col = None
    for cand in ("v1_1_verdict", "v1_1_verdict_preserved"):
        if cand in result.columns:
            verdict_col = cand
            break

    count = 0
    for idx in range(len(result)):
        diag = str(result["v1_2_diagnostic_label"].iloc[idx]).upper()
        is_no_go = False
        if verdict_col is not None:
            is_no_go = "NO_GO" in str(result[verdict_col].iloc[idx]).upper()
        if is_no_go and "RESEARCH" in diag:
            count += 1
    return count


def _process_one(
    input_path: Path,
    output_dir: Path,
    suffix: str,
) -> tuple[int, dict]:
    """
    Process a single input CSV. Returns (status_code, info_dict).
    status_code 0 == success + invariants hold; 1 == failure.
    """
    info: dict = {"input": str(input_path)}

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        return 1, info

    try:
        df = pd.read_csv(input_path)
    except Exception as exc:
        print(f"ERROR: Could not read {input_path}: {exc}", file=sys.stderr)
        return 1, info

    if df.empty:
        print(f"ERROR: Input CSV is empty: {input_path}", file=sys.stderr)
        return 1, info

    # Apply v1.2 adapter (non-invasive, never mutates df)
    try:
        result = add_v1_2_columns(df)
    except Exception as exc:
        print(f"ERROR: add_v1_2_columns failed for {input_path}: {exc}", file=sys.stderr)
        return 1, info

    # Invariant checks BEFORE writing
    live_go = _count_live_go(result)
    converted = _count_no_go_converted_to_research_go(df, result)
    if live_go != 0:
        print(f"ERROR: invariant failure — {live_go} LIVE-GO occurrence(s) in {input_path}",
              file=sys.stderr)
        return 1, info
    if converted != 0:
        print(f"ERROR: invariant failure — {converted} v1.1 NO-GO row(s) converted to "
              f"RESEARCH-GO in {input_path}", file=sys.stderr)
        return 1, info
    if len(result) != len(df):
        print(f"ERROR: invariant failure — row count changed for {input_path} "
              f"({len(df)} -> {len(result)})", file=sys.stderr)
        return 1, info

    # Resolve output path (never the same as input)
    output_path = output_dir / f"{input_path.stem}{suffix}{input_path.suffix}"
    if output_path.resolve() == input_path.resolve():
        print(f"ERROR: output path would overwrite input: {output_path}", file=sys.stderr)
        return 1, info

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_path, index=False)
    except Exception as exc:
        print(f"ERROR: Could not write {output_path}: {exc}", file=sys.stderr)
        return 1, info

    info.update({
        "output": str(output_path),
        "rows": len(result),
        "exposure_dist": _label_distribution(result, "exposure_edge_label"),
        "timing_dist": _label_distribution(result, "timing_edge_label"),
        "live_go": live_go,
        "no_go_converted": converted,
    })

    # Concise per-file summary
    print("-" * 66)
    print(f"  input          : {info['input']}")
    print(f"  output         : {info['output']}")
    print(f"  rows           : {info['rows']}")
    print(f"  exposure_edge_label distribution:")
    for label, cnt in info["exposure_dist"].items():
        print(f"      {str(label):45s} {cnt}")
    print(f"  timing_edge_label distribution:")
    for label, cnt in info["timing_dist"].items():
        print(f"      {str(label):45s} {cnt}")
    print(f"  LIVE-GO occurrences          : {info['live_go']}  (must be 0)")
    print(f"  NO-GO converted to RESEARCH-GO: {info['no_go_converted']}  (must be 0)")

    return 0, info


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="v1_2_generate_dry_reports",
        description=(
            "Batch-generate Protocol v1.2 side-by-side diagnostic CSVs from "
            "existing v1.1 summary CSVs. Diagnostic only — no backtests, no "
            "market data, no RESEARCH-GO / LIVE-GO, no input mutation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--inputs", "-i", nargs="+", required=True, metavar="CSV",
        help="One or more v1.1 summary CSV paths.",
    )
    p.add_argument(
        "--output-dir", "-o", default="v1_2_dry_reports", metavar="DIR",
        help="Directory to write v1.2 CSVs into (created if missing).",
    )
    p.add_argument(
        "--suffix", "-s", default="_v1_2", metavar="STR",
        help="Suffix appended to each input stem for the output filename.",
    )
    return p


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    suffix = args.suffix

    print("=" * 66)
    print("Protocol v1.2 Dry Report Generation")
    print("=" * 66)

    generated: list[str] = []
    overall_ok = True

    for raw in args.inputs:
        code, info = _process_one(Path(raw), output_dir, suffix)
        if code != 0:
            overall_ok = False
            # continue processing the rest so the user sees all failures,
            # but the overall exit code will be 1.
            continue
        if "output" in info:
            generated.append(info["output"])

    print("=" * 66)
    print(f"  generated {len(generated)} file(s):")
    for g in generated:
        print(f"    {g}")
    print("=" * 66)

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
