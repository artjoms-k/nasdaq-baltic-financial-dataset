# Nasdaq Baltic Financial Dataset

Structured financial data for every company listed on Nasdaq Baltic — Main List, Secondary List and First North — in one place, with the code that builds a database out of it.

**64 companies with data · 188 company-year rows · 3 countries · fiscal years 2022–2025**

The exchange publishes this information as Morningstar fact sheets, one PDF per company. That is fine for reading one company and useless for screening sixty-four. This repository is the same information as two CSV files, plus a SQLite build, a query library and a validation script.

## Repository structure

```
data/
  companies_meta.csv    curated  — 69 companies, one row each
  financials.csv        curated  — 188 company-year rows
  DICTIONARY.md         field definitions, conventions, known limits
src/
  01_create_db.py       builds db/nasdaq_baltic.db from the CSVs
  02_fetch_prices.py    pulls 3y of daily prices from Yahoo Finance
  03_analysis.py        writes charts to output/
  04_validate.py        integrity checks; exits non-zero on failure
queries/
  analysis_queries.sql  query library
  interactive.py        SQL explorer with 10 presets
```

`data/` is the dataset. Everything else is rebuilt from it, and `db/` and `output/` are not tracked.

## Quick start

```bash
pip install -r requirements.txt

python src/02_fetch_prices.py   # optional, needs internet
python src/01_create_db.py      # builds db/nasdaq_baltic.db
python src/03_analysis.py       # writes charts to output/
python queries/interactive.py   # explore
```

`src/02_fetch_prices.py` writes `data/stock_prices.csv`, which `01_create_db.py` picks up if present. Without it the database has companies and financials but no prices, and the price chart is skipped.

## Coverage

| List | Companies with data | Rows |
|---|---|---|
| Main List | 31 | 93 |
| Secondary List | 17 | 49 |
| First North | 15 | 43 |
| First North Foreign | 1 | 3 |
| **Total** | **64** | **188** |

`companies_meta.csv` holds 69 companies. Five First North listings — EJTC, GRB2G, PNKTD, PRIMO, ROBUS — are shells or micro-caps with no meaningful published financials and carry no financial rows.

Coverage is not uniform across years:

| Fiscal year | Companies | |
|---|---|---|
| 2022 | 18 of 64 | thin |
| 2023 | 62 of 64 | near complete |
| 2024 | 63 of 64 | near complete |
| 2025 | 45 of 64 | in progress |

Cross-sectional work on 2023 and 2024 is on solid ground. Anything that needs a four-year series is not — build it on the subset that has one.

## What is in the data

Revenue, net income, total assets, total equity, total liabilities, shares outstanding and dividends per share, in EUR millions, plus listing metadata and a Yahoo Finance symbol per company. Full field definitions and conventions are in [`data/DICTIONARY.md`](data/DICTIONARY.md).

Source: Morningstar fact sheets published on [nasdaqbaltic.com](https://nasdaqbaltic.com), retrieved manually. Figures are as reported, not restated.

## Limitations

Read these before using the numbers.

* **29 rows have no total assets and no total liabilities.** The source did not publish them. Blank means missing, never zero.
* **Some total assets are derived**, as Financial Leverage × Equity, and are not flagged as such in the data. This is a gap in provenance.
* **Four companies do not report on a calendar year:** VBL1L (August), PRF1T (June), SAF1R (June), AKO1L (June). The `year` field carries the company's own fiscal year label.
* **Banks report net revenue** in the `revenue_eur_m` field. Margins are not comparable to non-financials.
* **`industry` and `sector` are the author's groupings**, not GICS, ICB or NACE. Consistent inside this dataset, not comparable outside it.
* **Aggregates are unweighted.** A few First North micro-caps can move a country or sector average. ROE on a small equity base can look extreme without being wrong. Filter by size first.
* **Collection is manual**, so the dataset is a snapshot rather than a feed. See below.

## Validation

```bash
python src/04_validate.py
```

Checks referential integrity, key uniqueness, controlled vocabularies, and that assets equal equity plus liabilities within 1 EUR m on all 159 rows where the three are present. It reports coverage rather than asserting it, so a thinning year shows up as a note instead of passing silently. Exit code is non-zero on failure.

Current state: all checks pass.

## Updating the data

The dataset is only worth as much as its last refresh. The intended cycle:

1. Pull the current fact sheet for each company from nasdaqbaltic.com.
2. Add or correct rows in `data/financials.csv`. One row per company-year, never edit generated files.
3. Add any new listing to `data/companies_meta.csv`; set `status` to `delisted` rather than deleting a company that leaves the exchange.
4. Run `python src/04_validate.py` and fix what it flags.
5. Update the coverage tables above, and commit with the retrieval date in the message.

Annual reports for Baltic issuers land through Q1–Q2, so a refresh once a quarter keeps the current fiscal year moving and one in early summer closes the previous one.

## Charts

`src/03_analysis.py` writes to `output/`:

1. **Top 15 by ROE** — horizontal bars, coloured by country
2. **Risk vs return** — D/E against net profit margin
3. **Revenue growth by country** — grouped bars, year over year
4. **Sector comparison** — ROE and profit margin by sector
5. **Stock price performance** — normalised prices, top 10 by turnover *(requires step 02)*

## Interactive explorer

`python queries/interactive.py` — ten presets covering market overview, profitability, sector analysis, bank comparison, dividend screening, leverage and single-company drill-downs, plus free-form SQL.

## Tech stack

Python, pandas, SQLite, matplotlib, yfinance.

## License

Code in `src/` and `queries/` is released under the MIT License — see [`LICENSE`](LICENSE).

The data in `data/` is released under [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/) — see [`data/LICENSE`](data/LICENSE). Use it, redistribute it, build on it commercially; attribute it.

Underlying figures originate from Morningstar fact sheets published by Nasdaq Baltic. The licence covers this compilation, not the underlying source data.

## Citation

```
Kanausks, A. (2026). Nasdaq Baltic Financial Dataset.
https://github.com/artjoms-k/nasdaq-baltic-financial-dataset
```

## Disclaimer

Published for research and education. Not investment advice, not a recommendation to buy or sell any security. Figures are transcribed from public fact sheets and may contain errors — verify against the issuer's own reporting before relying on them. No warranty of accuracy or completeness.

## Author

Artjoms Kanausks — [LinkedIn](https://www.linkedin.com/in/kanausks/)

Corrections and additions are welcome: open an issue with the ticker, the year, the figure and the source.
