"""
Multi-Ticker Validator tests.

All tests use synthetic CSVs via fetch_fn injection — no real network calls.

Key invariants:
  - One ticker failure must not crash the run; error is recorded per-ticker
  - Output CSV contains all required columns
  - Falsifier failure reasons are preserved verbatim
  - PortfolioValidator applies all 8 GO criteria correctly
  - No dummy data is created when fetch fails
"""

import pandas as pd
import pytest
from pathlib import Path

from multi_ticker_runner import MultiTickerRunner, PortfolioValidator, TickerResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUIRED_COLUMNS = {
    "ticker", "status", "error",
    "rows_loaded", "rows_after_cleaning", "adjusted_ohlc_applied",
    "total_trades", "final_equity",
    "total_return_pct", "cagr_pct", "max_drawdown_pct",
    "sharpe_ratio", "calmar_ratio", "profit_factor",
    "expectancy_per_trade_R", "win_rate_pct", "ambiguous_exits_pct",
    "benchmark_cagr_pct", "benchmark_max_drawdown_pct",
    "benchmark_sharpe", "benchmark_calmar_ratio",
    "falsifier_pass", "falsifier_failure_reasons",
    "signal_count", "rows_reaching_min_score", "signal_rate_pct",
    "top_bottlenecks",
}


def _write_synthetic_csv(output_path: str, n_rows: int = 310) -> None:
    """Write minimal valid OHLCV CSV for pipeline testing."""
    dates = pd.date_range("2020-01-01", periods=n_rows, freq="B")
    prices = [100.0 + i * 0.05 for i in range(n_rows)]
    pd.DataFrame({
        "timestamp": dates.strftime("%Y-%m-%d"),
        "open": prices,
        "high": [p + 0.5 for p in prices],
        "low": [p - 0.5 for p in prices],
        "close": prices,
        "volume": [1_000_000.0] * n_rows,
    }).to_csv(output_path, index=False)


def _good_fetch(ticker: str, start: str, end: str, output: str) -> None:
    _write_synthetic_csv(output)


def _failing_fetch(ticker: str, start: str, end: str, output: str) -> None:
    raise ValueError(f"Simulated fetch failure for {ticker}")


def _selective_fetch(fail_tickers: set):
    def _fn(ticker, start, end, output):
        if ticker in fail_tickers:
            raise ValueError(f"Simulated failure: {ticker}")
        _write_synthetic_csv(output)
    return _fn


