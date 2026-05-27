import argparse
from pathlib import Path
import pandas as pd
import yfinance as yf


def fetch_and_save(ticker: str, start: str, end: str, output: str) -> None:
    df = yf.download(
        ticker,
        start=start,
        end=end,
        auto_adjust=False,  # pull raw Close + Adj Close; DataLoader handles adjustment
        progress=False,
    )

    if df.empty:
        raise ValueError(f"No data returned for {ticker} ({start} → {end})")

    # yfinance may return MultiIndex columns when fetching a single ticker
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adjusted_close",
            "Volume": "volume",
        }
    )

    df.index.name = "timestamp"
    df = df.reset_index()

    out_path = Path(output)
    df.to_csv(out_path, index=False)
    print(f"Fetched {len(df)} rows for {ticker} → {out_path.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch OHLCV data via yfinance")
    parser.add_argument("--ticker", required=True, help="Ticker symbol, e.g. QQQ")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--output", required=True, help="Output CSV path")
    args = parser.parse_args()

    fetch_and_save(
        ticker=args.ticker,
        start=args.start,
        end=args.end,
        output=args.output,
    )


if __name__ == "__main__":
    main()
