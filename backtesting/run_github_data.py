"""
Multi-ticker run using public GitHub data sources (yfinance blocked in this env).

Data sources (real historical OHLCV, not synthetic):
  - taeheon-kong/etf-app                                  → ETF universe
  - fja05680/brownbear                                     → DIA
  - sathya-rajesh-asokan/machine-learning-final-project   → individual stocks

Run modes (set RUN_MODE below):
  "etfs"   — SPY QQQ IWM DIA XLK XLF XLE TLT GLD
  "stocks" — AAPL MSFT NVDA META GOOGL AMZN JPM SNOW PLTR
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
_SATHYA_BASE = "https://raw.githubusercontent.com/sathya-rajesh-asokan/machine-learning-final-project/main/data/prices/backtest"
_SATHYA_ANALYSIS_BASE = "https://raw.githubusercontent.com/sathya-rajesh-asokan/machine-learning-final-project/main/data/prices/analysis"

_TAEHEON_TICKERS = {"SPY", "QQQ", "IWM", "XLK", "XLF", "XLE", "TLT", "GLD"}
_BROWNBEAR_TICKERS = {"DIA"}
_SATHYA_TICKERS = {
    "AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "JPM", "SNOW", "PLTR",
    "CRWD", "V", "COST", "WMT", "XOM", "JNJ",
    "AXON", "ANET", "APO", "WAL", "ORCL", "GOOG", "GE", "WDAY",
}
# Tickers available in BOTH analysis (2009-2019) + backtest (2020-2025) dirs
_SATHYA_COMBINED_TICKERS = {"AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "JPM",
                              "AXON", "ANET", "APO", "WAL", "ORCL"}


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


def _fetch_sathya(ticker: str) -> pd.DataFrame:
    url = f"{_SATHYA_BASE}/{ticker}.csv"
    with urllib.request.urlopen(url, timeout=30) as r:
        raw = r.read().decode()
    df = pd.read_csv(io.StringIO(raw))
    df = df.rename(columns={
        "date": "timestamp",
        "adjClose": "adjusted_close",
    })
    return df[["timestamp", "open", "high", "low", "close", "volume", "adjusted_close"]]


def _fetch_sathya_combined(ticker: str) -> pd.DataFrame:
    """Merge analysis (2009-2019) + backtest (2020-2025) into one DataFrame."""
    dfs = []
    for base in [_SATHYA_ANALYSIS_BASE, _SATHYA_BASE]:
        url = f"{base}/{ticker}.csv"
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                raw = r.read().decode()
            df = pd.read_csv(io.StringIO(raw))
            df = df.rename(columns={"date": "timestamp", "adjClose": "adjusted_close"})
            df = df[["timestamp", "open", "high", "low", "close", "volume", "adjusted_close"]]
            dfs.append(df)
        except Exception:
            pass
    if not dfs:
        raise ValueError(f"No data found for {ticker}")
    combined = pd.concat(dfs).drop_duplicates(subset="timestamp").sort_values("timestamp")
    return combined.reset_index(drop=True)


def github_fetch_fn(ticker: str, start: str, end: str, output: str) -> None:
    """Fetch from GitHub, filter to [start, end], save to output CSV."""
    if ticker in _TAEHEON_TICKERS:
        df = _fetch_taeheon(ticker)
    elif ticker in _BROWNBEAR_TICKERS:
        df = _fetch_brownbear(ticker)
    elif ticker in _SATHYA_COMBINED_TICKERS:
        df = _fetch_sathya_combined(ticker)
    elif ticker in _SATHYA_TICKERS:
        df = _fetch_sathya(ticker)
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

_UNIVERSES = {
    "etfs":   ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "TLT", "GLD"],
    "stocks": ["AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "JPM", "SNOW", "PLTR"],
    "stocks15": [
        "AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "JPM", "SNOW", "PLTR",
        "CRWD", "V", "COST", "WMT", "XOM", "JNJ",
    ],
    "momentum15": [
        # High-signal momentum stocks — swap lowest-signal ETF proxies for breakout names
        "AAPL", "MSFT", "NVDA", "META", "AMZN", "GOOGL",
        "JPM", "WMT", "PLTR", "CRWD",
        "AXON", "ANET", "APO", "WAL", "ORCL",
    ],
    "momentum10y": [
        # Same universe, 2015-2024 (10 years) — analysis+backtest combined
        # Includes 2018 crash + COVID crash to normalize benchmark calmar
        "AAPL", "MSFT", "NVDA", "META", "AMZN", "GOOGL",
        "JPM", "AXON", "ANET", "APO", "WAL", "ORCL",
    ],
}

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "stocks"
    tickers = _UNIVERSES[mode]
    start = "2015-01-01" if mode == "momentum10y" else "2020-01-01"
    end = "2024-12-31"
    output = f"multi_ticker_summary_{mode}.csv"

    print(f"\nUniverse: {mode.upper()} — {tickers}")
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
