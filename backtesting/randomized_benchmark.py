"""
Randomized Timing Benchmark Engine v1

Falsification test: does the strategy's entry timing add value beyond
random participation?

Generates N random trade schedules with the same trade count and (optionally)
the same holding durations as the real strategy, then compares the real
strategy's calmar and total return against that distribution.

Pass criterion: real_calmar > p75 of random AND real_total_return > p75 of random.

Diagnostic only. Not a trading recommendation.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class RandomizedBenchmarkConfig:
    n_simulations: int = 1000
    random_seed: int = 42
    min_required_trades: int = 5
    preserve_holding_periods: bool = True
    allow_overlap: bool = False


class RandomizedTimingBenchmarkEngine:
    """
    Tests market-timing skill by comparing the real strategy calmar and total
    return against the distribution from N random entry schedules that share
    the same trade count and holding durations.

    Pass: real_calmar > p75_random AND real_return > p75_random.
    """

    def __init__(self, config: Optional[RandomizedBenchmarkConfig] = None) -> None:
        self.config = config or RandomizedBenchmarkConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        df: pd.DataFrame,
        trades: list[dict],
        initial_cash: float,
        strategy_metrics: dict,
    ) -> dict:
        """
        Parameters
        ----------
        df              : cleaned DataFrame with DatetimeIndex and 'close' column
        trades          : list of real strategy trade dicts (from Backtester)
        initial_cash    : starting capital (float)
        strategy_metrics: output of MetricsEngine.calculate_all()

        Returns
        -------
        dict with all required output fields (see Required output per ticker in spec)
        """
        cfg = self.config
        n_trades = len(trades)

        if n_trades < cfg.min_required_trades:
            return self._insufficient_result(n_trades, strategy_metrics)

        closes = df["close"].values.astype(float)
        n_bars = len(closes)
        date_to_idx: dict = {d: i for i, d in enumerate(df.index)}

        holding_periods = self._extract_holding_periods(trades, date_to_idx, n_bars)
        position_fractions = self._extract_position_fractions(trades, initial_cash)
        avg_pf = float(np.mean(position_fractions))

        rng = np.random.default_rng(cfg.random_seed)
        hp_arr = np.array(holding_periods, dtype=int)

        sim_returns: list[float] = []
        sim_calmars: list[float] = []
        sim_mdd: list[float] = []

        for _ in range(cfg.n_simulations):
            schedule = self._generate_schedule(n_bars, n_trades, hp_arr, rng)
            if schedule is None:
                continue
            eq = self._build_equity(closes, schedule, initial_cash, avg_pf)
            m = self._compute_metrics(eq, n_bars)
            sim_returns.append(m["total_return"])
            sim_calmars.append(m["calmar"])
            sim_mdd.append(m["max_drawdown"])

        n_completed = len(sim_returns)

        if n_completed < 10:
            return {
                "status": "FAIL",
                "real_total_trades": n_trades,
                "n_simulations": cfg.n_simulations,
                "n_simulations_completed": n_completed,
                "real_total_return_pct": round(float(strategy_metrics.get("total_return_pct", 0.0) or 0.0), 2),
                "random_median_total_return_pct": None,
                "random_p75_total_return_pct": None,
                "random_p90_total_return_pct": None,
                "real_calmar": round(float(strategy_metrics.get("calmar_ratio", 0.0) or 0.0), 3),
                "random_median_calmar": None,
                "random_p75_calmar": None,
                "random_p90_calmar": None,
                "real_max_drawdown_pct": round(float(strategy_metrics.get("max_drawdown_pct", 0.0) or 0.0), 2),
                "random_median_max_drawdown_pct": None,
                "timing_edge_percentile_return": None,
                "timing_edge_percentile_calmar": None,
                "beats_random_median_return": False,
                "beats_random_p75_return": False,
                "beats_random_median_calmar": False,
                "beats_random_p75_calmar": False,
                "randomized_timing_pass": False,
                "failure_reasons": [f"TOO_FEW_VALID_SIMULATIONS: {n_completed}/{cfg.n_simulations}"],
            }

        # Real strategy metrics
        real_return = float(strategy_metrics.get("total_return_pct", 0.0) or 0.0)
        real_calmar = float(strategy_metrics.get("calmar_ratio", 0.0) or 0.0)
        real_mdd = float(strategy_metrics.get("max_drawdown_pct", 0.0) or 0.0)

        # Distribution statistics
        arr_r = np.array(sim_returns)
        arr_c = np.array([c for c in sim_calmars if np.isfinite(c)])
        arr_m = np.array(sim_mdd)

        med_r = float(np.median(arr_r))
        p75_r = float(np.percentile(arr_r, 75))
        p90_r = float(np.percentile(arr_r, 90))

        if len(arr_c) > 0:
            med_c = float(np.median(arr_c))
            p75_c = float(np.percentile(arr_c, 75))
            p90_c = float(np.percentile(arr_c, 90))
            edge_c = float((arr_c < real_calmar).mean() * 100)
        else:
            med_c = p75_c = p90_c = edge_c = 0.0

        med_m = float(np.median(arr_m))
        edge_r = float((arr_r < real_return).mean() * 100)

        beats_median_r = bool(real_return > med_r)
        beats_p75_r = bool(real_return > p75_r)
        beats_median_c = bool(real_calmar > med_c)
        beats_p75_c = bool(real_calmar > p75_c)

        randomized_timing_pass = beats_p75_c and beats_p75_r

        failure_reasons: list[str] = []
        if not beats_p75_c:
            failure_reasons.append(
                f"CALMAR_NOT_ABOVE_P75_RANDOM: real={real_calmar:.3f} <= p75={p75_c:.3f}"
            )
        if not beats_p75_r:
            failure_reasons.append(
                f"RETURN_NOT_ABOVE_P75_RANDOM: real={real_return:.1f}% <= p75={p75_r:.1f}%"
            )

        return {
            "status": "OK",
            "real_total_trades": n_trades,
            "n_simulations": cfg.n_simulations,
            "n_simulations_completed": n_completed,
            "real_total_return_pct": round(real_return, 2),
            "random_median_total_return_pct": round(med_r, 2),
            "random_p75_total_return_pct": round(p75_r, 2),
            "random_p90_total_return_pct": round(p90_r, 2),
            "real_calmar": round(real_calmar, 3),
            "random_median_calmar": round(med_c, 3),
            "random_p75_calmar": round(p75_c, 3),
            "random_p90_calmar": round(p90_c, 3),
            "real_max_drawdown_pct": round(real_mdd, 2),
            "random_median_max_drawdown_pct": round(med_m, 2),
            "timing_edge_percentile_return": round(edge_r, 1),
            "timing_edge_percentile_calmar": round(edge_c, 1),
            "beats_random_median_return": beats_median_r,
            "beats_random_p75_return": beats_p75_r,
            "beats_random_median_calmar": beats_median_c,
            "beats_random_p75_calmar": beats_p75_c,
            "randomized_timing_pass": randomized_timing_pass,
            "failure_reasons": failure_reasons,
        }

    # ------------------------------------------------------------------
    # Helpers: input extraction
    # ------------------------------------------------------------------

    def _insufficient_result(self, n_trades: int, strategy_metrics: dict) -> dict:
        return {
            "status": "INSUFFICIENT_TRADES_FOR_RANDOMIZATION",
            "real_total_trades": n_trades,
            "n_simulations": 0,
            "n_simulations_completed": 0,
            "real_total_return_pct": round(float(strategy_metrics.get("total_return_pct", 0.0) or 0.0), 2),
            "random_median_total_return_pct": None,
            "random_p75_total_return_pct": None,
            "random_p90_total_return_pct": None,
            "real_calmar": round(float(strategy_metrics.get("calmar_ratio", 0.0) or 0.0), 3),
            "random_median_calmar": None,
            "random_p75_calmar": None,
            "random_p90_calmar": None,
            "real_max_drawdown_pct": round(float(strategy_metrics.get("max_drawdown_pct", 0.0) or 0.0), 2),
            "random_median_max_drawdown_pct": None,
            "timing_edge_percentile_return": None,
            "timing_edge_percentile_calmar": None,
            "beats_random_median_return": False,
            "beats_random_p75_return": False,
            "beats_random_median_calmar": False,
            "beats_random_p75_calmar": False,
            "randomized_timing_pass": False,
            "failure_reasons": ["INSUFFICIENT_TRADES_FOR_RANDOMIZATION"],
        }

    def _extract_holding_periods(
        self, trades: list[dict], date_to_idx: dict, n_bars: int
    ) -> list[int]:
        periods = []
        for t in trades:
            entry = pd.Timestamp(t["entry_time"]).normalize()
            exit_ = pd.Timestamp(t["exit_time"]).normalize()
            ei = date_to_idx.get(entry, 0)
            xi = date_to_idx.get(exit_, ei + 1)
            periods.append(max(xi - ei, 1))
        return periods or [5]

    def _extract_position_fractions(
        self, trades: list[dict], initial_cash: float
    ) -> list[float]:
        fracs = []
        for t in trades:
            if "shares" in t and "entry_price" in t and initial_cash > 0:
                frac = t["shares"] * t["entry_price"] / initial_cash
                fracs.append(min(max(float(frac), 0.01), 1.0))
        return fracs or [0.25]

    # ------------------------------------------------------------------
    # Helpers: simulation
    # ------------------------------------------------------------------

    def _generate_schedule(
        self,
        n_bars: int,
        n_trades: int,
        hp_arr: np.ndarray,
        rng: np.random.Generator,
    ) -> list[tuple] | None:
        # Stratified sampling: divide timeline into n_trades equal slots and pick
        # one random entry per slot. This guarantees n_trades can always be placed
        # regardless of individual holding periods.
        slot_size = n_bars // n_trades
        if slot_size < 2:
            return None

        schedule: list[tuple] = []
        for i in range(n_trades):
            slot_start = i * slot_size
            next_slot = (i + 1) * slot_size
            slot_end = min(next_slot, n_bars) - 1

            if slot_start >= slot_end:
                continue

            entry_i = int(rng.integers(slot_start, slot_end))
            hp = (
                int(rng.choice(hp_arr))
                if self.config.preserve_holding_periods
                else int(round(float(hp_arr.mean())))
            )

            if self.config.allow_overlap:
                exit_i = min(entry_i + hp, n_bars - 1)
            else:
                exit_i = min(entry_i + hp, next_slot - 1, n_bars - 1)

            if exit_i <= entry_i:
                exit_i = min(entry_i + 1, n_bars - 1)

            schedule.append((entry_i, exit_i))

        return schedule if len(schedule) >= self.config.min_required_trades else None

    def _build_equity(
        self,
        closes: np.ndarray,
        schedule: list[tuple],
        initial_cash: float,
        avg_pf: float,
    ) -> np.ndarray:
        n = len(closes)
        equity = np.full(n, initial_cash, dtype=float)
        current = float(initial_cash)
        prev_end = 0

        for entry_i, exit_i in sorted(schedule, key=lambda x: x[0]):
            equity[prev_end:entry_i] = current
            if exit_i > entry_i:
                ratios = closes[entry_i : exit_i + 1] / closes[entry_i]
                equity[entry_i : exit_i + 1] = (
                    current * (1.0 - avg_pf) + current * avg_pf * ratios
                )
            else:
                equity[entry_i] = current
            current = float(equity[exit_i])
            prev_end = exit_i + 1

        equity[prev_end:] = current
        return equity

    def _compute_metrics(self, equity: np.ndarray, n_bars: int) -> dict:
        if equity[0] <= 0 or len(equity) < 2:
            return {"total_return": 0.0, "calmar": 0.0, "max_drawdown": 0.0}

        total_return = (equity[-1] / equity[0] - 1.0) * 100.0

        peak = np.maximum.accumulate(equity)
        with np.errstate(divide="ignore", invalid="ignore"):
            dd = np.where(peak > 0, (peak - equity) / peak, 0.0)
        max_dd = float(dd.max())

        dur = (n_bars - 1) / 252.0 if n_bars > 1 else 1.0
        cagr = (equity[-1] / equity[0]) ** (1.0 / dur) - 1.0 if dur > 0 else 0.0

        if max_dd > 0:
            calmar = cagr / max_dd
        elif cagr > 0:
            calmar = float("inf")
        else:
            calmar = 0.0

        return {
            "total_return": total_return,
            "calmar": calmar,
            "max_drawdown": max_dd * 100.0,
        }
