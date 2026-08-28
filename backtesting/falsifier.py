from dataclasses import dataclass, field


@dataclass
class FalsifierConfig:
    min_total_trades: int = 30
    min_profit_factor: float = 1.2
    min_expectancy_R: float = 0.0
    max_ambiguous_exits_pct: float = 5.0
    require_calmar_above_benchmark: bool = True


class FalsifierEngine:
    """
    Skeptic gate: rejects backtests that fail statistical or quality thresholds.

    Principle: a strategy needs to PASS every check.
    One failure is enough for overall_pass = False.
    A superficially good expectancy/profit_factor on < 30 trades is FAIL.
    """

    def __init__(self, config: FalsifierConfig | None = None) -> None:
        self.config = config or FalsifierConfig()

    def evaluate(
        self,
        strategy_metrics: dict,
        benchmark_metrics: dict,
        total_trades: int,
        ambiguous_exits_pct: float,
    ) -> dict:
        """
        Returns
        -------
        dict with keys:
            overall_pass    : bool
            failure_reasons : list[str]
            warnings        : list[str]
            checks          : dict — per-check detail
        """
        cfg = self.config
        failure_reasons: list[str] = []
        warnings: list[str] = []
        checks: dict = {}

        # ------------------------------------------------------------------
        # Check 1: sample size
        # ------------------------------------------------------------------
        trades_pass = total_trades >= cfg.min_total_trades
        checks["sufficient_trades"] = {
            "pass": trades_pass,
            "value": total_trades,
            "required": cfg.min_total_trades,
        }
        if not trades_pass:
            failure_reasons.append(
                f"INSUFFICIENT_TRADES: total_trades={total_trades} < required={cfg.min_total_trades}"
            )

        # ------------------------------------------------------------------
        # Check 2: expectancy per trade R
        # ------------------------------------------------------------------
        exp_r = strategy_metrics.get("expectancy_per_trade_r")
        if exp_r is None:
            exp_pass = False
            failure_reasons.append("MISSING_EXPECTANCY: expectancy_per_trade_r not in metrics")
        else:
            exp_pass = exp_r > cfg.min_expectancy_R
            if not exp_pass:
                failure_reasons.append(
                    f"NEGATIVE_EXPECTANCY: expectancy_per_trade_r={exp_r:.3f} <= {cfg.min_expectancy_R}"
                )
        checks["positive_expectancy"] = {"pass": exp_pass, "value": exp_r}

        # ------------------------------------------------------------------
        # Check 3: profit factor
        # ------------------------------------------------------------------
        pf = strategy_metrics.get("profit_factor")
        if pf is None:
            pf_pass = False
            failure_reasons.append("MISSING_PROFIT_FACTOR")
        else:
            pf_pass = pf >= cfg.min_profit_factor
            if not pf_pass:
                failure_reasons.append(
                    f"LOW_PROFIT_FACTOR: profit_factor={pf:.3f} < required={cfg.min_profit_factor}"
                )
        checks["adequate_profit_factor"] = {"pass": pf_pass, "value": pf}

        # ------------------------------------------------------------------
        # Check 4: Calmar vs benchmark
        # ------------------------------------------------------------------
        if cfg.require_calmar_above_benchmark:
            s_calmar = strategy_metrics.get("calmar_ratio")
            b_calmar = benchmark_metrics.get("calmar_ratio")
            if s_calmar is None or b_calmar is None:
                calmar_pass = False
                failure_reasons.append("MISSING_CALMAR")
            else:
                calmar_pass = s_calmar >= b_calmar
                if not calmar_pass:
                    failure_reasons.append(
                        f"CALMAR_BELOW_BENCHMARK: strategy={s_calmar:.3f} < benchmark={b_calmar:.3f}"
                    )
            checks["calmar_above_benchmark"] = {
                "pass": calmar_pass,
                "strategy": s_calmar,
                "benchmark": b_calmar,
            }
        else:
            checks["calmar_above_benchmark"] = {"pass": True, "skipped": True}

        # ------------------------------------------------------------------
        # Check 5: ambiguous exits
        # ------------------------------------------------------------------
        amb_pass = ambiguous_exits_pct <= cfg.max_ambiguous_exits_pct
        checks["ambiguous_exits_below_threshold"] = {
            "pass": amb_pass,
            "value_pct": ambiguous_exits_pct,
            "max_pct": cfg.max_ambiguous_exits_pct,
        }
        if not amb_pass:
            failure_reasons.append(
                f"TOO_MANY_AMBIGUOUS_EXITS: {ambiguous_exits_pct:.1f}% > max {cfg.max_ambiguous_exits_pct}%"
            )

        # ------------------------------------------------------------------
        # Check 6: exposure-matched calmar (diagnostic only, non-blocking)
        # ------------------------------------------------------------------
        em_calmar = strategy_metrics.get("exposure_matched_calmar")
        if em_calmar is not None and em_calmar != float("inf"):
            s_calmar_v = strategy_metrics.get("calmar_ratio", 0) or 0
            em_pass = s_calmar_v >= em_calmar
            checks["exposure_matched_calmar"] = {
                "pass": em_pass,
                "diagnostic_only": True,
                "strategy_calmar": s_calmar_v,
                "exposure_matched_calmar": em_calmar,
            }
            status = "PASS" if em_pass else "FAIL"
            warnings.append(
                f"EXPOSURE_MATCHED_{status}: "
                f"strategy_calmar={s_calmar_v:.3f} vs exposure_matched_calmar={em_calmar:.3f}"
            )

        # ------------------------------------------------------------------
        # Warnings (non-blocking)
        # ------------------------------------------------------------------
        if trades_pass and total_trades < 50:
            warnings.append(
                f"LOW_TRADE_COUNT: {total_trades} trades passes minimum (30) "
                "but is below the 50-trade threshold for reliable statistics"
            )

        overall_pass = len(failure_reasons) == 0

        return {
            "overall_pass": overall_pass,
            "failure_reasons": failure_reasons,
            "warnings": warnings,
            "checks": checks,
        }
