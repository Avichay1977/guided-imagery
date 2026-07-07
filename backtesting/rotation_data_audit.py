"""
Local CSV data audit for RelativeStrengthRotation_v1.

Audits already-on-disk OHLCV CSV files for the frozen 15-ticker universe
against the research split-spec requirements. NEVER fetches market data.
NEVER writes a CSV with market data. NEVER repairs missing rows.

The audit is structural: presence, schema, numeric finiteness, sign rules,
and date-coverage. It produces a JSON report. It does not authorize a
research run.

Hard prohibitions enforced by this module:
  - No outbound network calls.
  - No data-vendor library imports.
  - No timing-strategy runner imports.
  - No forward-fill / back-fill / interpolation.
  - No live or research verdict tokens emitted.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Config / Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RotationDataAuditConfig:
    start_date: str = "2015-01-01"
    end_date: str = "2024-12-31"
    required_columns: tuple = (
        "timestamp", "open", "high", "low", "close", "volume",
    )
    allow_adjusted_close: bool = True
    require_all_tickers: bool = True
    data_source_label: str = "LOCAL_CSV_AUDIT_ONLY"
    auto_adjust_required: bool = False
    # Trading-day boundary rule (deterministic, no external calendar).
    # If required_start_date / required_end_date falls on a non-trading day
    # (e.g., 2015-01-01 is a US-market holiday), the CSV is allowed to start
    # on the first available trading day on or after the required start, and
    # to end on the last available trading day on or before the required end,
    # provided the gap does not exceed `trading_day_slack_days` calendar days.
    # This is NOT a forward-fill / back-fill / interpolation. The audit still
    # never invents or fills any bar; it only relaxes the boundary equality.
    trading_day_slack_days: int = 7


@dataclass
class RotationTickerDataAudit:
    ticker: str
    found: bool
    path: Optional[str]
    row_count: int = 0
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    missing_required_columns: list = field(default_factory=list)
    has_adjusted_close: bool = False
    has_nan_ohlc: bool = False
    has_inf_ohlc: bool = False
    has_non_positive_ohlc: bool = False
    has_negative_volume: bool = False
    coverage_ok: bool = False
    valid_for_research: bool = False
    failure_reasons: list = field(default_factory=list)
    # Effective trading-day boundary actually observed in the CSV (string
    # ISO dates). Populated when the CSV passed validation up to the
    # coverage check. The "_effective" suffix marks that these are the
    # first/last trading days observed in the data, not the required dates.
    effective_first_trading_day: Optional[str] = None
    effective_last_trading_day: Optional[str] = None
    coverage_slack_days_used: int = 0


@dataclass
class RotationUniverseDataAuditResult:
    universe: list
    required_start_date: str
    required_end_date: str
    ticker_results: dict
    missing_tickers: list = field(default_factory=list)
    valid_tickers: list = field(default_factory=list)
    invalid_tickers: list = field(default_factory=list)
    all_required_tickers_present: bool = False
    all_required_tickers_valid: bool = False
    research_ready: bool = False
    diagnostics: dict = field(default_factory=dict)


_OHLC_COLUMNS = ("open", "high", "low", "close")


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_local_ticker_csvs(search_roots, universe: list) -> dict:
    """
    Recursively scan `search_roots` for CSV files whose filename starts with
    a frozen-universe ticker (case-insensitive).

    Returns a dict {ticker: pathlib.Path}. Tickers without a match are
    absent from the dict. When multiple CSVs match the same ticker, the
    deterministic lexicographic-smallest path is chosen.

    Does NOT read network. Does NOT read CSV contents. Pure path scan.
    """
    if not universe:
        return {}

    roots = []
    if isinstance(search_roots, (str, pathlib.Path)):
        roots = [pathlib.Path(search_roots)]
    else:
        roots = [pathlib.Path(r) for r in search_roots]

    candidates_by_ticker: dict[str, list[pathlib.Path]] = {t: [] for t in universe}
    upper_universe = {t.upper(): t for t in universe}

    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.csv")):
            name_upper = path.name.upper()
            for upper_t, original_t in upper_universe.items():
                # Match patterns: AAPL.csv, AAPL_2015-01-01_2024-12-31.csv,
                # but reject substrings like AAPLE.csv (require non-alnum boundary).
                if name_upper.startswith(upper_t):
                    tail = name_upper[len(upper_t):]
                    if tail == ".CSV" or (tail and not tail[0].isalnum()):
                        candidates_by_ticker[original_t].append(path)

    matched: dict[str, pathlib.Path] = {}
    for ticker, paths in candidates_by_ticker.items():
        if paths:
            matched[ticker] = sorted(paths, key=lambda p: str(p))[0]
    return matched


# ---------------------------------------------------------------------------
# Per-ticker audit
# ---------------------------------------------------------------------------

def audit_ticker_csv(
    ticker: str,
    path: Any,
    config: Optional[RotationDataAuditConfig] = None,
) -> RotationTickerDataAudit:
    """
    Audit a single ticker's local CSV for structural and content validity.

    Reads ONLY the file at `path`. Never fetches. Never modifies the CSV.
    Never forward-fills, back-fills, or interpolates.

    Returns a RotationTickerDataAudit with explicit failure_reasons.
    """
    cfg = config or RotationDataAuditConfig()
    audit = RotationTickerDataAudit(
        ticker=ticker, found=False, path=None,
    )

    if path is None:
        audit.failure_reasons.append("PATH_IS_NONE")
        return audit

    p = pathlib.Path(path)
    if not p.exists() or not p.is_file():
        audit.failure_reasons.append(f"FILE_NOT_FOUND:{p}")
        return audit

    audit.path = str(p)
    audit.found = True

    try:
        df = pd.read_csv(p)
    except Exception as exc:
        audit.failure_reasons.append(f"READ_ERROR:{exc!r}")
        return audit

    audit.row_count = int(len(df))
    if audit.row_count == 0:
        audit.failure_reasons.append("EMPTY_CSV")
        return audit

    # Required columns
    missing_cols = [c for c in cfg.required_columns if c not in df.columns]
    audit.missing_required_columns = missing_cols
    if missing_cols:
        audit.failure_reasons.append(
            f"MISSING_REQUIRED_COLUMNS:{missing_cols}"
        )
        return audit

    audit.has_adjusted_close = "adjusted_close" in df.columns

    # Timestamp parseability
    try:
        timestamps = pd.to_datetime(df["timestamp"], errors="raise")
    except Exception:
        audit.failure_reasons.append("TIMESTAMP_UNPARSEABLE")
        return audit
    if timestamps.isna().any():
        audit.failure_reasons.append("TIMESTAMP_HAS_NAT")
        return audit

    # OHLC numeric / finite / positive
    for col in _OHLC_COLUMNS:
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.isna().any():
            audit.has_nan_ohlc = True
            audit.failure_reasons.append(f"NAN_OR_NON_NUMERIC:{col}")
            continue
        arr = numeric.to_numpy(dtype="float64")
        if np.isinf(arr).any():
            audit.has_inf_ohlc = True
            audit.failure_reasons.append(f"INF:{col}")
        if (arr <= 0.0).any():
            audit.has_non_positive_ohlc = True
            audit.failure_reasons.append(f"NON_POSITIVE:{col}")

    # Volume non-negative
    volume_numeric = pd.to_numeric(df["volume"], errors="coerce")
    if volume_numeric.isna().any():
        audit.failure_reasons.append("VOLUME_NAN_OR_NON_NUMERIC")
    else:
        v_arr = volume_numeric.to_numpy(dtype="float64")
        if not np.isfinite(v_arr).all():
            audit.failure_reasons.append("VOLUME_INF")
        if (v_arr < 0.0).any():
            audit.has_negative_volume = True
            audit.failure_reasons.append("NEGATIVE_VOLUME")

    # Coverage — trading-day boundary rule.
    #
    # The required dates are calendar dates, but markets close on holidays
    # and weekends. The CSV is considered to cover the start when:
    #   ts_min <= required_start_date + slack_days
    # AND there is no observed bar BEFORE required_start_date that the CSV
    # somehow skipped (i.e., ts_min is the first available trading day on
    # or after required_start_date).
    #
    # Equivalent rule for the end: ts_max >= required_end_date - slack_days.
    #
    # This is a deterministic boundary relaxation for non-trading calendar
    # dates. It is NOT a forward-fill / back-fill / interpolation: no bars
    # are invented or modified. Only the equality check is widened so that
    # a CSV whose first row is 2015-01-02 satisfies a required_start_date
    # of 2015-01-01 (a US-market holiday).
    ts_min = timestamps.min()
    ts_max = timestamps.max()
    audit.start_date = str(ts_min.date())
    audit.end_date = str(ts_max.date())
    audit.effective_first_trading_day = audit.start_date
    audit.effective_last_trading_day = audit.end_date

    req_start = pd.Timestamp(cfg.start_date)
    req_end = pd.Timestamp(cfg.end_date)
    slack_days = int(getattr(cfg, "trading_day_slack_days", 0))
    slack = pd.Timedelta(days=slack_days)

    coverage_start_ok = ts_min <= (req_start + slack)
    coverage_end_ok = ts_max >= (req_end - slack)
    audit.coverage_ok = bool(coverage_start_ok and coverage_end_ok)
    audit.coverage_slack_days_used = slack_days

    if not coverage_start_ok:
        audit.failure_reasons.append(
            f"COVERAGE_MISS_START:first_trading_day_observed={audit.start_date}"
            f"_exceeds_required_start_date={cfg.start_date}"
            f"_plus_{slack_days}_day_slack"
        )
    if not coverage_end_ok:
        audit.failure_reasons.append(
            f"COVERAGE_MISS_END:last_trading_day_observed={audit.end_date}"
            f"_short_of_required_end_date={cfg.end_date}"
            f"_minus_{slack_days}_day_slack"
        )

    audit.valid_for_research = (
        audit.found
        and not audit.missing_required_columns
        and not audit.has_nan_ohlc
        and not audit.has_inf_ohlc
        and not audit.has_non_positive_ohlc
        and not audit.has_negative_volume
        and audit.coverage_ok
        and not audit.failure_reasons
    )
    return audit


# ---------------------------------------------------------------------------
# Universe-level audit
# ---------------------------------------------------------------------------

def audit_frozen_universe_data(
    search_roots,
    universe: list,
    config: Optional[RotationDataAuditConfig] = None,
) -> RotationUniverseDataAuditResult:
    """
    Audit the entire frozen universe against local CSVs only.

    research_ready is True only if EVERY ticker in `universe` is found and
    passes audit. Missing tickers force research_ready=False.
    """
    cfg = config or RotationDataAuditConfig()
    paths = find_local_ticker_csvs(search_roots, universe)

    ticker_results: dict[str, RotationTickerDataAudit] = {}
    missing: list[str] = []
    valid: list[str] = []
    invalid: list[str] = []

    for ticker in universe:
        path = paths.get(ticker)
        if path is None:
            audit = RotationTickerDataAudit(
                ticker=ticker, found=False, path=None,
                failure_reasons=["TICKER_NOT_FOUND_LOCALLY"],
            )
            ticker_results[ticker] = audit
            missing.append(ticker)
            invalid.append(ticker)
            continue
        audit = audit_ticker_csv(ticker, path, cfg)
        ticker_results[ticker] = audit
        if audit.valid_for_research:
            valid.append(ticker)
        else:
            invalid.append(ticker)

    all_present = len(missing) == 0
    all_valid = (len(invalid) == 0) and all_present
    research_ready = all_present and all_valid

    diagnostics = {
        "data_source_label": cfg.data_source_label,
        "auto_adjust_required": cfg.auto_adjust_required,
        "research_run_authorized": False,
        "market_data_fetched": False,
        "v1_1_verdict_impact": "NONE",
        "audit_mode": "LOCAL_CSV_ONLY",
        "trading_day_slack_days": int(getattr(cfg, "trading_day_slack_days", 0)),
        "boundary_rule": "first_trading_day_on_or_after_required_start_date",
    }

    return RotationUniverseDataAuditResult(
        universe=list(universe),
        required_start_date=cfg.start_date,
        required_end_date=cfg.end_date,
        ticker_results=ticker_results,
        missing_tickers=missing,
        valid_tickers=valid,
        invalid_tickers=invalid,
        all_required_tickers_present=all_present,
        all_required_tickers_valid=all_valid,
        research_ready=research_ready,
        diagnostics=diagnostics,
    )


# ---------------------------------------------------------------------------
# JSON report writer
# ---------------------------------------------------------------------------

def write_data_audit_report(
    result: RotationUniverseDataAuditResult,
    output_path,
) -> pathlib.Path:
    """
    Write a deterministic JSON audit report.

    - Creates parent directory if missing.
    - Writes JSON only; never any market-data CSV.
    - Does not mutate the input result.
    - Returns the resolved output path.
    """
    path = pathlib.Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "universe": list(result.universe),
        "required_start_date": result.required_start_date,
        "required_end_date": result.required_end_date,
        "all_required_tickers_present": result.all_required_tickers_present,
        "all_required_tickers_valid": result.all_required_tickers_valid,
        "research_ready": result.research_ready,
        "missing_tickers": list(result.missing_tickers),
        "valid_tickers": list(result.valid_tickers),
        "invalid_tickers": list(result.invalid_tickers),
        "ticker_results": {
            t: asdict(a) for t, a in result.ticker_results.items()
        },
        "diagnostics": dict(result.diagnostics),
    }

    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    return path.resolve()


__all__ = [
    "RotationDataAuditConfig",
    "RotationTickerDataAudit",
    "RotationUniverseDataAuditResult",
    "find_local_ticker_csvs",
    "audit_ticker_csv",
    "audit_frozen_universe_data",
    "write_data_audit_report",
]
