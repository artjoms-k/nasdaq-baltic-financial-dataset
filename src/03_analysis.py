"""
03_analysis.py — Financial analysis and visualization
Nasdaq Baltic Financial Dataset
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from pathlib import Path

DB_PATH = Path("db/nasdaq_baltic.db")
OUTPUT_PATH = Path("output")
OUTPUT_PATH.mkdir(exist_ok=True)

# --- Style setup ---
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "#f8f9fa",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
})

COLORS = {
    "EE": "#0072CE",  # Estonia blue
    "LV": "#9E1B32",  # Latvia maroon
    "LT": "#006A44",  # Lithuania green
}

SECTOR_COLORS = [
    "#264653", "#2a9d8f", "#e9c46a", "#f4a261",
    "#e76f51", "#606c38", "#283618", "#bc6c25",
]

conn = sqlite3.connect(DB_PATH)


# ============================================================
# CHART 1: ROE by Country — Bar chart
# ============================================================
def chart_roe_by_country():
    query = """
    SELECT c.company_name, c.country, c.sector,
           ROUND(f.net_income_eur_m * 100.0 / NULLIF(f.total_equity_eur_m, 0), 2) AS roe
    FROM financials f
    JOIN companies c ON f.ticker = c.ticker
    WHERE f.year = (SELECT MAX(year) FROM financials)
      AND f.total_equity_eur_m > 0
      AND f.net_income_eur_m IS NOT NULL
    ORDER BY roe DESC
    """
    df = pd.read_sql(query, conn)
    if df.empty:
        print("SKIP: chart_roe_by_country — no data")
        return

    top = df.head(15)
    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(
        range(len(top)), top["roe"],
        color=[COLORS.get(c, "#999") for c in top["country"]],
        edgecolor="white", linewidth=0.5
    )
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels([f"{row.company_name} ({row.country})" for _, row in top.iterrows()])
    ax.invert_yaxis()
    ax.set_xlabel("Return on Equity (%)")
    ax.set_title("Nasdaq Baltic: Top 15 Companies by ROE")
    ax.axvline(x=0, color="black", linewidth=0.8)

    # Legend
    for country, color in COLORS.items():
        ax.barh([], [], color=color, label=country)
    ax.legend(loc="lower right", framealpha=0.9)

    plt.tight_layout()
    fig.savefig(OUTPUT_PATH / "01_roe_by_country.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: 01_roe_by_country.png")


# ============================================================
# CHART 2: Debt/Equity vs Profit Margin — Scatter (Risk vs Return)
# ============================================================
def chart_risk_vs_return():
    query = """
    SELECT c.company_name, c.country, c.sector,
           f.total_liabilities_eur_m * 1.0 / NULLIF(f.total_equity_eur_m, 0) AS de_ratio,
           f.net_income_eur_m * 100.0 / NULLIF(f.revenue_eur_m, 0) AS profit_margin
    FROM financials f
    JOIN companies c ON f.ticker = c.ticker
    WHERE f.year = (SELECT MAX(year) FROM financials)
      AND f.total_equity_eur_m > 0
      AND f.revenue_eur_m > 0
    """
    df = pd.read_sql(query, conn)
    if df.empty:
        print("SKIP: chart_risk_vs_return — no data")
        return

    # Filter extreme outliers for readability
    df = df[(df["de_ratio"] < 20) & (df["profit_margin"].between(-50, 80))]

    fig, ax = plt.subplots(figsize=(12, 8))
    for country, color in COLORS.items():
        mask = df["country"] == country
        subset = df[mask]
        ax.scatter(
            subset["de_ratio"], subset["profit_margin"],
            c=color, s=80, alpha=0.7, edgecolors="white",
            linewidth=0.5, label=country, zorder=3
        )
        for _, row in subset.iterrows():
            ax.annotate(
                row["company_name"], (row["de_ratio"], row["profit_margin"]),
                fontsize=7, alpha=0.7,
                xytext=(5, 5), textcoords="offset points"
            )

    ax.axhline(y=0, color="gray", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Debt-to-Equity Ratio (higher = more leveraged)")
    ax.set_ylabel("Net Profit Margin (%)")
    ax.set_title("Nasdaq Baltic: Risk (Leverage) vs Return (Profitability)")
    ax.legend(framealpha=0.9)

    plt.tight_layout()
    fig.savefig(OUTPUT_PATH / "02_risk_vs_return.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: 02_risk_vs_return.png")


# ============================================================
# CHART 3: Revenue Growth by Country — Grouped bar chart
# ============================================================
def chart_revenue_growth_by_country():
    query = """
    SELECT c.country,
           f_curr.year,
           AVG((f_curr.revenue_eur_m - f_prev.revenue_eur_m) * 100.0
               / NULLIF(f_prev.revenue_eur_m, 0)) AS avg_growth
    FROM financials f_curr
    JOIN financials f_prev
        ON f_curr.ticker = f_prev.ticker
        AND f_curr.year = f_prev.year + 1
    JOIN companies c ON f_curr.ticker = c.ticker
    WHERE f_prev.revenue_eur_m > 0
    GROUP BY c.country, f_curr.year
    ORDER BY f_curr.year, c.country
    """
    df = pd.read_sql(query, conn)
    if df.empty:
        print("SKIP: chart_revenue_growth_by_country — no data")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    years = sorted(df["year"].unique())
    countries = sorted(df["country"].unique())
    x = np.arange(len(years))
    width = 0.25

    for i, country in enumerate(countries):
        mask = df["country"] == country
        values = [df[mask & (df["year"] == y)]["avg_growth"].values for y in years]
        values = [v[0] if len(v) > 0 else 0 for v in values]
        ax.bar(x + i * width, values, width,
               label=country, color=COLORS.get(country, "#999"),
               edgecolor="white", linewidth=0.5)

    ax.set_xticks(x + width)
    ax.set_xticklabels([str(y) for y in years])
    ax.set_ylabel("Average Revenue Growth (%)")
    ax.set_title("Nasdaq Baltic: Average Revenue Growth by Country")
    ax.axhline(y=0, color="black", linewidth=0.8)
    ax.legend(framealpha=0.9)

    plt.tight_layout()
    fig.savefig(OUTPUT_PATH / "03_revenue_growth.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: 03_revenue_growth.png")


# ============================================================
# CHART 4: Sector Breakdown — ROE and Profit Margin comparison
# ============================================================
def chart_sector_comparison():
    query = """
    SELECT c.sector,
           AVG(f.net_income_eur_m * 100.0 / NULLIF(f.total_equity_eur_m, 0)) AS avg_roe,
           AVG(f.net_income_eur_m * 100.0 / NULLIF(f.revenue_eur_m, 0)) AS avg_margin,
           COUNT(DISTINCT f.ticker) AS n
    FROM financials f
    JOIN companies c ON f.ticker = c.ticker
    WHERE f.year = (SELECT MAX(year) FROM financials)
      AND f.total_equity_eur_m > 0
      AND f.revenue_eur_m > 0
    GROUP BY c.sector
    HAVING n >= 2
    ORDER BY avg_roe DESC
    """
    df = pd.read_sql(query, conn)
    if df.empty:
        print("SKIP: chart_sector_comparison — no data")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    colors = SECTOR_COLORS[:len(df)]

    ax1.barh(df["sector"], df["avg_roe"], color=colors, edgecolor="white")
    ax1.set_xlabel("Average ROE (%)")
    ax1.set_title("ROE by Sector")
    ax1.invert_yaxis()

    ax2.barh(df["sector"], df["avg_margin"], color=colors, edgecolor="white")
    ax2.set_xlabel("Average Net Profit Margin (%)")
    ax2.set_title("Profit Margin by Sector")
    ax2.invert_yaxis()

    fig.suptitle("Nasdaq Baltic: Sector Financial Comparison", fontsize=15, fontweight="bold", y=1.02)
    plt.tight_layout()
    fig.savefig(OUTPUT_PATH / "04_sector_comparison.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: 04_sector_comparison.png")


# ============================================================
# CHART 5: Stock price performance (normalized)
# ============================================================
def chart_price_performance():
    query = """
    SELECT sp.ticker, c.company_name, c.country, sp.date, sp.close
    FROM stock_prices sp
    JOIN companies c ON sp.ticker = c.ticker
    WHERE sp.ticker IN (
        SELECT ticker FROM stock_prices
        GROUP BY ticker
        HAVING COUNT(*) > 100
    )
    ORDER BY sp.ticker, sp.date
    """
    df = pd.read_sql(query, conn)
    if df.empty:
        print("SKIP: chart_price_performance — no price data")
        return

    df["date"] = pd.to_datetime(df["date"])

    # Normalize to 100
    fig, ax = plt.subplots(figsize=(14, 7))
    tickers = df["ticker"].unique()

    # Pick top 10 by trading volume to avoid clutter
    if len(tickers) > 10:
        vol_query = """
        SELECT ticker, SUM(volume) as total_vol
        FROM stock_prices GROUP BY ticker ORDER BY total_vol DESC LIMIT 10
        """
        top_tickers = pd.read_sql(vol_query, conn)["ticker"].tolist()
        df = df[df["ticker"].isin(top_tickers)]
        tickers = top_tickers

    for ticker in tickers:
        sub = df[df["ticker"] == ticker].sort_values("date")
        if sub.empty:
            continue
        first_close = sub["close"].iloc[0]
        if first_close <= 0:
            continue
        normalized = (sub["close"] / first_close) * 100
        country = sub["country"].iloc[0]
        ax.plot(sub["date"], normalized,
                label=f"{sub['company_name'].iloc[0]} ({country})",
                alpha=0.8, linewidth=1.2)

    ax.axhline(y=100, color="gray", linewidth=0.8, linestyle="--", alpha=0.5)
    ax.set_ylabel("Normalized Price (Start = 100)")
    ax.set_title("Nasdaq Baltic: Stock Price Performance (Normalized)")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9, ncol=2)
    ax.xaxis.set_major_locator(plt.MaxNLocator(12))

    plt.tight_layout()
    fig.savefig(OUTPUT_PATH / "05_price_performance.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: 05_price_performance.png")


# ============================================================
# RUN ALL
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("Nasdaq Baltic Financial Analysis")
    print("=" * 50)

    chart_roe_by_country()
    chart_risk_vs_return()
    chart_revenue_growth_by_country()
    chart_sector_comparison()
    chart_price_performance()

    conn.close()
    print("\nAll charts saved to output/")
