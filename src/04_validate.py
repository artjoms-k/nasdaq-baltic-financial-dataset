"""
04_validate.py — Integrity checks for the Nasdaq Baltic Financial Dataset

Runs against the curated CSVs in data/. Exits 1 on any failure, so it can be
used as a pre-commit or CI gate. Everything it checks is documented in
data/DICTIONARY.md.
"""

import sys
from pathlib import Path

import pandas as pd

DATA = Path("data")
TOLERANCE_EUR_M = 1.0

VALID_LIST_TYPES = {"Main", "Secondary", "FirstNorth", "FirstNorthForeign"}
VALID_COUNTRIES = {"EE", "LV", "LT"}
VALID_EXCHANGES = {"TLN", "RIG", "VLN"}
VALID_STATUS = {"active", "delisted"}

failures = []
notes = []


def check(condition, message):
    if condition:
        print(f"  PASS  {message}")
    else:
        print(f"  FAIL  {message}")
        failures.append(message)


def main():
    meta = pd.read_csv(DATA / "companies_meta.csv")
    fin = pd.read_csv(DATA / "financials.csv")

    print("\nKeys and references")
    check(meta.ticker.is_unique, "companies_meta.ticker is unique")
    orphans = sorted(set(fin.ticker) - set(meta.ticker))
    check(not orphans, f"every financials.ticker exists in companies_meta {orphans if orphans else ''}")
    dupes = fin[fin.duplicated(["ticker", "year"], keep=False)]
    check(dupes.empty, "no duplicate (ticker, year) rows")

    print("\nControlled vocabularies")
    check(set(meta.list_type) <= VALID_LIST_TYPES, f"list_type in {sorted(VALID_LIST_TYPES)}")
    check(set(meta.country) <= VALID_COUNTRIES, f"country in {sorted(VALID_COUNTRIES)}")
    check(set(meta.exchange) <= VALID_EXCHANGES, f"exchange in {sorted(VALID_EXCHANGES)}")
    check(set(meta.status) <= VALID_STATUS, f"status in {sorted(VALID_STATUS)}")

    print("\nAccounting consistency")
    complete = fin.dropna(subset=["total_assets_eur_m", "total_equity_eur_m", "total_liabilities_eur_m"])
    gap = (complete.total_assets_eur_m - (complete.total_equity_eur_m + complete.total_liabilities_eur_m)).abs()
    broken = complete[gap > TOLERANCE_EUR_M]
    check(
        broken.empty,
        f"assets = equity + liabilities within {TOLERANCE_EUR_M:g} EUR m on all {len(complete)} complete rows"
        + ("" if broken.empty else f" — {len(broken)} rows off: {broken.ticker.tolist()[:10]}"),
    )
    # Negative equity is not an error. Airobot's 2025 equity is -0.227m: a real
    # capital deficit, and exactly the kind of fact a screen should surface
    # rather than a validator reject.
    negative = fin[fin.total_equity_eur_m < 0]
    if len(negative):
        print(f"  INFO  {len(negative)} rows with negative equity: "
              + ", ".join(f"{r.ticker} {r.year}" for r in negative.itertuples()))
    check((fin.revenue_eur_m.dropna() >= 0).all(), "no negative revenue")
    check(fin.year.between(2000, 2100).all(), "year values are plausible")

    print("\nCoverage (reported, not asserted)")
    covered = fin.ticker.nunique()
    no_data = sorted(set(meta.ticker) - set(fin.ticker))
    print(f"        {len(meta)} companies in metadata, {covered} with financial data")
    print(f"        {len(no_data)} without any rows: {', '.join(no_data) if no_data else '—'}")
    print(f"        {len(fin)} company-year rows")

    per_year = fin.year.value_counts().sort_index()
    print("        companies per year:")
    for year, count in per_year.items():
        print(f"          {year}: {count:>3} of {covered}")

    thin = per_year[per_year < covered * 0.75]
    if len(thin):
        notes.append(
            "years below 75% coverage: " + ", ".join(f"{y} ({c}/{covered})" for y, c in thin.items())
        )

    missing_bs = fin.total_assets_eur_m.isna().sum()
    if missing_bs:
        notes.append(f"{missing_bs} rows without total assets / liabilities")

    # A figure recorded as whole millions collapses to zero for a company
    # whose real number is a fraction of one. Equity of zero makes return on
    # equity undefined and poisons any average it lands in, so it is called
    # out rather than left to be discovered downstream.
    zero_equity = fin[fin.total_equity_eur_m == 0]
    if len(zero_equity):
        names = ", ".join(sorted(zero_equity.ticker.unique()))
        notes.append(f"{len(zero_equity)} rows with equity of exactly 0 — ROE is undefined ({names})")

    statement = ["revenue_eur_m", "net_income_eur_m", "total_assets_eur_m",
                 "total_equity_eur_m", "total_liabilities_eur_m"]
    present = [c for c in statement if c in fin.columns]
    rounded = fin[fin[present].apply(lambda r: all(v == round(v) for v in r.dropna()), axis=1)]
    if len(rounded):
        notes.append(
            f"{len(rounded)} rows carry whole millions only — precision lost at source, "
            "which matters most for companies below 10m"
        )

    by_list = (
        fin.assign(list_type=fin.ticker.map(meta.set_index("ticker").list_type))
        .groupby("list_type")
        .agg(companies=("ticker", "nunique"), rows=("ticker", "size"))
    )
    print("\n        coverage by list:")
    for list_type, row in by_list.iterrows():
        print(f"          {list_type:<18} {row.companies:>3} companies  {row.rows:>4} rows")

    print()
    if notes:
        print("Notes (not failures — disclose these in the README):")
        for note in notes:
            print(f"  •  {note}")
        print()

    if failures:
        print(f"FAILED — {len(failures)} check(s) did not pass.\n")
        return 1

    print("All checks passed.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
