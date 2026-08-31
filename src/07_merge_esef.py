"""
07_merge_esef.py — Merge the ESEF extract into the dataset

Policy, decided deliberately and documented in data/DICTIONARY.md:

* Where a filing exists for a company-year, the five statement figures come
  from it — revenue, net income, assets, equity, liabilities. Primary,
  audited, and stated to the thousand rather than rounded to the million.
* Dividends per share and shares outstanding are never taken from ESEF. The
  filings carry dividends paid during the year, which is a different quantity,
  and shares outstanding is not reliably tagged. Existing values are kept; new
  rows carry a share count derived from profit over basic EPS, flagged as
  such in `notes`.
* Where no filing exists, the row is left exactly as it was.
* Every row gains provenance: `source`, `source_url`, `retrieved_date`, `notes`.

Writes data/financials_proposed.csv and prints what it would change. Replacing
data/financials.csv is a manual step, on purpose.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

DATA = Path("data")
STATEMENT_FIELDS = [
    "revenue_eur_m",
    "net_income_eur_m",
    "total_assets_eur_m",
    "total_equity_eur_m",
    "total_liabilities_eur_m",
]
KEPT_FIELDS = ["shares_outstanding_m", "dividends_per_share_eur"]
PROVENANCE = ["source", "source_url", "retrieved_date", "notes"]
LEGACY_SOURCE = "Morningstar fact sheet via nasdaqbaltic.com"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="also overwrite data/financials.csv (default: write the proposal only)")
    args = parser.parse_args()

    existing = pd.read_csv(DATA / "financials.csv")
    # Two inputs, treated identically: what the collector read out of ESEF
    # filings, and what was entered by hand from an issuer's own report where
    # no filing was reachable. Each row carries its own source label.
    inputs = []
    esef_path = DATA / "esef_extract.csv"
    if esef_path.exists():
        inputs.append(pd.read_csv(esef_path))
        print(f"Reading {esef_path}")
    for manual_path in sorted(DATA.glob("manual_*.csv")):
        inputs.append(pd.read_csv(manual_path))
        print(f"Reading {manual_path}")
    if not inputs:
        print("Nothing to merge — run src/05_fetch_esef.py first.")
        return 1
    esef = pd.concat(inputs, ignore_index=True)

    # The existing figures are whole millions and load as integers; the filed
    # ones carry thousands. Widen the columns first, or the first assignment
    # fails on dtype rather than on anything meaningful.
    for column in STATEMENT_FIELDS + KEPT_FIELDS:
        if column in existing.columns:
            existing[column] = pd.to_numeric(existing[column], errors="coerce").astype("float64")

    for column in PROVENANCE:
        if column not in existing.columns:
            existing[column] = ""
        existing[column] = existing[column].astype("object")
    existing["source"] = existing["source"].replace("", LEGACY_SOURCE).fillna(LEGACY_SOURCE)

    merged = existing.set_index(["ticker", "year"])
    replaced, added, kept_blank = 0, 0, []

    for _, filing in esef.iterrows():
        key = (filing["ticker"], int(filing["year"]))
        values = {f: filing.get(f) for f in STATEMENT_FIELDS}
        present = {f: v for f, v in values.items() if pd.notna(v)}
        if not present:
            continue

        notes = filing.get("notes")
        notes = "" if pd.isna(notes) else str(notes)

        if key in merged.index:
            row = merged.loc[key]
            # Revenue is deliberately absent for banks and investment
            # companies; keep whatever the previous source had rather than
            # blanking a column that already held a figure.
            for field, value in present.items():
                merged.loc[key, field] = value
            source = "ESEF"
            if pd.isna(filing.get("revenue_eur_m")) and pd.notna(row.get("revenue_eur_m")):
                notes = "; ".join(filter(None, [notes, "revenue kept from the previous source"]))
                kept_blank.append(f"{key[0]} {key[1]}")
                # The row is no longer wholly from the filing, and the source
                # column has to say so on its own — it will be read without
                # the notes beside it.
                source = "ESEF; revenue from Morningstar fact sheet"
            merged.loc[key, "source"] = filing.get("source") if pd.notna(filing.get("source")) and source == "ESEF" else source
            merged.loc[key, "source_url"] = filing.get("source_url", "")
            merged.loc[key, "retrieved_date"] = filing.get("retrieved_date", "")
            merged.loc[key, "notes"] = notes
            replaced += 1
        else:
            new = {f: present.get(f) for f in STATEMENT_FIELDS}
            stated_shares = filing.get("shares_outstanding_m")
            derived_shares = filing.get("shares_outstanding_m_derived")
            if pd.notna(stated_shares):
                new["shares_outstanding_m"] = stated_shares
            elif pd.notna(derived_shares):
                new["shares_outstanding_m"] = derived_shares
                notes = "; ".join(filter(None, [notes, "shares derived from profit / basic EPS (weighted average)"]))
            new["dividends_per_share_eur"] = filing.get("dividends_per_share_eur", pd.NA)
            new["source"] = filing.get("source") if pd.notna(filing.get("source")) else "ESEF"
            new["source_url"] = filing.get("source_url", "")
            new["retrieved_date"] = filing.get("retrieved_date", "")
            new["notes"] = notes
            merged.loc[key, list(new)] = list(new.values())
            added += 1

    result = merged.reset_index()
    ordered = ["ticker", "year"] + STATEMENT_FIELDS + KEPT_FIELDS + PROVENANCE
    result = result[[c for c in ordered if c in result.columns]]
    result = result.sort_values(["ticker", "year"], ascending=[True, False])

    out = DATA / "financials_proposed.csv"
    result.to_csv(out, index=False)

    print(f"\nRows before: {len(existing)}   after: {len(result)}")
    print(f"Replaced from filings: {replaced}")
    print(f"Added from filings:    {added}")
    if kept_blank:
        print(f"Revenue kept from the previous source (financial companies): {len(kept_blank)}")

    print("\nSource mix:")
    print(result.source.value_counts().to_string())

    print("\nCompanies per year, after the merge:")
    covered = result.ticker.nunique()
    for year, count in result.groupby("year").ticker.nunique().items():
        print(f"  {year}: {count:>3} of {covered}")

    gaps = result[STATEMENT_FIELDS].isna().sum()
    print("\nStill blank, by field:")
    print(gaps.to_string())

    # The dataset's own rule, checked here before it reaches the validator.
    complete = result.dropna(subset=["total_assets_eur_m", "total_equity_eur_m", "total_liabilities_eur_m"])
    off = complete[(complete.total_assets_eur_m
                    - complete.total_equity_eur_m
                    - complete.total_liabilities_eur_m).abs() > 1]
    print(f"\nBalance sheet closes on {len(complete) - len(off)} of {len(complete)} complete rows.")
    if len(off):
        print(off[["ticker", "year", "total_assets_eur_m", "total_equity_eur_m", "total_liabilities_eur_m"]].to_string(index=False))

    print(f"\nWrote {out}")
    if args.apply:
        result.to_csv(DATA / "financials.csv", index=False)
        print("Applied to data/financials.csv — run src/04_validate.py, then commit.")
    else:
        print("Review it, then re-run with --apply to replace data/financials.csv.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
