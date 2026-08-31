# Nasdaq Baltic Financial Dataset

Structured financial data for every company listed on Nasdaq Baltic — Main List, Secondary List and First North — in one place, with the code that builds a database out of it.

**64 companies with data · 226 company-year rows · 3 countries · fiscal years 2022–2025**

The exchange publishes this information as Morningstar fact sheets, one PDF per company. That is fine for reading one company and useless for screening sixty-four. This repository is the same information as two CSV files, plus a SQLite build, a query library and a validation script.

## Repository structure

```
data/
  companies_meta.csv    curated  — 69 companies, one row each
  financials.csv        curated  — 226 company-year rows
  manual_2025.csv       curated  — figures entered by hand where no filing was reachable
  DICTIONARY.md         field definitions, conventions, known limits
src/
  01_create_db.py       builds db/nasdaq_baltic.db from the CSVs
  02_fetch_prices.py    pulls 3y of daily prices from Yahoo Finance
  03_analysis.py        writes charts to output/
  04_validate.py        integrity checks; exits non-zero on failure
  05_fetch_esef.py      collects figures from ESEF filings (see Sources)
  06_compare_sources.py compares that extract against the current data
  07_merge_esef.py      merges the extract in, with provenance
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
| Main List | 31 | 108 |
| Secondary List | 17 | 62 |
| First North | 15 | 52 |
| First North Foreign | 1 | 4 |
| **Total** | **64** | **226** |

`companies_meta.csv` holds 69 companies. Five First North listings — EJTC, GRB2G, PNKTD, PRIMO, ROBUS — are shells or micro-caps with no meaningful published financials and carry no financial rows.

Coverage is not uniform across years:

| Fiscal year | Companies | |
|---|---|---|
| 2022 | 38 of 64 | partial |
| 2023 | 62 of 64 | near complete |
| 2024 | 63 of 64 | near complete |
| 2025 | 63 of 64 | complete but for one |

2023, 2024 and 2025 are close to complete; 2022 is not, and a full four-year series exists for part of the market only. The single gap in 2025 is RKB1R, which has published no annual report since 2022 — its 2023 audit was still unfinished in April 2026 and the exchange lists its 2025 report for April 2027.

Figures come from three sources, and every row says which:

| Source | Rows |
|---|---|
| Issuer's ESEF filing | 78 |
| Issuer's ESEF filing, revenue from the fact sheet | 8 |
| Issuer's annual report, read by hand (audited) | 40 |
| Issuer's full-year report, read by hand (unaudited) | 4 |
| Morningstar fact sheet | 96 |

Where more than one existed the issuer's own report won: primary, mostly audited, and stated to the thousand rather than rounded to the million.

## What is in the data

Revenue, net income, total assets, total equity, total liabilities, shares outstanding and dividends per share, in EUR millions, plus listing metadata and a Yahoo Finance symbol per company. Full field definitions and conventions are in [`data/DICTIONARY.md`](data/DICTIONARY.md).

Sources: the issuer's own ESEF annual report where one is available, otherwise the Morningstar fact sheet published on [nasdaqbaltic.com](https://nasdaqbaltic.com). Each row records which, with a link to the filing it came from. Figures are as reported, not restated.

## Limitations

Read these before using the numbers.

* **17 rows have no total assets and no total liabilities.** The source did not publish them, and no filing was available to fill the gap. Blank means missing, never zero.
* **Some total assets are derived**, as Financial Leverage × Equity, on rows sourced from fact sheets. Rows read from a filing carry the reported figure instead; where the two differ by a few million, the filing is the reliable one.
* **Net income and equity are the owners' share**, excluding non-controlling interests, so the minority share sits inside liabilities. Rows where this applies say so in `notes`. See [`data/DICTIONARY.md`](data/DICTIONARY.md).
* **Revenue is blank for three rows** covering banks and investment companies read from filings — they report no comparable revenue line, and interest or fee income is not substituted for one.
* **Four companies do not report on a calendar year:** VBL1L (August), PRF1T (June), SAF1R (June), AKO1L (June). The `year` field carries the company's own fiscal year label.
* **Banks report net revenue** in the `revenue_eur_m` field on fact-sheet rows. Margins are not comparable to non-financials.
* **`industry` and `sector` are the author's groupings**, not GICS, ICB or NACE. Consistent inside this dataset, not comparable outside it.
* **Precision is not uniform.** Rows read from an issuer's own report are stated to the thousand; the 96 rows still sourced from fact sheets were recorded as whole millions, which for a company whose real figures are a fraction of a million destroys them. Every row where that rounding had produced a zero has now been re-entered from the issuer's report, and no row carries equity of exactly zero any more. Remaining fact-sheet rows for companies below 10m are still indicative rather than exact.
* **Aggregates are unweighted.** A few First North micro-caps can move a country or sector average. ROE on a small equity base can look extreme without being wrong. Filter by size first.
* **Collection is partly manual.** Lithuanian figures refresh automatically from filings; Estonian and Latvian ones are entered by hand. See below.

## Validation

```bash
python src/04_validate.py
```

Checks referential integrity, key uniqueness, controlled vocabularies, and that assets equal equity plus liabilities within 1 EUR m on all 209 rows where the three are present. It reports negative equity rather than rejecting it — Airobot ended 2025 with a capital deficit of 0.227m, which is a fact about the company, not a data error. It reports coverage rather than asserting it, so a thinning year shows up as a note instead of passing silently. Exit code is non-zero on failure.

Current state: all checks pass.

## Updating the data

The dataset is only worth as much as its last refresh. The intended cycle:

1. Run the ESEF collection below — it covers most of the Lithuanian market on its own.
2. For everything it does not reach, add or correct rows in `data/financials.csv` by hand from the issuer's annual report. One row per company-year, never edit generated files.
3. Add any new listing to `data/companies_meta.csv`; set `status` to `delisted` rather than deleting a company that leaves the exchange.
4. Run `python src/04_validate.py` and fix what it flags.
5. Update the coverage tables above, and commit with the retrieval date in the message.

Annual reports for Baltic issuers land through Q1–Q2, so a refresh once a quarter keeps the current fiscal year moving and one in early summer closes the previous one.

### Collecting from ESEF filings

Issuers on a regulated market file their annual report in ESEF — the European Single Electronic Format — with the figures tagged in XBRL. Those filings reach the national Officially Appointed Mechanisms and are indexed by XBRL International at [filings.xbrl.org](https://filings.xbrl.org/), which places no restrictions on reuse.

```bash
python src/05_fetch_esef.py --tickers RSU1L      # one company first
python src/06_compare_sources.py                 # how it lines up with what we have
python src/07_merge_esef.py                      # writes a proposal, changes nothing
python src/07_merge_esef.py --apply              # replaces data/financials.csv
```

`05_fetch_esef.py` resolves each ISIN to an LEI through GLEIF, finds that entity's filings, and reads the figures out of the xBRL-JSON rendering. It writes `data/esef_extract.csv` and never touches `data/financials.csv`. `06_compare_sources.py` compares the two on the years they share and reports where they disagree. `07_merge_esef.py` then writes `data/financials_proposed.csv`; it replaces the statement figures where a filing exists, keeps dividends and share counts from the previous source, and stamps every row with its provenance. Only `--apply` touches `data/financials.csv`.

**Coverage is uneven by country, and the reason is not the listing venue.** A full run in August 2026 returned 2025 figures for fourteen Lithuanian companies and none at all for Estonia or Latvia. Sixteen of the twenty-two Lithuanian issuers on a regulated market are in the index; twelve of nineteen Estonian ones and six of seven Latvian ones are absent, including names that certainly do file. The Lithuanian storage mechanism feeds the index reliably and the other two barely do. Both countries publish their filings on national portals — [Estonia](http://oam.fi.ee/et/home), [Latvia](https://csri.investinfo.lv/lv/) — but neither offers machine-readable access, so those figures are entered by hand.

So the dataset is refreshed asymmetrically, and says so plainly:

| Country | How it is collected | 2025 |
|---|---|---|
| Lithuania | automatically, from ESEF filings | current |
| Estonia | by hand, from the issuer's annual report | as noted per row |
| Latvia | by hand, from the issuer's annual report | as noted per row |

ESEF also does not apply to First North at all: an MTF is outside the regulated-market obligation, so those issuers publish PDFs only and always stay manual.

Two fields the filings do not give:

* **Dividend per share.** The filings carry total dividends paid during the year, which is not the dividend declared for that year. Tested against three years of one issuer, the one-year-lag reconstruction fits once — not a rule.
* **Revenue for banks and investment companies.** They do not report a comparable revenue line. Interest and fee income is a different quantity, and the script leaves the field blank rather than substituting it. Those companies are listed at the end of a run.

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
