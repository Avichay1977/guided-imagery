"""
Randomized-selection comparator (p95) for RelativeStrengthRotation_v1.

This module implements the rotation-specific randomized comparator described
in spec §16. It is REPORT ONLY (v1_1_verdict_impact = "NONE").

Design contract (frozen by spec §16):
  - Same rebalance dates as the strategy.
  - Same N (top_n = 3) holdings per rebalance.
  - Same fixed universe and eligibility filters.
  - Asset selection randomized uniformly from the eligible set each rebalance.
  - Minimum 1000 simulations per split.
  - The 95th percentile of Calmar AND total_return across simulations.
  - The 75th percentile is not computed; the 95th is not aliased to any other.
  - Comparator is diagnostic only; never drives a live or research verdict.

No market-data-fetch library imported. No Backtester imported.
No runner imported. No live or research verdict tokens emitted anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from rotation_benchmark_b2 import calculate_calmar, calculate_total_return


# ---------------------------------------------------------------------------
# Config / Result
# ---------------------------------------------------------------------------

@dataclass
class RandomSelectionComparatorConfig:
    n_simulations: int = 1000
    random_seed: int = 42
    top_n: int = 3
    cash_return: float = 0.0
    annualization_days: int = 252
    comparator_label: str = "RANDOMIZED_SELECTION_P95_REPORT_ONLY"


@dataclass
class RandomSelectionComparatorResult:
    simulation_total_returns: list[float]
    simulation_calmars: list[float]
    p95_total_return: float
    p95_calmar: float
    n_simulations: int
    diagnostics: dict


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_random_selection_inputs(
    rebalance_dates,
    eligible_by_date: dict,
    returns_by_ticker: dict,
    strategy_holdings_by_date: Optional[dict] = None,
    config: Optional[RandomSelectionComparatorConfig] = None,
) -> None:
    """
    Validate structural inputs. Raises ValueError on any problem.

    Does NOT fetch or infer data. No fill of any kind.
    """
    if not rebalance_dates or len(list(rebalance_dates)) == 0:
        raise ValueError("rebalance_dates must not be empty.")
    if not isinstance(eligible_by_date, dict) or not eligible_by_date:
        raise ValueError("eligible_by_date must be a non-empty dict.")
    if not isinstance(returns_by_ticker, dict) or not returns_by_ticker:
        raise ValueError("returns_by_ticker must be a non-empty dict.")

    for d in rebalance_dates:
        key = pd.Timestamp(d)
        if key not in eligible_by_date and d not in eligible_by_date:
            raise ValueError(
                f"rebalance date {d} not found in eligible_by_date."
            )
        tickers = eligible_by_date.get(key, eligible_by_date.get(d, []))
        for t in tickers:
            if t not in returns_by_ticker:
                raise ValueError(
                    f"Eligible ticker {t!r} at {d} not found in returns_by_ticker."
                )

    if strategy_holdings_by_date is not None:
        for d in rebalance_dates:
            key = pd.Timestamp(d)
            if key not in strategy_holdings_by_date and d not in strategy_holdings_by_date:
                raise ValueError(
                    f"rebalance date {d} not found in strategy_holdings_by_date."
                )


# ---------------------------------------------------------------------------
# Random selection for one rebalance date
# ---------------------------------------------------------------------------

def select_random_holdings_for_date(
    eligible_tickers,
    target_count: int,
    rng: np.random.Generator,
) -> list[str]:
    """
    Randomly select up to target_count tickers from eligible_tickers.

    - Sort before sampling for deterministic base ordering.
    - Sample without replacement.
    - If eligible count < target_count, select all eligible (remainder = cash).
    - Never duplicates. Never selects outside the eligible set.
    """
    pool = sorted(eligible_tickers)
    n = min(target_count, len(pool))
    if n == 0:
        return []
    indices = rng.choice(len(pool), size=n, replace=False)
    return [pool[i] for i in sorted(indices)]


# ---------------------------------------------------------------------------
# Holdings path for one simulation
# ---------------------------------------------------------------------------

def build_random_holdings_path(
    rebalance_dates,
    eligible_by_date: dict,
    strategy_holdings_by_date: Optional[dict] = None,
    config: Optional[RandomSelectionComparatorConfig] = None,
    rng: Optional[np.random.Generator] = None,
) -> dict:
    """
    Build a dict of rebalance_date -> list[str] for one random simulation.

    Uses the same rebalance dates and eligible sets as the strategy.
    Mirrors the strategy's top_n count per date when strategy_holdings_by_date
    is provided; otherwise uses config.top_n.
    Empty slots (eligible < target) remain as cash implicitly.
    """
    cfg = config or RandomSelectionComparatorConfig()
    if rng is None:
        rng = np.random.default_rng(cfg.random_seed)

    result: dict = {}
    for d in rebalance_dates:
        key = pd.Timestamp(d)
        eligible = list(eligible_by_date.get(key, eligible_by_date.get(d, [])))

        if strategy_holdings_by_date is not None:
            strat = strategy_holdings_by_date.get(key, strategy_holdings_by_date.get(d, []))
            target = len(strat)
        else:
            target = cfg.top_n

        result[key] = select_random_holdings_for_date(eligible, target, rng)

    return result


# ---------------------------------------------------------------------------
# Portfolio return series for one holdings path
# ---------------------------------------------------------------------------

def compute_rotation_path_returns(
    holdings_by_date: dict,
    returns_by_ticker: dict,
    rebalance_dates,
    top_n: int = 3,
    cash_return: float = 0.0,
) -> pd.Series:
    """
    Compute daily portfolio return series from a holdings path.

    Weight per selected holding = 1/top_n (NOT 1/number_selected).
    Cash weight = 1 - len(holdings)/top_n.
    No leverage, no shorting, no daily rebalancing, no stops.
    Raises ValueError for missing return data.
    """
    sorted_dates = sorted(pd.Timestamp(d) for d in rebalance_dates)

    # Build a full daily date index from all return series
    all_dates: pd.Index = pd.Index([])
    for s in returns_by_ticker.values():
        all_dates = all_dates.union(s.index)
    all_dates = all_dates.sort_values()

    if len(all_dates) == 0:
        return pd.Series(dtype="float64")

    # Map each calendar day to its active rebalance holdings
    # A rebalance takes effect on its own date and holds until the next.
    def _holdings_for(date: pd.Timestamp) -> list[str]:
        active = None
        for rd in sorted_dates:
            if rd <= date:
                active = rd
            else:
                break
        if active is None:
            return []
        key = pd.Timestamp(active)
        return holdings_by_date.get(key, [])

    portfolio_returns: list[float] = []
    for date in all_dates:
        holdings = _holdings_for(date)
        n_held = len(holdings)
        weight_per_held = 1.0 / top_n
        cash_weight = 1.0 - n_held * weight_per_held

        daily_ret = cash_weight * cash_return
        for t in holdings:
            if t not in returns_by_ticker:
                raise ValueError(
                    f"Ticker {t!r} required by holdings but not in returns_by_ticker."
                )
            ret_series = returns_by_ticker[t]
            if date not in ret_series.index:
                raise ValueError(
                    f"Return for {t!r} on {date.date()} not found; cannot fill."
                )
            daily_ret += weight_per_held * float(ret_series.loc[date])

        portfolio_returns.append(daily_ret)

    return pd.Series(portfolio_returns, index=all_dates, name="random_sim_returns")


# ---------------------------------------------------------------------------
# Main comparator
# ---------------------------------------------------------------------------

def calculate_randomized_selection_p95(
    rebalance_dates,
    eligible_by_date: dict,
    returns_by_ticker: dict,
    strategy_holdings_by_date: Optional[dict] = None,
    config: Optional[RandomSelectionComparatorConfig] = None,
) -> RandomSelectionComparatorResult:
    """
    Run n_simulations randomized-selection paths and compute p95 metrics.

    p95_total_return = 95th percentile of simulation total returns.
    p95_calmar      = 95th percentile of simulation Calmars.

    Only the 95th-percentile values are computed and reported.
    No lower-percentile comparator is produced or aliased.

    Diagnostics mark this as report-only with v1_1_verdict_impact = "NONE".
    """
    cfg = config or RandomSelectionComparatorConfig()

    validate_random_selection_inputs(
        rebalance_dates, eligible_by_date, returns_by_ticker,
        strategy_holdings_by_date, cfg,
    )

    master_rng = np.random.default_rng(cfg.random_seed)

    sim_total_returns: list[float] = []
    sim_calmars: list[float] = []

    for _ in range(cfg.n_simulations):
        # Each simulation gets an independent child RNG derived from master
        child_rng = np.random.default_rng(master_rng.integers(0, 2**32))

        holdings = build_random_holdings_path(
            rebalance_dates=rebalance_dates,
            eligible_by_date=eligible_by_date,
            strategy_holdings_by_date=strategy_holdings_by_date,
            config=cfg,
            rng=child_rng,
        )

        ret_series = compute_rotation_path_returns(
            holdings_by_date=holdings,
            returns_by_ticker=returns_by_ticker,
            rebalance_dates=rebalance_dates,
            top_n=cfg.top_n,
            cash_return=cfg.cash_return,
        )

        # Convert daily returns to equity curve for metric computation
        equity = (1.0 + ret_series).cumprod()
        if len(equity) > 0:
            equity.iloc[0] = 1.0 + ret_series.iloc[0]  # already set, consistent

        tr = calculate_total_return(equity)
        cal = calculate_calmar(equity, cfg.annualization_days)

        sim_total_returns.append(tr)
        sim_calmars.append(cal if not np.isnan(cal) else 0.0)

    # 95th percentile — explicit, no aliasing to any other threshold
    p95_tr = float(np.nanpercentile(sim_total_returns, 95))
    p95_cal = float(np.nanpercentile(sim_calmars, 95))

    diagnostics = {
        "comparator_label": cfg.comparator_label,
        "n_simulations": cfg.n_simulations,
        "p95_threshold": 0.95,
        "report_only": True,
        "v1_1_verdict_impact": "NONE",
        "same_rebalance_dates": True,
        "same_universe": True,
        "same_eligibility_filters": True,
    }

    return RandomSelectionComparatorResult(
        simulation_total_returns=sim_total_returns,
        simulation_calmars=sim_calmars,
        p95_total_return=p95_tr,
        p95_calmar=p95_cal,
        n_simulations=cfg.n_simulations,
        diagnostics=diagnostics,
    )
