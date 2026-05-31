"""
RotationBacktester — dedicated multi-asset rotation engine scaffold.

For RelativeStrengthRotation_v1 (asset-selection / rotation family).

SCAFFOLD ONLY. run() is intentionally NOT implemented — it raises so that no
fabricated returns, equity curves, or verdicts can be produced before the real
engine exists. The decision to build this dedicated engine is recorded in
ROTATION_ENGINE_DECISION_RELATIVE_STRENGTH_ROTATION_V1.md
(DECISION: DEDICATED_ROTATION_BACKTESTER_REQUIRED).

What IS implemented here are the pure, deterministic, side-effect-free helper
methods that the future run() will compose:

  - select_rebalance_dates   — calendar logic (first trading day per month)
  - validate_universe_data    — structural validation of toy/real data dicts
  - select_top_n_assets       — eligibility + hysteresis-capped selection (§11, §12)
  - calculate_equal_weights   — 1/top_n sizing (§13)
  - calculate_cash_weight     — unused-slot cash (§13)

Hard invariants enforced by this scaffold (frozen by the spec):
  - top_n = 3 hard cap; hysteresis NEVER produces more than top_n holdings
  - equal weight is 1/top_n, NOT 1/number_selected
  - unused slots remain cash (never redistributed)
  - no leverage, no shorting
  - NaN / inf / None / missing composite_rs disqualifies a ticker
  - no market-data-fetch library imported, no market-data access
  - no research/live verdict tokens emitted anywhere
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Config / Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RotationBacktesterConfig:
    """Frozen rotation parameters (defaults mirror the spec)."""

    top_n: int = 3
    rebalance_frequency: str = "monthly"
    hysteresis_threshold: float = 0.50
    initial_cash: float = 100_000.0
    cash_return: float = 0.0
    allow_leverage: bool = False
    allow_shorting: bool = False


@dataclass
class RotationBacktesterResult:
    """
    Portfolio-level result container (scaffold).

    Populated by a future run() implementation. Defined here so the output
    schema is fixed before execution code is written. No values are fabricated.
    """

    equity_curve: list[float] = field(default_factory=list)
    rebalance_events: list[dict] = field(default_factory=list)
    per_ticker_contribution_pct: dict[str, float] = field(default_factory=dict)
    exposure_pct: Optional[float] = None
    final_equity: Optional[float] = None
    strategy_total_return: Optional[float] = None
    strategy_calmar: Optional[float] = None
    v1_2_metric_sources: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_finite_number(value: Any) -> bool:
    """True only for a real, finite number (rejects None, NaN, ±inf, non-numeric)."""
    if value is None or isinstance(value, bool):
        return False
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    return not (math.isnan(f) or math.isinf(f))


# ---------------------------------------------------------------------------
# RotationBacktester
# ---------------------------------------------------------------------------

class RotationBacktester:
    """
    Dedicated rotation engine scaffold.

    run() is NOT implemented. The helper methods below are pure and
    deterministic and may be unit-tested on toy data only.
    """

    NOT_IMPLEMENTED_MESSAGE = (
        "RotationBacktester.run is not implemented yet; scaffold only."
    )

    # eligibility filter columns required True for a ticker to participate
    _FILTER_FIELDS: tuple[str, ...] = (
        "trend_filter_ema200",
        "volatility_filter_atr_pct",
        "liquidity_filter_volume_avg_20",
    )

    def __init__(self, config: Optional[RotationBacktesterConfig] = None) -> None:
        self.config = config or RotationBacktesterConfig()
        if self.config.allow_leverage:
            raise ValueError("RotationBacktester does not permit leverage.")
        if self.config.allow_shorting:
            raise ValueError("RotationBacktester does not permit shorting.")
        if self.config.top_n < 1:
            raise ValueError("top_n must be >= 1.")

    # ------------------------------------------------------------------
    # Calendar
    # ------------------------------------------------------------------

    def select_rebalance_dates(self, dates) -> list[pd.Timestamp]:
        """
        Return the first available trading date of each calendar month.

        `dates` may be any iterable of date-likes (strings, datetimes,
        Timestamps). Output is sorted ascending, one Timestamp per (year, month).
        """
        timestamps = sorted(pd.Timestamp(d) for d in dates)
        seen: set[tuple[int, int]] = set()
        result: list[pd.Timestamp] = []
        for ts in timestamps:
            key = (ts.year, ts.month)
            if key not in seen:
                seen.add(key)
                result.append(ts)
        return result

    # ------------------------------------------------------------------
    # Universe data validation
    # ------------------------------------------------------------------

    def validate_universe_data(self, universe_data) -> bool:
        """
        Validate structural shape of a universe-data dict (toy or real).

        Raises ValueError on any structural problem. Returns True when valid.
        Does NOT fetch or inspect market values — purely structural.
        """
        if not isinstance(universe_data, dict):
            raise ValueError("universe_data must be a dict of ticker -> data.")
        if not universe_data:
            raise ValueError("universe_data must not be empty.")
        for ticker, data in universe_data.items():
            if not isinstance(ticker, str) or not ticker:
                raise ValueError(f"Invalid ticker key: {ticker!r}")
            if data is None:
                raise ValueError(f"universe_data[{ticker!r}] is None.")
            if hasattr(data, "__len__") and len(data) == 0:
                raise ValueError(f"universe_data[{ticker!r}] is empty.")
        return True

    # ------------------------------------------------------------------
    # Eligibility + selection (§11, §12)
    # ------------------------------------------------------------------

    def _is_eligible(self, row: dict) -> bool:
        """
        A ticker is eligible at a rebalance bar only if ALL filters are True and
        its composite_rs and rank_percentile are finite numbers.
        """
        if not isinstance(row, dict):
            return False
        if "ticker" not in row or not isinstance(row["ticker"], str):
            return False
        for f in self._FILTER_FIELDS:
            if row.get(f) is not True:
                return False
        if not _is_finite_number(row.get("composite_rs")):
            return False
        if not _is_finite_number(row.get("rank_percentile")):
            return False
        return True

    def select_top_n_assets(
        self,
        feature_rows,
        existing_holdings=None,
    ) -> list[str]:
        """
        Apply the spec §12 hysteresis-capped selection algorithm.

        feature_rows : iterable of per-ticker dicts with keys:
            ticker, composite_rs, rank_percentile, and the three filter booleans.
        existing_holdings : optional list of currently-held tickers.

        Returns the selected ticker list (length <= top_n), ordered
        deterministically by composite_rs descending, ticker ascending.

        Algorithm (frozen, spec §12):
          1. keep-set = existing holdings that are eligible AND
             rank_percentile >= hysteresis_threshold.
          2. if |keep-set| > N: keep only top N of keep-set by
             composite_rs desc, ticker asc.
          3. if |keep-set| < N: fill remaining slots from eligible non-held
             assets, top-ranked by composite_rs desc, ticker asc.
          4. remainder (if fewer than N qualify) stays cash (implicit here —
             this method returns fewer than N tickers).
        """
        existing = set(existing_holdings or [])
        n = self.config.top_n
        thresh = self.config.hysteresis_threshold

        eligible = [r for r in feature_rows if self._is_eligible(r)]

        def _rank_key(r: dict):
            return (-float(r["composite_rs"]), r["ticker"])

        # Step 1: preliminary keep-set
        keep = [
            r for r in eligible
            if r["ticker"] in existing
            and float(r["rank_percentile"]) >= thresh
        ]
        keep_sorted = sorted(keep, key=_rank_key)

        # Step 2: trim oversized keep-set to N (hard cap)
        if len(keep_sorted) > n:
            selected = keep_sorted[:n]
        else:
            selected = list(keep_sorted)
            # Step 3: fill from eligible non-held assets
            kept = {r["ticker"] for r in selected}
            fill_candidates = [
                r for r in eligible
                if r["ticker"] not in existing and r["ticker"] not in kept
            ]
            for r in sorted(fill_candidates, key=_rank_key):
                if len(selected) >= n:
                    break
                selected.append(r)

        # Hard invariant: never exceed N
        assert len(selected) <= n, "selection exceeded top_n (invariant violated)"

        return [r["ticker"] for r in sorted(selected, key=_rank_key)]

    # ------------------------------------------------------------------
    # Sizing (§13)
    # ------------------------------------------------------------------

    def calculate_equal_weights(self, selected_assets) -> dict[str, float]:
        """
        Equal weight = 1/top_n for each selected asset (NOT 1/number_selected).

        Unused slots are implicitly cash (see calculate_cash_weight).
        """
        n = self.config.top_n
        if len(selected_assets) > n:
            raise ValueError(
                f"selected_assets ({len(selected_assets)}) exceeds top_n ({n})."
            )
        w = 1.0 / n
        return {ticker: w for ticker in selected_assets}

    def calculate_cash_weight(self, selected_assets) -> float:
        """
        Cash weight = (top_n - number_selected) / top_n.

        Cash is never redistributed into positions (spec §13).
        """
        n = self.config.top_n
        invested = len(selected_assets) * (1.0 / n)
        cash = 1.0 - invested
        return cash if cash > 0.0 else 0.0

    # ------------------------------------------------------------------
    # run() — intentionally not implemented
    # ------------------------------------------------------------------

    def run(self, universe_data, strategy):
        """
        Scaffold only. Raises NotImplementedError to prevent fabricated output.
        """
        raise NotImplementedError(self.NOT_IMPLEMENTED_MESSAGE)