def _make_passing_result(ticker: str, trades: int = 40) -> TickerResult:
    """Create a TickerResult that passes the FalsifierEngine thresholds."""
    return TickerResult(
        ticker=ticker,
        status="OK",
        total_trades=trades,
        expectancy_per_trade_R=0.5,
        profit_factor=1.8,
        calmar_ratio=0.8,
        benchmark_calmar_ratio=0.5,
        ambiguous_exits_pct=0.0,
        falsifier_pass=True,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_runner_continues_when_one_ticker_fails(tmp_path):
    """
    A fetch failure on one ticker must not abort the run.
    The failed ticker records status=ERROR; the succeeding ticker records status=OK.
    """
    runner = MultiTickerRunner(fetch_fn=_selective_fetch({"FAIL"}))
    results, _ = runner.run_all(
        tickers=["GOOD", "FAIL"],
        start="2020-01-01",
        end="2024-12-31",
        adjust=False,
        output=str(tmp_path / "out.csv"),
        data_dir=tmp_path / "data",
    )

    assert len(results) == 2
    statuses = {r.ticker: r.status for r in results}
    assert statuses["GOOD"] == "OK"
    assert statuses["FAIL"] == "ERROR"
    assert "FAIL" in results[1].error or len(results[1].error) > 0


def test_summary_contains_required_columns(tmp_path):
    """Output CSV must contain all required columns."""
    out_csv = tmp_path / "summary.csv"
    runner = MultiTickerRunner(fetch_fn=_good_fetch)
    runner.run_all(
        tickers=["AAA", "BBB"],
        start="2020-01-01",
        end="2024-12-31",
        adjust=False,
        output=str(out_csv),
        data_dir=tmp_path / "data",
    )

    df = pd.read_csv(out_csv)
    missing = _REQUIRED_COLUMNS - set(df.columns)
    assert not missing, f"Output CSV missing columns: {missing}"


def test_falsifier_failure_reasons_are_recorded(tmp_path):
    """
    With synthetic data, total_trades will be very low (likely 0).
    The falsifier must record INSUFFICIENT_TRADES in failure_reasons.
    """
    runner = MultiTickerRunner(fetch_fn=_good_fetch)
    results, _ = runner.run_all(
        tickers=["SPY"],
        start="2020-01-01",
        end="2024-12-31",
        adjust=False,
        output=str(tmp_path / "out.csv"),
        data_dir=tmp_path / "data",
    )

    r = results[0]
    assert r.status == "OK"
    assert r.falsifier_pass is False
    assert "INSUFFICIENT_TRADES" in r.falsifier_failure_reasons


def test_portfolio_summary_counts_completed_and_failed_tickers(tmp_path):
    """tickers_completed and tickers_failed must sum to tickers_requested."""
    runner = MultiTickerRunner(fetch_fn=_selective_fetch({"FAIL1", "FAIL2"}))
    results, summary = runner.run_all(
        tickers=["OK1", "FAIL1", "OK2", "FAIL2"],
        start="2020-01-01",
        end="2024-12-31",
        adjust=False,
        output=str(tmp_path / "out.csv"),
        data_dir=tmp_path / "data",
    )

    assert summary["tickers_requested"] == 4
    assert summary["tickers_completed"] == 2
    assert summary["tickers_failed"] == 2
    assert summary["tickers_completed"] + summary["tickers_failed"] == summary["tickers_requested"]


def test_multi_ticker_no_go_when_total_trades_too_low():
    """
    PortfolioValidator must return NO-GO when total trades < 100.
    Tests the criterion directly with mock TickerResults.
    """
    results = [_make_passing_result(f"T{i}", trades=5) for i in range(8)]
    validator = PortfolioValidator()
    summary = validator.evaluate(results)

    assert summary["overall_verdict"] == "NO-GO"
    assert any("INSUFFICIENT_TOTAL_TRADES" in r for r in summary["failure_reasons"])


def test_multi_ticker_no_go_when_pass_rate_too_low():
    """
    If fewer than 60% of completed tickers have positive expectancy → NO-GO.
    """
    # 8 tickers, only 2 have positive expectancy (25%)
    results = [
        _make_passing_result(f"T{i}", trades=40) if i < 2
        else TickerResult(ticker=f"T{i}", status="OK", total_trades=40, expectancy_per_trade_R=-0.5)
        for i in range(8)
    ]
    summary = PortfolioValidator().evaluate(results)

    assert summary["overall_verdict"] == "NO-GO"
    assert any("LOW_POSITIVE_EXPECTANCY_RATE" in r for r in summary["failure_reasons"])


def test_multi_ticker_no_go_when_single_ticker_dominates_trades():
    """
    One ticker with 95% of all trades → TRADE_CONCENTRATION failure.
    """
    results = [
        _make_passing_result("DOMINANT", trades=950),
    ] + [_make_passing_result(f"T{i}", trades=5) for i in range(9)]

    summary = PortfolioValidator().evaluate(results)

    assert summary["overall_verdict"] == "NO-GO"
    assert any("TRADE_CONCENTRATION" in r for r in summary["failure_reasons"])


def test_multi_ticker_research_go_when_all_thresholds_pass():
    """
    8 tickers, all passing all criteria → overall_verdict = RESEARCH-GO.
    """
    results = [_make_passing_result(f"T{i}", trades=20) for i in range(8)]
    # Total trades = 160 ≥ 100 ✓
    # All have positive expectancy ✓
    # Median = 20 ≥ 10 ✓
    # avg PF = 1.8 ≥ 1.2 ✓
    # Calmar strategy=0.8 ≥ benchmark=0.5 ✓
    # Max concentration = 12.5% ≤ 40% ✓
    # Ambiguous = 0% < 5% ✓
    # Completed = 8 ≥ 6 ✓

    summary = PortfolioValidator().evaluate(results)

    assert summary["overall_verdict"] == "RESEARCH-GO", (
        f"Expected RESEARCH-GO, got NO-GO. Failures: {summary['failure_reasons']}"
    )
    assert summary["overall_pass"] is True


def test_runner_does_not_create_dummy_data_on_fetch_failure(tmp_path):
    """
    When fetch fails, the error is recorded but no CSV file is created.
    No fake data is silently substituted.
    """
    data_dir = tmp_path / "data"
    runner = MultiTickerRunner(fetch_fn=_failing_fetch)
    results, _ = runner.run_all(
        tickers=["SPY"],
        start="2020-01-01",
        end="2024-12-31",
        adjust=False,
        output=str(tmp_path / "out.csv"),
        data_dir=data_dir,
    )

    r = results[0]
    assert r.status == "ERROR", "Failed fetch must produce status=ERROR"
    assert len(r.error) > 0, "Error message must be recorded"

    # No CSV with fake data should exist
    expected_csv = data_dir / "SPY_2020-01-01_2024-12-31.csv"
    assert not expected_csv.exists(), (
        "Fetch failure must not leave a dummy CSV at the data path"
    )
