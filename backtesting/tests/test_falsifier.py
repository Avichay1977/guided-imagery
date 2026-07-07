"""
FalsifierEngine tests.

Core invariant:
  total_trades < min_total_trades → overall_pass is False,
  even if expectancy, profit_factor, and Calmar all look excellent.

One failure reason is enough for overall_pass = False.
"""

import pytest

from falsifier import FalsifierEngine, FalsifierConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GOOD_STRATEGY = {
    "expectancy_per_trade_r": 1.5,
    "profit_factor": 3.0,
    "calmar_ratio": 1.2,
}

_GOOD_BENCHMARK = {
    "calmar_ratio": 0.55,
}


def _run(
    strategy: dict | None = None,
    benchmark: dict | None = None,
    total_trades: int = 50,
    ambiguous_pct: float = 0.0,
    config: FalsifierConfig | None = None,
) -> dict:
    engine = FalsifierEngine(config=config)
    return engine.evaluate(
        strategy_metrics=strategy or _GOOD_STRATEGY,
        benchmark_metrics=benchmark or _GOOD_BENCHMARK,
        total_trades=total_trades,
        ambiguous_exits_pct=ambiguous_pct,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_falsifier_rejects_insufficient_trades():
    """
    3 trades — even with stellar expectancy, profit_factor, and Calmar —
    must produce overall_pass=False with INSUFFICIENT_TRADES in failure_reasons.

    This is the primary regression this module was built to catch:
    the QQQ baseline sanity run had 3 trades and superficially good metrics.
    """
    result = _run(total_trades=3)

    assert result["overall_pass"] is False
    reasons = result["failure_reasons"]
    assert any("INSUFFICIENT_TRADES" in r for r in reasons), (
        f"Expected INSUFFICIENT_TRADES in failure_reasons, got: {reasons}"
    )


def test_falsifier_accepts_valid_metrics():
    """
    50 trades + positive expectancy + profit_factor ≥ 1.2 +
    calmar ≥ benchmark + 0% ambiguous → overall_pass must be True.
    """
    result = _run(total_trades=50)

    assert result["overall_pass"] is True
    assert result["failure_reasons"] == []


def test_falsifier_rejects_negative_expectancy():
    """
    expectancy_per_trade_r ≤ 0 → FAIL even with 50 trades.
    """
    result = _run(
        strategy={**_GOOD_STRATEGY, "expectancy_per_trade_r": -0.1},
        total_trades=50,
    )

    assert result["overall_pass"] is False
    assert any("NEGATIVE_EXPECTANCY" in r for r in result["failure_reasons"])


def test_falsifier_rejects_zero_expectancy():
    """
    expectancy_per_trade_r == 0.0 is not strictly > 0 → FAIL.
    """
    result = _run(
        strategy={**_GOOD_STRATEGY, "expectancy_per_trade_r": 0.0},
        total_trades=50,
    )

    assert result["overall_pass"] is False
    assert any("NEGATIVE_EXPECTANCY" in r for r in result["failure_reasons"])


def test_falsifier_rejects_low_profit_factor():
    """
    profit_factor < 1.2 → FAIL even with 50 trades and good expectancy.
    """
    result = _run(
        strategy={**_GOOD_STRATEGY, "profit_factor": 1.1},
        total_trades=50,
    )

    assert result["overall_pass"] is False
    assert any("LOW_PROFIT_FACTOR" in r for r in result["failure_reasons"])


def test_falsifier_rejects_calmar_below_benchmark():
    """
    strategy Calmar below benchmark Calmar → FAIL.
    """
    result = _run(
        strategy={**_GOOD_STRATEGY, "calmar_ratio": 0.3},
        benchmark={"calmar_ratio": 0.55},
        total_trades=50,
    )

    assert result["overall_pass"] is False
    assert any("CALMAR_BELOW_BENCHMARK" in r for r in result["failure_reasons"])


def test_falsifier_rejects_too_many_ambiguous_exits():
    """
    ambiguous_exits_pct > max_ambiguous_exits_pct → FAIL.
    """
    result = _run(total_trades=50, ambiguous_pct=6.0)

    assert result["overall_pass"] is False
    assert any("TOO_MANY_AMBIGUOUS_EXITS" in r for r in result["failure_reasons"])


def test_checks_dict_contains_all_keys():
    """evaluate() must always return all five check keys."""
    result = _run()
    expected_keys = {
        "sufficient_trades",
        "positive_expectancy",
        "adequate_profit_factor",
        "calmar_above_benchmark",
        "ambiguous_exits_below_threshold",
    }
    assert expected_keys.issubset(result["checks"].keys())


def test_insufficient_trades_overrides_good_metrics():
    """
    Regression: even when ALL metric checks pass individually,
    trade count below threshold must force overall_pass=False.
    """
    result = _run(
        strategy={
            "expectancy_per_trade_r": 99.0,
            "profit_factor": 99.0,
            "calmar_ratio": 99.0,
        },
        total_trades=1,
    )

    assert result["overall_pass"] is False
    assert result["checks"]["sufficient_trades"]["pass"] is False


def test_warning_issued_for_low_but_passing_trade_count():
    """
    30 trades passes the minimum threshold but should trigger a warning
    about borderline sample size (below the 50-trade reliable zone).
    """
    result = _run(total_trades=30)

    assert result["overall_pass"] is True
    assert any("LOW_TRADE_COUNT" in w for w in result["warnings"])


def test_calmar_check_skipped_when_not_required():
    """
    require_calmar_above_benchmark=False: the check is skipped and
    a strategy with calmar below benchmark still passes.
    """
    config = FalsifierConfig(require_calmar_above_benchmark=False)
    result = _run(
        strategy={**_GOOD_STRATEGY, "calmar_ratio": 0.1},
        benchmark={"calmar_ratio": 0.9},
        total_trades=50,
        config=config,
    )

    assert result["overall_pass"] is True
    assert result["checks"]["calmar_above_benchmark"].get("skipped") is True
