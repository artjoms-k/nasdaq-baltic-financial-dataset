"""
02_fetch_prices.py — Download historical stock prices from Yahoo Finance
Nasdaq Baltic Financial Dataset
"""

import pandas as pd
import yfinance as yf
from pathlib import Path

DATA_PATH = Path("data")
meta = pd.read_csv(DATA_PATH / "companies_meta.csv")

all_prices = []
failed = []

for _, row in meta.iterrows():
    yticker = row["yahoo_ticker"]
    ticker = row["ticker"]
    print(f"Fetching {ticker} ({yticker})...", end=" ")

    try:
        data = yf.download(yticker, period="3y", progress=False, auto_adjust=True)
        if data.empty:
            print("NO DATA")
            failed.append(ticker)
            continue

        data = data.reset_index()
        # Handle both single and multi-level column names from yfinance
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [c[0] if c[1] == '' else c[0] for c in data.columns]

        data["ticker"] = ticker
        data = data.rename(columns={
            "Date": "date", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume"
        })
        data = data[["ticker", "date", "open", "high", "low", "close", "volume"]]
        data["date"] = pd.to_datetime(data["date"]).dt.strftime("%Y-%m-%d")
        all_prices.append(data)
        print(f"OK ({len(data)} rows)")
    except Exception as e:
        print(f"ERROR: {e}")
        failed.append(ticker)

if all_prices:
    prices_df = pd.concat(all_prices, ignore_index=True)
    prices_df.to_csv(DATA_PATH / "stock_prices.csv", index=False)
    print(f"\nSaved {len(prices_df)} price records to data/stock_prices.csv")

if failed:
    print(f"\nFailed tickers ({len(failed)}): {', '.join(failed)}")

print("\nDone.")
