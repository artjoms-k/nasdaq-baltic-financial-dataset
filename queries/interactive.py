"""
interactive.py — Explore the Nasdaq Baltic Financial Dataset
Run: python queries/interactive.py
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("db/nasdaq_baltic.db")

if not DB_PATH.exists():
    print("Database not found. Run: python src/01_create_db.py")
    exit()

conn = sqlite3.connect(DB_PATH)
pd.set_option("display.max_rows", 100)
pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 12)

PRESET_QUERIES = {
    "1": (
        "Market overview by country",
        """
        SELECT c.country,
               COUNT(DISTINCT f.ticker) AS companies,
               ROUND(SUM(f.revenue_eur_m), 0) AS total_revenue_M,
               ROUND(SUM(f.net_income_eur_m), 0) AS total_net_income_M,
               ROUND(SUM(f.total_assets_eur_m), 0) AS total_assets_M,
               ROUND(AVG(f.net_income_eur_m * 100.0 / NULLIF(f.total_equity_eur_m, 0)), 1) AS avg_roe_pct
        FROM financials f
        JOIN companies c ON f.ticker = c.ticker
        WHERE f.year = (SELECT MAX(year) FROM financials WHERE ticker = f.ticker)
          AND f.total_equity_eur_m > 0
        GROUP BY c.country
        ORDER BY total_revenue_M DESC
        """
    ),
    "2": (
        "Largest companies by revenue",
        """
        SELECT c.company_name, c.country, c.sector, f.year,
               f.revenue_eur_m AS revenue_M,
               f.net_income_eur_m AS net_income_M,
               f.total_assets_eur_m AS assets_M
        FROM financials f
        JOIN companies c ON f.ticker = c.ticker
        WHERE f.year = (SELECT MAX(year) FROM financials WHERE ticker = f.ticker)
        ORDER BY f.revenue_eur_m DESC
        LIMIT 20
        """
    ),
    "3": (
        "Most profitable companies (ROE, equity > 5M)",
        """
        SELECT c.company_name, c.country, c.sector,
               ROUND(f.net_income_eur_m * 100.0 / f.total_equity_eur_m, 1) AS roe_pct,
               f.net_income_eur_m AS net_income_M,
               f.total_equity_eur_m AS equity_M
        FROM financials f
        JOIN companies c ON f.ticker = c.ticker
        WHERE f.year = (SELECT MAX(year) FROM financials WHERE ticker = f.ticker)
          AND f.total_equity_eur_m > 5
          AND f.net_income_eur_m > 0
        ORDER BY roe_pct DESC
        LIMIT 20
        """
    ),
    "4": (
        "Sector breakdown (avg ROE + margin)",
        """
        SELECT c.sector,
               COUNT(DISTINCT f.ticker) AS companies,
               ROUND(SUM(f.revenue_eur_m), 0) AS total_revenue_M,
               ROUND(AVG(f.net_income_eur_m * 100.0 / NULLIF(f.revenue_eur_m, 0)), 1) AS avg_margin_pct,
               ROUND(AVG(f.net_income_eur_m * 100.0 / NULLIF(f.total_equity_eur_m, 0)), 1) AS avg_roe_pct
        FROM financials f
        JOIN companies c ON f.ticker = c.ticker
        WHERE f.year = (SELECT MAX(year) FROM financials WHERE ticker = f.ticker)
          AND f.total_equity_eur_m > 0 AND f.revenue_eur_m > 0
        GROUP BY c.sector
        HAVING companies >= 2
        ORDER BY avg_roe_pct DESC
        """
    ),
    "5": (
        "Baltic banks head-to-head",
        """
        SELECT c.company_name, c.country, f.year,
               f.revenue_eur_m AS net_revenue_M,
               f.net_income_eur_m AS net_income_M,
               f.total_assets_eur_m AS total_assets_M,
               f.total_equity_eur_m AS equity_M,
               ROUND(f.net_income_eur_m * 100.0 / NULLIF(f.total_equity_eur_m, 0), 1) AS roe_pct,
               ROUND(f.total_assets_eur_m / NULLIF(f.total_equity_eur_m, 0), 1) AS leverage
        FROM financials f
        JOIN companies c ON f.ticker = c.ticker
        WHERE c.sector LIKE '%Bank%'
          AND f.year = (SELECT MAX(year) FROM financials WHERE ticker = f.ticker)
        ORDER BY f.total_assets_eur_m DESC
        """
    ),
    "6": (
        "Revenue growth leaders (YoY, revenue > 5M)",
        """
        SELECT c.company_name, c.country, c.sector,
               f_prev.year AS from_year, f_curr.year AS to_year,
               f_prev.revenue_eur_m AS prev_M,
               f_curr.revenue_eur_m AS curr_M,
               ROUND((f_curr.revenue_eur_m - f_prev.revenue_eur_m) * 100.0
                     / f_prev.revenue_eur_m, 1) AS growth_pct
        FROM financials f_curr
        JOIN financials f_prev ON f_curr.ticker = f_prev.ticker
             AND f_curr.year = f_prev.year + 1
        JOIN companies c ON f_curr.ticker = c.ticker
        WHERE f_curr.year = (SELECT MAX(year) FROM financials WHERE ticker = f_curr.ticker)
          AND f_prev.revenue_eur_m > 5
        ORDER BY growth_pct DESC
        LIMIT 20
        """
    ),
    "7": (
        "Highest dividend payers",
        """
        SELECT c.company_name, c.country, f.year,
               f.dividends_per_share_eur AS dps_eur,
               f.net_income_eur_m AS net_income_M,
               f.shares_outstanding_m AS shares_M,
               ROUND(f.dividends_per_share_eur * f.shares_outstanding_m, 1) AS total_div_M,
               ROUND(f.dividends_per_share_eur * f.shares_outstanding_m * 100.0
                     / NULLIF(f.net_income_eur_m, 0), 0) AS payout_pct
        FROM financials f
        JOIN companies c ON f.ticker = c.ticker
        WHERE f.year = (SELECT MAX(year) FROM financials WHERE ticker = f.ticker)
          AND f.dividends_per_share_eur > 0
        ORDER BY total_div_M DESC
        """
    ),
    "8": (
        "Most leveraged companies (D/E ratio)",
        """
        SELECT c.company_name, c.country, c.sector,
               f.total_assets_eur_m AS assets_M,
               f.total_equity_eur_m AS equity_M,
               f.total_liabilities_eur_m AS debt_M,
               ROUND(f.total_liabilities_eur_m * 1.0 / NULLIF(f.total_equity_eur_m, 0), 2) AS de_ratio,
               ROUND(f.net_income_eur_m * 100.0 / NULLIF(f.total_equity_eur_m, 0), 1) AS roe_pct
        FROM financials f
        JOIN companies c ON f.ticker = c.ticker
        WHERE f.year = (SELECT MAX(year) FROM financials WHERE ticker = f.ticker)
          AND f.total_equity_eur_m > 0
          AND f.total_liabilities_eur_m > 0
        ORDER BY de_ratio DESC
        LIMIT 20
        """
    ),
    "9": (
        "Loss-making companies",
        """
        SELECT c.company_name, c.country, c.sector, f.year,
               f.revenue_eur_m AS revenue_M,
               f.net_income_eur_m AS net_income_M,
               ROUND(f.net_income_eur_m * 100.0 / NULLIF(f.revenue_eur_m, 0), 1) AS margin_pct
        FROM financials f
        JOIN companies c ON f.ticker = c.ticker
        WHERE f.year = (SELECT MAX(year) FROM financials WHERE ticker = f.ticker)
          AND f.net_income_eur_m < 0
        ORDER BY f.net_income_eur_m ASC
        """
    ),
    "10": (
        "Company deep dive (3-year trend)",
        "PROMPT"
    ),
}

def run_query(sql):
    try:
        df = pd.read_sql(sql, conn)
        if df.empty:
            print("No results.")
        else:
            print(df.to_string(index=False))
            print(f"\n({len(df)} rows)")
    except Exception as e:
        print(f"Error: {e}")

def company_deep_dive():
    print("Enter company name or ticker (e.g. LHV, Tallink, IGN1L):")
    search = input("Search> ").strip()
    if not search:
        return
    sql = f"""
    SELECT c.company_name, c.country, c.sector, c.list_type,
           f.year,
           f.revenue_eur_m AS revenue_M,
           f.net_income_eur_m AS net_income_M,
           f.total_assets_eur_m AS assets_M,
           f.total_equity_eur_m AS equity_M,
           ROUND(f.net_income_eur_m * 100.0 / NULLIF(f.total_equity_eur_m, 0), 1) AS roe_pct,
           ROUND(f.net_income_eur_m * 100.0 / NULLIF(f.revenue_eur_m, 0), 1) AS margin_pct,
           f.dividends_per_share_eur AS dps_eur
    FROM financials f
    JOIN companies c ON f.ticker = c.ticker
    WHERE c.company_name LIKE '%{search}%'
       OR c.ticker LIKE '%{search.upper()}%'
    ORDER BY c.company_name, f.year
    """
    run_query(sql)

def show_menu():
    print("\n" + "=" * 60)
    print("  NASDAQ BALTIC — Financial Dataset Explorer")
    print("  64 companies | 3 countries | 2022-2025")
    print("=" * 60)
    print()
    for key, (name, _) in PRESET_QUERIES.items():
        print(f"  [{key:>2}]  {name}")
    print()
    print("  [sql]  Write your own SQL query")
    print("  [t]    Show database structure")
    print("  [q]    Quit")
    print()

def show_tables():
    print("\n--- DATABASE STRUCTURE ---")
    print("\ncompanies: ticker, company_name, country, sector, list_type, exchange")
    print("financials: ticker, year, revenue_eur_m, net_income_eur_m,")
    print("            total_assets_eur_m, total_equity_eur_m,")
    print("            total_liabilities_eur_m, shares_outstanding_m,")
    print("            dividends_per_share_eur")
    print("stock_prices: ticker, date, open, high, low, close, volume")
    print("\nAll monetary values in EUR millions. Shares in millions.")
    print("\nCountries: EE (Estonia), LV (Latvia), LT (Lithuania)")
    print("Lists: Main, Secondary, FirstNorth")

if __name__ == "__main__":
    show_menu()

    while True:
        choice = input(">>> ").strip()

        if choice.lower() == 'q':
            break
        elif choice.lower() == 't':
            show_tables()
        elif choice.lower() == 'sql':
            print("Type your SQL query:")
            sql = input("SQL> ").strip()
            if sql:
                run_query(sql)
        elif choice == '10':
            company_deep_dive()
        elif choice in PRESET_QUERIES:
            name, sql = PRESET_QUERIES[choice]
            print(f"\n--- {name} ---\n")
            run_query(sql)
        elif choice.upper().startswith("SELECT"):
            run_query(choice)
        else:
            show_menu()

    conn.close()
    print("Done.")
