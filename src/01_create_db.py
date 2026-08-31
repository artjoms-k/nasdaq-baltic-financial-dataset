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
    currency TEXT,
    country TEXT NOT NULL,       -- EE, LV, LT
    exchange TEXT NOT NULL,      -- TLN, RIG, VLN
    industry TEXT,
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
    source TEXT,                    -- ESEF filing, or the fact sheet it came from
    source_url TEXT,                -- link to the filing, where there is one
    retrieved_date TEXT,
    notes TEXT,                     -- what in this row is derived rather than reported
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

STATEMENT_FIELDS = [
    "revenue_eur_m",
    "net_income_eur_m",
    "total_assets_eur_m",
    "total_equity_eur_m",
    "total_liabilities_eur_m",
]


def load(frame, table):
    """Empty the table and append, rather than letting pandas replace it.
    `if_exists="replace"` drops the table and rebuilds it from the DataFrame,
    which silently discards the primary and foreign keys declared above."""
    cursor.execute(f"DELETE FROM {table}")
    frame.to_sql(table, conn, if_exists="append", index=False)


meta = pd.read_csv(DATA_PATH / "companies_meta.csv")
load(meta, "companies")
print(f"Loaded {len(meta)} companies into 'companies' table")

# --- Load financial data ---

fin_path = DATA_PATH / "financials.csv"
if fin_path.exists():
    fin = pd.read_csv(fin_path)
    # Drop a row only when it carries no figures at all. Filtering on revenue
    # alone would discard banks and investment companies, whose revenue is
    # deliberately blank while the rest of the row is complete.
    present = [f for f in STATEMENT_FIELDS if f in fin.columns]
    before = len(fin)
    fin = fin.dropna(subset=present, how="all")
    if before != len(fin):
        print(f"Skipped {before - len(fin)} rows with no figures at all")
    load(fin, "financials")
    print(f"Loaded {len(fin)} financial records into 'financials' table")
else:
    print("WARNING: data/financials.csv not found. Copy financials_template.csv, fill in data, and save as financials.csv")

# --- Load stock prices (if fetched) ---

prices_path = DATA_PATH / "stock_prices.csv"
if prices_path.exists():
    prices = pd.read_csv(prices_path)
    load(prices, "stock_prices")
    print(f"Loaded {len(prices)} price records into 'stock_prices' table")
else:
    print("INFO: No stock_prices.csv found.")

conn.commit()
conn.close()
print(f"\nDatabase created: {DB_PATH}")
