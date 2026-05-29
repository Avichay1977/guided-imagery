"""
Multi-ticker run using public GitHub data sources (yfinance blocked in this env).

Data sources (real historical OHLCV, not synthetic):
  - taeheon-kong/etf-app  → SPY QQQ IWM XLK XLF XLE TLT GLD
  - fja05680/brownbear    → DIA

Runs via MultiTickerRunner with an injected fetch_fn so no yfinance is needed.
"""

import io
import urllib.request
import pandas as pd
from pathlib import Path

from multi_ticker_runner import MultiTickerRunner, _print_portfolio_summary

# ---------------------------------------------------------------------------
# Data-source config
# ---------------------------------------------------------------------------

_TAEHEON_BASE = "https://raw.githubusercontent.com/taeheon-kong/etf-app/main/data/raw"
_BROWNBEAR_BASE = "https://raw.githubusercontent.com/fja05680/brownbear/master/symbol-cache"

_TAEHEON_TICKERS = {"SPY", "QQQ", "IWM", "XLK", "XLF", "XLE", "TLT", "GLD"}
_BROWNBEAR_TICKERS = {"DIA"}


def _fetch_taeheon(ticker: str) -> pd.DataFrame:
    url = f"{_TAEHEON_BASE}/{ticker}.csv"
    with urllib.request.urlopen(url, timeout=30) as r:
        raw = r.read().decode()
    df = pd.read_csv(io.StringIO(raw))
    df = df.rename(columns={
        "Date": "timestamp",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "AdjClose": "adjusted_close",
        "Volume": "volume",
    })
    return df[["timestamp", "open", "high", "low", "close", "volume", "adjusted_close"]]


def _fetch_brownbear(ticker: str) -> pd.DataFrame:
    url = f"{_BROWNBEAR_BASE}/{ticker}.csv"
    with urllib.request.urlopen(url, timeout=30) as r:
        raw = r.read().decode()
    df = pd.read_csv(io.StringIO(raw))
    df = df.rename(columns={
        "Date": "timestamp",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adjusted_close",
        "Volume": "volume",
    })
    return df[["timestamp", "open", "high", "low", "close", "volume", "adjusted_close"]]


def github_fetch_fn(ticker: str, start: str, end: str, output: str) -> None:
    """Fetch from GitHub, filter to [start, end], save to output CSV."""
    if ticker in _TAEHEON_TICKERS:
        df = _fetch_taeheon(ticker)
    elif ticker in _BROWNBEAR_TICKERS:
        df = _fetch_brownbear(ticker)
    else:
        raise ValueError(f"No GitHub data source configured for {ticker}")

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df[(df["timestamp"] >= start) & (df["timestamp"] <= end)].copy()
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d")

    if df.empty:
        raise ValueError(f"No rows in [{start}, {end}] for {ticker}")

    df.to_csv(output, index=False)
    print(f"  fetched {len(df)} rows from GitHub → {output}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tickers = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "TLT", "GLD"]
    start = "2020-01-01"
    end = "2024-12-31"
    output = "multi_ticker_summary.csv"

    runner = MultiTickerRunner(fetch_fn=github_fetch_fn)
    results, summary = runner.run_all(
        tickers=tickers,
        start=start,
        end=end,
        adjust=True,
        output=output,
        data_dir=Path("data"),
    )

    _print_portfolio_summary(summary)
