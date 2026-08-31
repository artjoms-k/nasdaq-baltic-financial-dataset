"""
05_fetch_esef.py — Collect financial facts from ESEF filings

Source chain:
  ISIN  -> LEI          via GLEIF (api.gleif.org)
  LEI   -> filing list  via filings.xbrl.org (XBRL International, fed by the
                        national Officially Appointed Mechanisms)
  filing -> facts       via the xBRL-JSON rendering of the filing

Writes data/esef_extract.csv. It does NOT touch data/financials.csv — compare
first with src/06_compare_sources.py, merge only what you have looked at.

Coverage is uneven by country, and not because of the listing venue: the
Lithuanian OAM feeds the index reliably, the Estonian and Latvian ones barely
do. Run --report to see what came back before drawing conclusions from it.
"""

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

DATA = Path("data")
LEI_CACHE = DATA / "lei_map.csv"
OUT = DATA / "esef_extract.csv"

GLEIF_API = "https://api.gleif.org/api/v1/lei-records"
FILINGS_API = "https://filings.xbrl.org/api/filings"
FILINGS_HOST = "https://filings.xbrl.org"

HEADERS = {
    "User-Agent": "nasdaq-baltic-financial-dataset/1.0 (open dataset; +https://github.com/artjoms-k/nasdaq-baltic-financial-dataset)",
    "Accept": "application/json",
}
PAUSE_SECONDS = 1.0

# Duration facts: the income statement.
DURATION_CONCEPTS = {
    "revenue_eur_m": [
        "ifrs-full:Revenue",
        "ifrs-full:RevenueFromContractsWithCustomers",
        "ifrs-full:RevenueFromSaleOfGoods",
        "ifrs-full:RevenueFromRenderingOfServices",
    ],
    # Attributable to owners first, deliberately. A group with minority
    # shareholders tags both, and the totals differ by the non-controlling
    # share — Akola Group 2025: 60.7m total against 54.3m to owners. The
    # dataset is built on the owners' share, and equity below must match it or
    # return on equity compares one company's numerator to another's
    # denominator.
    "net_income_eur_m": [
        "ifrs-full:ProfitLossAttributableToOwnersOfParent",
        "ifrs-full:ProfitLoss",
    ],
    "dividends_paid_eur_m": [
        "ifrs-full:DividendsPaid",
        "ifrs-full:DividendsPaidClassAOrdinaryShares",
    ],
}
# Instant facts: the balance sheet, as at the period end.
INSTANT_CONCEPTS = {
    "total_assets_eur_m": ["ifrs-full:Assets"],
    "total_equity_eur_m": ["ifrs-full:EquityAttributableToOwnersOfParent", "ifrs-full:Equity"],
    "total_liabilities_eur_m": ["ifrs-full:Liabilities"],
}
EPS_CONCEPTS = ["ifrs-full:BasicEarningsLossPerShare"]

# Banks and investment companies do not report a comparable "revenue" line.
# Whatever ifrs-full:Revenue holds for them is not what the column means:
# DelfinGroup 2023 tags 9.2m against 41m of interest income, Invalda INVL
# 14.1m against 76m of total income. Leaving the field blank is the honest
# outcome — a wrong number in a comparable column is worse than a gap.
SKIP_REVENUE_SECTORS = {"Banks", "Financial Services"}

MIN_YEAR_DAYS, MAX_YEAR_DAYS = 300, 400


def get(url, params=None):
    response = requests.get(url, params=params, headers=HEADERS, timeout=60)
    response.raise_for_status()
    time.sleep(PAUSE_SECONDS)
    return response


# --------------------------------------------------------------------------
# Step 1: identifiers


