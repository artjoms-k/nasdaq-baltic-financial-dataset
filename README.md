# Nasdaq Baltic Financial Dataset

The first open-source structured financial dataset covering all Nasdaq Baltic listed companies - Main List, Secondary List, and First North.

**64 companies · 188 data points · 3 countries · 12 sectors**

## What's Inside

* Financial data (revenue, net income, total assets, equity, liabilities, shares outstanding, dividends) for 2022-2025
* Data sourced from Morningstar Fact Sheets via nasdaqbaltic.com
* SQLite database with normalized tables (companies, financials, stock\_prices)
* 5 automated analysis charts
* Interactive SQL explorer with 10 preset analytical queries
* SQL query library for common financial analysis patterns

## Coverage

|List|Companies|Data Rows|
|-|-|-|
|Main List|31|\~93|
|Secondary List|17|\~51|
|First North|15|\~41|
|First North Foreign|1|3|
|**Total**|**64**|**188**|

5 micro/shell companies excluded (EJTC, GRB2G, PRIMO, PNKTD, ROBUS) - no meaningful financial data.

## Quick Start

```bash
pip install -r requirements.txt

# Step 1: Download stock prices (optional, requires internet)
python src/02\_fetch\_prices.py

# Step 2: Build database
python src/01\_create\_db.py

# Step 3: Generate charts
python src/03\_analysis.py

# Step 4: Explore the data interactively
python queries/interactive.py
```

## Interactive Explorer

```
python queries/interactive.py
```

10 preset queries covering market overview, profitability, sector analysis, bank comparison, dividend screening, leverage analysis, and individual company deep dives. Also supports custom SQL queries.

## Charts

1. **Top 15 by ROE** - horizontal bar chart, colored by country (EE/LV/LT)
2. **Risk vs Return** - scatter plot: D/E ratio vs net profit margin
3. **Revenue Growth by Country** - grouped bar chart, year-over-year
4. **Sector Comparison** - dual bar chart: ROE and profit margin by sector
5. **Stock Price Performance** - normalized price chart for top 10 most traded stocks

## Data Notes

* All monetary values in EUR millions
* Shares outstanding in millions
* Banks use Net Revenue as Revenue
* Some Total Assets estimated via Financial Leverage x Equity when not directly available
* Fiscal year anomalies: VBL1L (August), PRF1T (June), SAF1R (June), AKO1L (June)
* ROE figures for micro-cap companies with low equity base may appear inflated and should be interpreted with caution
* The dataset includes First North micro-caps which can skew country-level averages; filtering by company size is recommended for meaningful comparisons

## Tech Stack

Python, pandas, SQLite, matplotlib, yfinance

## Author

Artjoms Kanausks 
https://www.linkedin.com/in/kanausks/

