"""
RotationBacktester — dedicated multi-asset rotation engine.

For RelativeStrengthRotation_v1 (asset-selection / rotation family).

Accepts precomputed feature matrices and return series.
No market-data-fetch library imported. No runner imported.
No verdict tokens emitted anywhere.

What IS implemented here:
  - select_rebalance_dates   — calendar logic (first trading day per month)
  - validate_universe_data   — structural validation of toy data dicts
  - select_top_n_assets      — eligibility + hysteresis-capped selection (§11, §12)
  - calculate_equal_weights  — 1/top_n sizing (§13)
  - calculate_cash_weight    — unused-slot cash (§13)
  - run()                    — portfolio path engine for precomputed toy inputs

Hard invariants enforced here (frozen by the spec):
  - top_n = 3 hard cap; hysteresis NEVER produces more than top_n holdings
  - equal weight is 1/top_n, NOT 1/number_selected
  - unused slots remain cash (never redistributed)
  - no leverage, no shorting
  - NaN / inf / None / missing composite_rs disqualifies a ticker
  - no market-data-fetch library imported, no market-data access
  - no verdict tokens emitted anywhere

Engine decision:
  DEDICATED_ROTATION_BACKTESTER_REQUIRED
  (recorded in ROTATION_ENGINE_DECISION_RELATIVE_STRENGTH_ROTATION_V1.md)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from rotation_benchmark_b2 import calculate_calmar


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
    annualization_days: int = 252


@dataclass
class RotationBacktesterResult:
    """
    Portfolio-level result container.

    equity_curve     : pd.Series of portfolio value at the start of each day
                       (before applying that day's returns); index = dates.
    rebalance_events : list of dicts, one per rebalance date.
    per_ticker_contribution_pct : {ticker: pct_of_initial_cash}.
    exposure_pct     : average invested fraction as a percentage.
    final_equity     : portfolio value after all returns applied.
    strategy_total_return : (final_equity / initial_cash) - 1.
    strategy_calmar  : annualized return / max drawdown (NaN when no drawdown).
    v1_2_metric_sources : diagnostics dict.
    weights_by_date  : DataFrame of drifted weights per date (tickers as columns).
    cash_by_date     : Series of cash value (not weight) per date.
    holdings_by_date : {date: [ticker, ...]} map of selected holdings.
    """

    equity_curve: Any = field(default_factory=list)
    rebalance_events: list[dict] = field(default_factory=list)
    per_ticker_contribution_pct: dict[str, float] = field(default_factory=dict)
    exposure_pct: Optional[float] = None
    final_equity: Optional[float] = None
    strategy_total_return: Optional[float] = None
    strategy_calmar: Optional[float] = None
    v1_2_metric_sources: dict[str, Any] = field(default_factory=dict)
    weights_by_date: Optional[pd.DataFrame] = None
    cash_by_date: Optional[pd.Series] = None
    holdings_by_date: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Required columns for feature_matrix input
# ---------------------------------------------------------------------------

_REQUIRED_FEATURE_COLS = frozenset({
    "date",
    "ticker",
    "composite_rs",
    "rank_percentile",
    "trend_filter_ema200",
    "volatility_filter_atr_pct",
    "liquidity_filter_volume_avg_20",
})


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
    Dedicated rotation engine.

    run() accepts precomputed toy feature matrices and return series.
    All helper methods are pure, deterministic, and may be unit-tested on
    toy data only.
    """

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
    # run()
    # ------------------------------------------------------------------

    def run(self, universe_data, strategy=None) -> RotationBacktesterResult:
        """
        Execute rotation backtest on precomputed feature matrix and return series.

        universe_data must be a dict containing:
          'feature_matrix'   : pd.DataFrame with columns date, ticker,
                               composite_rs, rank_percentile,
                               trend_filter_ema200, volatility_filter_atr_pct,
                               liquidity_filter_volume_avg_20.
          'returns_by_ticker': dict[str, pd.Series] of daily simple returns.

        Rebalances on the first trading day of each calendar month (derived
        from the union of all return-series dates). On each rebalance date the
        feature_matrix rows for that date are used to select holdings via the
        spec §12 hysteresis algorithm. Between rebalances no changes are made.

        Equity curve: recorded at the start of each day (before applying that
        day's returns). equity_curve.iloc[0] == initial_cash.

        Returns a RotationBacktesterResult with diagnostics marking this as
        a precomputed toy path — not research evidence.
        """
        # -- Input validation ------------------------------------------
        if not isinstance(universe_data, dict):
            raise ValueError(
                "universe_data must be a dict with 'feature_matrix' and "
                "'returns_by_ticker' keys."
            )
        if "feature_matrix" not in universe_data:
            raise ValueError(
                "universe_data must contain 'feature_matrix' key. "
                "Pass raw OHLCV data to a feature builder first."
            )
        if "returns_by_ticker" not in universe_data:
            raise ValueError(
                "universe_data must contain 'returns_by_ticker' key."
            )

        feature_matrix = universe_data["feature_matrix"]
        returns_by_ticker = universe_data["returns_by_ticker"]

        if not isinstance(feature_matrix, pd.DataFrame) or feature_matrix.empty:
            raise ValueError("feature_matrix must be a non-empty DataFrame.")
        if not isinstance(returns_by_ticker, dict) or not returns_by_ticker:
            raise ValueError("returns_by_ticker must be a non-empty dict.")

        missing_cols = _REQUIRED_FEATURE_COLS - set(feature_matrix.columns)
        if missing_cols:
            raise ValueError(
                f"feature_matrix is missing required columns: {sorted(missing_cols)}"
            )

        cfg = self.config

        # Normalise feature_matrix date column to Timestamp
        fm = feature_matrix.copy()
        fm["date"] = pd.to_datetime(fm["date"])

        # Build sorted union of all trading dates from return series
        all_dates_idx: pd.Index = pd.Index([], dtype="datetime64[ns]")
        for ticker, series in returns_by_ticker.items():
            if not isinstance(series, pd.Series):
                raise ValueError(
                    f"returns_by_ticker[{ticker!r}] must be a pd.Series."
                )
            all_dates_idx = all_dates_idx.union(series.index)
        all_dates: list[pd.Timestamp] = sorted(
            pd.Timestamp(d) for d in all_dates_idx
        )

        if not all_dates:
            raise ValueError("No dates found in returns_by_ticker.")

        # Rebalance dates: first trading day of each calendar month
        rebalance_dates: set[pd.Timestamp] = set(
            self.select_rebalance_dates(all_dates)
        )

        # -- Simulation state ------------------------------------------
        holding_values: dict[str, float] = {}
        cash_value: float = cfg.initial_cash
        current_holdings: list[str] = []

        # -- Output accumulators ---------------------------------------
        equity_curve_vals: list[float] = []
        date_index: list[pd.Timestamp] = []
        weights_by_ts: list[tuple[pd.Timestamp, dict[str, float]]] = []
        cash_records: list[float] = []
        holdings_records: list[list[str]] = []
        rebalance_events: list[dict] = []
        ticker_pnl: dict[str, float] = {}

        # -- Main simulation loop --------------------------------------
        for date in all_dates:
            ts = pd.Timestamp(date)

            # 1. Equity at the START of this day (before any action)
            equity = sum(holding_values.values()) + cash_value

            # 2. Monthly rebalance
            if ts in rebalance_dates:
                date_mask = fm["date"] == ts
                feature_rows = fm[date_mask].to_dict("records")
                new_holdings = self.select_top_n_assets(
                    feature_rows, current_holdings
                )

                prev_set = set(current_holdings)
                new_set = set(new_holdings)
                rebalance_events.append({
                    "date": ts,
                    "holdings_before": list(current_holdings),
                    "holdings_after": list(new_holdings),
                    "buys": sorted(new_set - prev_set),
                    "sells": sorted(prev_set - new_set),
                    "equity_at_rebalance": equity,
                    "old_weights": {
                        t: 1.0 / cfg.top_n for t in current_holdings
                    },
                    "new_weights": {
                        t: 1.0 / cfg.top_n for t in new_holdings
                    },
                })

                per_slot = equity / cfg.top_n
                holding_values = {t: per_slot for t in new_holdings}
                cash_value = equity * (cfg.top_n - len(new_holdings)) / cfg.top_n
                current_holdings = list(new_holdings)

            # 3. Record start-of-day equity
            equity_curve_vals.append(equity)
            date_index.append(ts)

            # 4. Record drifted weights, cash, and holdings for this date
            drifted: dict[str, float] = {}
            if equity > 0:
                for t in current_holdings:
                    drifted[t] = holding_values.get(t, 0.0) / equity
            weights_by_ts.append((ts, drifted))
            cash_records.append(cash_value)
            holdings_records.append(list(current_holdings))

            # 5. Apply daily returns (no fill; missing or invalid return raises)
            for t in current_holdings:
                if t not in returns_by_ticker:
                    raise ValueError(
                        f"Ticker {t!r} is selected but not in returns_by_ticker."
                    )
                ret_series = returns_by_ticker[t]
                if ts not in ret_series.index:
                    raise ValueError(
                        f"Return for {t!r} on {ts.date()} not found; "
                        "cannot fill missing returns."
                    )
                ret_val = float(ret_series.loc[ts])
                if math.isnan(ret_val) or math.isinf(ret_val):
                    raise ValueError(
                        f"Invalid return ({ret_val}) for {t!r} on {ts.date()}."
                    )
                pnl = holding_values[t] * ret_val
                holding_values[t] = holding_values[t] * (1.0 + ret_val)
                ticker_pnl[t] = ticker_pnl.get(t, 0.0) + pnl

            # 6. Cash return
            cash_value = cash_value * (1.0 + cfg.cash_return)

        # -- Post-loop computations ------------------------------------
        final_equity = sum(holding_values.values()) + cash_value
        initial_cash = cfg.initial_cash

        equity_series = pd.Series(
            equity_curve_vals, index=pd.DatetimeIndex(date_index),
            name="equity_curve",
        )

        strategy_total_return = (
            (final_equity / initial_cash) - 1.0
            if initial_cash != 0 else float("nan")
        )

        strategy_calmar = calculate_calmar(equity_series, cfg.annualization_days)

        # Cash series
        cash_series = pd.Series(
            cash_records, index=pd.DatetimeIndex(date_index), name="cash"
        )

        # Weights DataFrame: tickers as columns, dates as index
        all_held = sorted({t for _, dw in weights_by_ts for t in dw})
        if all_held:
            weights_matrix: dict[str, list[float]] = {t: [] for t in all_held}
            w_dates: list[pd.Timestamp] = []
            for ts_, dw in weights_by_ts:
                w_dates.append(ts_)
                for t in all_held:
                    weights_matrix[t].append(dw.get(t, 0.0))
            weights_df = pd.DataFrame(
                weights_matrix, index=pd.DatetimeIndex(w_dates)
            )
            weights_df.index.name = "date"
        else:
            weights_df = pd.DataFrame(
                index=pd.DatetimeIndex(date_index)
            )
            weights_df.index.name = "date"

        # Holdings by date
        holdings_by_date_out = {
            ts_: list(h)
            for ts_, h in zip(date_index, holdings_records)
        }

        # Per-ticker contribution to return (as % of initial_cash)
        per_ticker_contribution_pct = {
            t: (pnl / initial_cash) * 100.0
            for t, pnl in ticker_pnl.items()
        } if initial_cash != 0 else {}

        # Exposure pct: fraction of days with at least one holding, as %
        invested_days = sum(1 for h in holdings_records if len(h) > 0)
        total_days = len(date_index)
        exposure_pct = (
            (invested_days / total_days) * 100.0 if total_days > 0 else 0.0
        )

        diagnostics: dict[str, Any] = {
            "mode": "PRECOMPUTED_TOY_ROTATION_PATH",
            "research_valid": False,
            "market_data_used": False,
            "strategy_lab_runner_used": False,
            "live_go_emitted": False,
            "research_go_emitted": False,
            "v1_1_verdict_impact": "NONE",
            "n_rebalance_dates": len(rebalance_dates),
        }

        return RotationBacktesterResult(
            equity_curve=equity_series,
            rebalance_events=rebalance_events,
            per_ticker_contribution_pct=per_ticker_contribution_pct,
            exposure_pct=exposure_pct,
            final_equity=final_equity,
            strategy_total_return=strategy_total_return,
            strategy_calmar=strategy_calmar,
            v1_2_metric_sources=diagnostics,
            weights_by_date=weights_df,
            cash_by_date=cash_series,
            holdings_by_date=holdings_by_date_out,
        )