def resolve_leis(meta, refresh=False):
    """ISIN -> LEI, cached in data/lei_map.csv.

    GLEIF sometimes answers a filter it cannot satisfy with an unrelated
    record, so the jurisdiction of the entity returned is checked against the
    country of the listing. A mismatch is refused, not stored: a wrong LEI
    quietly puts another company's figures into the dataset.

    Column access is by key throughout — `row.isin` would return the pandas
    Series method of that name rather than the ISIN value.
    """
    if LEI_CACHE.exists() and not refresh:
        cache = pd.read_csv(LEI_CACHE, dtype=str).fillna("")
    else:
        cache = pd.DataFrame(columns=["ticker", "isin", "lei", "legal_name", "jurisdiction"], dtype=str)

    rows = cache.to_dict("records")
    known = {r["isin"] for r in rows if r.get("lei")}
    suspect = []

    for _, company in meta.iterrows():
        ticker, isin_code, country = company["ticker"], company["isin"], company["country"]
        if isin_code in known:
            continue
        print(f"  {ticker} ({isin_code})...", end=" ", flush=True)
        record = {"ticker": ticker, "isin": isin_code, "lei": "", "legal_name": "", "jurisdiction": ""}
        try:
            found = get(GLEIF_API, {"filter[isin]": isin_code}).json().get("data", [])
            if not found:
                print("not found")
            else:
                entity = found[0]["attributes"]["entity"]
                jurisdiction = (entity.get("jurisdiction") or "")[:2]
                name = entity["legalName"]["name"]
                # An ISIN's country prefix is the reliable cross-check; the
                # listing country is a fallback for foreign-domiciled issuers.
                expected = {isin_code[:2], country}
                if jurisdiction and jurisdiction not in expected:
                    print(f"REFUSED — {name} ({jurisdiction}), expected {'/'.join(sorted(expected))}")
                    suspect.append(f"{ticker}: got {name} in {jurisdiction}")
                else:
                    record.update(lei=found[0]["id"], legal_name=name, jurisdiction=jurisdiction)
                    print(f"{record['lei']} — {name}")
        except Exception as error:
            print(f"ERROR {error}")
        rows.append(record)

    result = pd.DataFrame(rows).drop_duplicates(subset=["isin"], keep="last")
    result.to_csv(LEI_CACHE, index=False)
    if suspect:
        print("\n  Refused as mismatched (resolve by hand if the company is real):")
        for line in suspect:
            print(f"    {line}")
    return result


# --------------------------------------------------------------------------
# Step 2: filings


def list_filings(lei):
    payload = get(FILINGS_API, {"filter[entity.identifier]": lei, "page[size]": 100}).json()
    filings = []
    for item in payload.get("data", []):
        attributes = item.get("attributes", {})
        if not attributes.get("json_url") or not attributes.get("period_end"):
            continue
        filings.append(
            {
                "period_end": attributes["period_end"],
                "json_url": attributes["json_url"],
                "errors": attributes.get("error_count") or 0,
            }
        )
    return filings


def pick_one_per_period(filings):
    """Filings are often published twice, in the local language and in English.
    Prefer English, then fewest validation errors."""
    chosen = {}
    for filing in filings:
        period = filing["period_end"]
        english = "-en." in (filing["json_url"] or "")
        score = (0 if english else 1, filing["errors"])
        if period not in chosen or score < chosen[period]["_score"]:
            chosen[period] = {**filing, "_score": score}
    return sorted(chosen.values(), key=lambda f: f["period_end"])


def fiscal_year(period_end):
    """The label the company itself uses. A period ending 1 January belongs to
    the year before; a June or August year end belongs to its own year."""
    end = date.fromisoformat(period_end)
    return end.year - 1 if (end.month, end.day) == (1, 1) else end.year


# --------------------------------------------------------------------------
# Step 3: facts


def core_facts(report):
    """Yield (concept, period, value) for facts carrying no extra dimensions.
    A fact broken down by segment, geography or share class has more keys in
    `dimensions` and must never be mistaken for the consolidated total."""
    for fact in report.get("facts", {}).values():
        dimensions = fact.get("dimensions", {})
        if set(dimensions) - {"concept", "entity", "period", "unit", "language"}:
            continue
        yield dimensions.get("concept"), dimensions.get("period", ""), fact.get("value")


def parse_day(text):
    try:
        return date.fromisoformat(text[:10])
    except (TypeError, ValueError):
        return None


