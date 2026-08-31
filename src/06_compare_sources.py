"""
06_compare_sources.py — Compare the ESEF extract with the existing dataset

Answers one question: can 2025 be appended to a series built from Morningstar
fact sheets, or does the whole series have to be rebuilt from ESEF?

It compares only the years present in both, per company and per field, and
reports the relative difference. Nothing is written unless --write-merge is
passed, and even then it writes a proposed file, never financials.csv itself.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

DATA = Path("data")
FIELDS = [
    "revenue_eur_m",
    "net_income_eur_m",
    "total_assets_eur_m",
    "total_equity_eur_m",
    "total_liabilities_eur_m",
]
# The existing figures are rounded to whole millions, so anything within half a
# million of the filed figure is that rounding and nothing else. On a company
# earning 12.5m that same half million is 4% — which is why the test has to be
# absolute first and relative only as a backstop for large numbers.
ROUNDING_TOLERANCE_EUR_M = 0.5
ROUNDING_TOLERANCE_PCT = 1.0
MATERIAL_PCT = 5.0
MATERIAL_EUR_M = 1.0


def relative_difference(existing, esef):
    if pd.isna(existing) or pd.isna(esef):
        return None
    if existing == 0:
        return None
    return (esef - existing) / abs(existing) * 100


def explained_by_rounding(existing, esef):
    if pd.isna(existing) or pd.isna(esef):
        return None
    absolute = abs(esef - existing)
    if absolute <= ROUNDING_TOLERANCE_EUR_M:
        return True
    relative = relative_difference(existing, esef)
    return relative is not None and abs(relative) <= ROUNDING_TOLERANCE_PCT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-merge", action="store_true",
                        help="write data/financials_proposed.csv with ESEF rows appended for missing years")
    args = parser.parse_args()

    existing = pd.read_csv(DATA / "financials.csv")
    esef_path = DATA / "esef_extract.csv"
    if not esef_path.exists():
        print("data/esef_extract.csv not found — run src/05_fetch_esef.py first.")
        return 1
    esef = pd.read_csv(esef_path)

    print(f"\nExisting: {len(existing)} rows, {existing.ticker.nunique()} companies")
    print(f"ESEF:     {len(esef)} rows, {esef.ticker.nunique()} companies")

    overlap = existing.merge(esef, on=["ticker", "year"], suffixes=("_old", "_esef"))
    print(f"Overlapping company-years: {len(overlap)}\n")

    if overlap.empty:
        print("No overlap — cannot assess comparability. Widen --from-year in the fetch step.")
    else:
        summary = []
        material_rows = []
        for field in FIELDS:
            old_col, new_col = f"{field}_old", f"{field}_esef"
            if old_col not in overlap or new_col not in overlap:
                continue
            gaps, explained = [], 0
            for _, row in overlap.iterrows():
                delta = relative_difference(row[old_col], row[new_col])
                if delta is None:
                    continue
                absolute = abs(row[new_col] - row[old_col])
                gaps.append((abs(delta), absolute))
                if explained_by_rounding(row[old_col], row[new_col]):
                    explained += 1
                elif abs(delta) > MATERIAL_PCT and absolute > MATERIAL_EUR_M:
                    material_rows.append(
                        {
                            "ticker": row.ticker,
                            "year": row.year,
                            "field": field,
                            "existing": row[old_col],
                            "esef": row[new_col],
                            "diff_pct": round(delta, 1),
                            "diff_eur_m": round(row[new_col] - row[old_col], 3),
                        }
                    )
            if gaps:
                relatives = pd.Series([g[0] for g in gaps])
                absolutes = pd.Series([g[1] for g in gaps])
                summary.append(
                    {
                        "field": field,
                        "compared": len(gaps),
                        "within_rounding": explained,
                        "median_pct": round(relatives.median(), 2),
                        "max_eur_m": round(absolutes.max(), 3),
                    }
                )

        print("Agreement between sources, on years present in both:\n")
        print(pd.DataFrame(summary).to_string(index=False))

        total = sum(s["compared"] for s in summary)
        clean = sum(s["within_rounding"] for s in summary)
        if total:
            share = clean / total * 100
            print(
                f"\n{clean} of {total} comparisons ({share:.0f}%) are explained by rounding "
                f"(within {ROUNDING_TOLERANCE_EUR_M} EUR m or {ROUNDING_TOLERANCE_PCT}%)."
            )
            if share >= 95:
                print("Reading: the two sources are the same figures rounded differently.")
                print("A full rebuild is not needed — appending ESEF years keeps the series homogeneous.")
            elif share >= 80:
                print("Reading: mostly consistent, with a tail worth inspecting before appending.")
            else:
                print("Reading: the sources disagree too often to mix. Rebuild the series from ESEF.")

        if material_rows:
            print(f"\nDifferences above {MATERIAL_PCT}% ({len(material_rows)}):\n")
            print(pd.DataFrame(material_rows).to_string(index=False))
        else:
            print("\nNo differences above the material threshold.")

    # What ESEF would add
    have = set(zip(existing.ticker, existing.year))
    additions = esef[~esef.apply(lambda r: (r.ticker, r.year) in have, axis=1)]
    print(f"\nESEF rows not present in financials.csv: {len(additions)}")
    if len(additions):
        print(additions.groupby("year").size().to_string())

    if args.write_merge and len(additions):
        columns = [c for c in existing.columns if c in additions.columns]
        merged = pd.concat([existing, additions[columns]], ignore_index=True)
        merged = merged.sort_values(["ticker", "year"], ascending=[True, False])
        out = DATA / "financials_proposed.csv"
        merged.to_csv(out, index=False)
        print(f"\nWrote {out} — {len(merged)} rows. Review it, then replace financials.csv yourself.")
        print("Note: dividends_per_share_eur is not filled from ESEF and stays blank on new rows.")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
