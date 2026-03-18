"""
01_create_db.py — Load CSV data into SQLite database
Nasdaq Baltic Financial Dataset
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("db/nasdaq_baltic.db")
DATA_PATH = Path("data")

DB_PATH.parent.mkdir(exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# --- Create tables ---

cursor.execute("""
CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    isin TEXT,
    country TEXT NOT NULL,       -- EE, LV, LT
    exchange TEXT NOT NULL,      -- TLN, RIG, VLN
    sector TEXT,
    list_type TEXT,              -- Main, Secondary, FirstNorth
    yahoo_ticker TEXT,
    status TEXT DEFAULT 'active' -- active, delisted
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS financials (
    ticker TEXT NOT NULL,
    year INTEGER NOT NULL,
    revenue_eur_m REAL,             -- in EUR millions
    net_income_eur_m REAL,
    total_assets_eur_m REAL,
    total_equity_eur_m REAL,
    total_liabilities_eur_m REAL,
    shares_outstanding_m REAL,      -- in millions
    dividends_per_share_eur REAL,
    PRIMARY KEY (ticker, year),
    FOREIGN KEY (ticker) REFERENCES companies(ticker)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS stock_prices (
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    PRIMARY KEY (ticker, date),
    FOREIGN KEY (ticker) REFERENCES companies(ticker)
)
""")

# --- Load company metadata ---

meta = pd.read_csv(DATA_PATH / "companies_meta.csv")
meta.to_sql("companies", conn, if_exists="replace", index=False)
print(f"Loaded {len(meta)} companies into 'companies' table")

# --- Load financial data ---

fin_path = DATA_PATH / "financials.csv"
if fin_path.exists():
    fin = pd.read_csv(fin_path)
    fin = fin.dropna(subset=["revenue_eur_m"])  # skip empty rows
    fin.to_sql("financials", conn, if_exists="replace", index=False)
    print(f"Loaded {len(fin)} financial records into 'financials' table")
else:
    print("WARNING: data/financials.csv not found. Copy financials_template.csv, fill in data, and save as financials.csv")

# --- Load stock prices (if fetched) ---

prices_path = DATA_PATH / "stock_prices.csv"
if prices_path.exists():
    prices = pd.read_csv(prices_path)
    prices.to_sql("stock_prices", conn, if_exists="replace", index=False)
    print(f"Loaded {len(prices)} price records into 'stock_prices' table")
else:
    print("INFO: No stock_prices.csv found.")

conn.commit()
conn.close()
print(f"\nDatabase created: {DB_PATH}")