def period_ends_at(period, period_end, duration):
    """The same instant is written either as 31 December or as 1 January of the
    next day, and both must match the filing's own period end."""
    if not period:
        return False
    target = date.fromisoformat(period_end)
    allowed = {target, target + timedelta(days=1)}
    if duration:
        if "/" not in period:
            return False
        start, end = (parse_day(p) for p in period.split("/", 1))
        if not start or not end or end not in allowed:
            return False
        return MIN_YEAR_DAYS <= (end - start).days <= MAX_YEAR_DAYS
    return "/" not in period and parse_day(period) in allowed


def to_number(value):
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def best_value(facts, concepts, period_end, duration):
    """Collect every matching fact, prefer a non-zero one, and say when the
    candidates disagree. Taking the first hit is how a tagged zero ends up in
    the dataset in place of the real figure."""
    for concept in concepts:
        values = [
            to_number(value)
            for name, period, value in facts
            if name == concept and period_ends_at(period, period_end, duration)
        ]
        values = [v for v in values if v is not None]
        if not values:
            continue
        non_zero = [v for v in values if v != 0]
        if not non_zero:
            continue  # a tagged zero — try the next concept before believing it
        distinct = sorted(set(non_zero), key=abs, reverse=True)
        return distinct[0], (f"{concept} had {len(distinct)} differing values" if len(distinct) > 1 else "")
    return None, ""


def extract(report, period_end, sector=""):
    facts = list(core_facts(report))
    row, notes = {}, []

    for column, concepts in DURATION_CONCEPTS.items():
        if column == "revenue_eur_m" and sector in SKIP_REVENUE_SECTORS:
            notes.append(f"revenue not collected — {sector} report no comparable revenue line")
            continue
        value, note = best_value(facts, concepts, period_end, duration=True)
        if value is not None:
            row[column] = round(value / 1e6, 3)
        if note:
            notes.append(note)

    for column, concepts in INSTANT_CONCEPTS.items():
        value, note = best_value(facts, concepts, period_end, duration=False)
        if value is not None:
            row[column] = round(value / 1e6, 3)
        if note:
            notes.append(note)

    eps, _ = best_value(facts, EPS_CONCEPTS, period_end, duration=True)
    if eps is not None:
        row["basic_eps_eur"] = eps

    # Some issuers tag assets and equity but not the liabilities total.
    if "total_liabilities_eur_m" not in row and {"total_assets_eur_m", "total_equity_eur_m"} <= set(row):
        row["total_liabilities_eur_m"] = round(row["total_assets_eur_m"] - row["total_equity_eur_m"], 3)
        notes.append("liabilities derived as assets minus equity")

    # Equity here is the owners' share, so with minority shareholders in the
    # group the tagged liabilities total no longer closes the balance sheet:
    # assets minus owners' equity exceeds it by the non-controlling interest.
    # The dataset's own rule is that assets equal equity plus liabilities, and
    # the existing rows follow it, so the residual goes to liabilities and the
    # row says so.
    if {"total_assets_eur_m", "total_equity_eur_m", "total_liabilities_eur_m"} <= set(row):
        residual = row["total_assets_eur_m"] - row["total_equity_eur_m"] - row["total_liabilities_eur_m"]
        if abs(residual) > 0.5:
            row["total_liabilities_eur_m"] = round(row["total_assets_eur_m"] - row["total_equity_eur_m"], 3)
            notes.append(f"liabilities include {residual:.3f}m of non-controlling interests")

    # Shares outstanding is rarely tagged on its own. Profit over basic EPS
    # gives the weighted average over the year, not the year-end count — right
    # where there were no buybacks or issues, wrong where there were.
    if row.get("net_income_eur_m") and row.get("basic_eps_eur"):
        try:
            row["shares_outstanding_m_derived"] = round(row["net_income_eur_m"] / row["basic_eps_eur"], 3)
        except ZeroDivisionError:
            pass

    if notes:
        row["notes"] = "; ".join(notes)
    return row


