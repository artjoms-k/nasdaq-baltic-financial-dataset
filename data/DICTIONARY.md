# Data Dictionary

Two curated CSV files. Everything else in the repository is generated from them.

## `companies_meta.csv` — 69 rows, one per listed company

| Field | Type | Description |
|---|---|---|
| `ticker` | text | Nasdaq Baltic trading symbol. Primary key. |
| `company_name` | text | Legal or commonly used name. |
| `isin` | text | ISIN as published by Nasdaq Baltic. |
| `currency` | text | Reporting and trading currency. `EUR` for all current rows. |
| `exchange` | text | `TLN` Tallinn, `RIG` Riga, `VLN` Vilnius. |
| `list_type` | text | `Main`, `Secondary`, `FirstNorth`, `FirstNorthForeign`. |
| `industry` | text | Broad grouping, assigned by the author (see Classification below). |
| `sector` | text | Narrower grouping, assigned by the author. |
| `country` | text | `EE`, `LV`, `LT` — country of the listing venue, not of operations. |
| `status` | text | `active` or `delisted`. All rows are currently `active`. |
| `yahoo_ticker` | text | Symbol used by `src/02_fetch_prices.py` to pull prices. |

## `financials.csv` — 188 rows, one per company-year

| Field | Type | Unit | Description |
|---|---|---|---|
| `ticker` | text | — | Foreign key to `companies_meta.ticker`. |
| `year` | integer | — | Fiscal year, not calendar year (see Fiscal years below). |
| `revenue_eur_m` | real | EUR millions | Revenue. For banks, net revenue (net interest + net fee income). |
| `net_income_eur_m` | real | EUR millions | Net income attributable to shareholders. |
| `total_assets_eur_m` | real | EUR millions | Total assets. Blank where not published (29 rows). |
| `total_equity_eur_m` | real | EUR millions | Total shareholders' equity. |
| `total_liabilities_eur_m` | real | EUR millions | Total liabilities. Blank where not published (29 rows). |
| `shares_outstanding_m` | real | millions | Shares outstanding at year end. |
| `dividends_per_share_eur` | real | EUR | Dividend per share declared for that fiscal year. |

Primary key: (`ticker`, `year`).

## Source

Morningstar Fact Sheets published on [nasdaqbaltic.com](https://nasdaqbaltic.com), retrieved manually. Figures are as reported by the fact sheet, not restated by the author.

## Conventions and known limits

**Fiscal years.** Four companies do not report on a calendar year: `VBL1L` (August), `PRF1T` (June), `SAF1R` (June), `AKO1L` (June). The `year` field carries the fiscal year label used by the company.

**Derived total assets.** Where total assets were not directly available, they were derived as Financial Leverage × Equity. Such rows are not flagged separately — this is a known gap in provenance.

**Blank vs zero.** A blank cell means the figure was not available in the source. It does not mean zero.

**Classification.** `industry` and `sector` are the author's own groupings, not GICS, ICB or NACE. They are consistent within this dataset and not comparable to external classifications.

**Excluded companies.** Five First North listings appear in `companies_meta.csv` but carry no rows in `financials.csv`: `EJTC`, `GRB2G`, `PNKTD`, `PRIMO`, `ROBUS`. They are shells or micro-caps with no meaningful published financials.

**Micro-caps.** ROE for companies with a small equity base can look extreme without being wrong. Country and sector aggregates in this dataset are unweighted, so a handful of First North names can move them. Filter by size before comparing.

## Integrity checks

`src/04_validate.py` re-runs the checks that the dataset is expected to pass:

- every `ticker` in `financials.csv` exists in `companies_meta.csv`
- no duplicate (`ticker`, `year`) pairs
- `total_assets = total_equity + total_liabilities` within 1 EUR m, on every row where all three are present
- no negative equity, no negative revenue
- `list_type`, `country`, `exchange`, `status` take only the values listed above
- the coverage table in the README matches the data

The script exits non-zero on failure, so it can be wired into CI.