# --------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Collect financial facts from ESEF filings.")
    parser.add_argument("--tickers", help="comma-separated subset, e.g. RSU1L,ZMP1L")
    parser.add_argument("--from-year", type=int, default=2022)
    parser.add_argument("--refresh-lei", action="store_true", help="re-resolve every LEI")
    args = parser.parse_args()

    meta = pd.read_csv(DATA / "companies_meta.csv")
    if args.tickers:
        wanted = {t.strip().upper() for t in args.tickers.split(",")}
        meta = meta[meta.ticker.isin(wanted)]
        if meta.empty:
            print("No such tickers in companies_meta.csv")
            return 1

    print(f"\nStep 1 — resolving LEIs for {len(meta)} companies")
    leis = resolve_leis(meta, refresh=args.refresh_lei)
    leis = leis[leis["lei"].astype(str).str.len() == 20]
    leis = leis[leis["ticker"].isin(meta["ticker"])]
    print(f"  {len(leis)} of {len(meta)} usable")

    print("\nStep 2 — collecting filings")
    sectors = meta.set_index("ticker")["sector"].to_dict()
    rows, no_filings, nothing_recent = [], [], []
    today = date.today().isoformat()

    for _, company in leis.iterrows():
        ticker, lei = company["ticker"], company["lei"]
        print(f"  {ticker}...", end=" ", flush=True)
        try:
            filings = pick_one_per_period(list_filings(lei))
        except Exception as error:
            print(f"ERROR {error}")
            continue

        if not filings:
            print("nothing in the index")
            no_filings.append(ticker)
            continue

        collected = []
        for filing in filings:
            period_end = filing["period_end"]
            year = fiscal_year(period_end)
            if year < args.from_year:
                continue

            url = FILINGS_HOST + filing["json_url"]
            try:
                report = get(url).json()
            except Exception as error:
                print(f"[{year}: {error}]", end=" ")
                continue

            values = extract(report, period_end, sectors.get(ticker, ""))
            if not values:
                print(f"[{year}: no facts matched]", end=" ")
                continue

            rows.append(
                {
                    "ticker": ticker,
                    "year": year,
                    "period_end": period_end,
                    **values,
                    "source": "ESEF",
                    "source_url": url,
                    "retrieved_date": today,
                }
            )
            collected.append(year)

        if collected:
            print(f"OK {sorted(collected)}")
        else:
            print("nothing since %d" % args.from_year)
            nothing_recent.append(ticker)

    if not rows:
        print("\nNothing collected.")
        return 1

    frame = pd.DataFrame(rows).sort_values(["ticker", "year"], ascending=[True, False])
    frame.to_csv(OUT, index=False)

    print(f"\nWrote {len(frame)} rows for {frame.ticker.nunique()} companies to {OUT}")

    # Coverage is the finding, so report it rather than leaving it in the log.
    countries = meta.set_index("ticker")["country"]
    frame["country"] = frame.ticker.map(countries)
    print("\nRows by country and year:")
    print(pd.crosstab(frame.country, frame.year).to_string())

    if "revenue_eur_m" in frame:
        blank = frame[frame["revenue_eur_m"].isna()]
        skipped = sorted(t for t in blank.ticker.unique() if sectors.get(t) in SKIP_REVENUE_SECTORS)
        unexplained = sorted(t for t in blank.ticker.unique() if sectors.get(t) not in SKIP_REVENUE_SECTORS)
        if skipped:
            print(f"\nRevenue left blank on purpose ({len(skipped)}): {', '.join(skipped)}")
            print("Banks and investment companies report no comparable revenue line.")
        if unexplained:
            print(f"\nRevenue tag not found ({len(unexplained)}): {', '.join(unexplained)}")
            print("Worth opening one of these filings by hand — the tag may be non-standard.")

    if no_filings:
        print(f"\nNot in the index ({len(no_filings)}): {', '.join(no_filings)}")
    if nothing_recent:
        print(f"Nothing since {args.from_year} ({len(nothing_recent)}): {', '.join(nothing_recent)}")
    if no_filings or nothing_recent:
        print("These are index coverage gaps, not proof the company never filed.")

    print("\nNothing in data/financials.csv has been changed.")
    print("Next: python src/06_compare_sources.py\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
