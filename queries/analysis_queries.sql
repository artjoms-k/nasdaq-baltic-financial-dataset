-- ============================================================
-- Nasdaq Baltic Financial Dataset — SQL Analysis Queries
-- ============================================================

-- 1. COMPANY OVERVIEW: Count of listed companies by country and list type
SELECT
    country,
    list_type,
    COUNT(*) AS company_count
FROM companies
GROUP BY country, list_type
ORDER BY country, list_type;


-- 2. PROFITABILITY RANKING: Top 10 companies by ROE (latest year)
SELECT
    c.company_name,
    c.country,
    c.sector,
    f.year,
    f.net_income_eur_m,
    f.total_equity_eur_m,
    ROUND(f.net_income_eur_m * 100.0 / NULLIF(f.total_equity_eur_m, 0), 2) AS roe_pct
FROM financials f
JOIN companies c ON f.ticker = c.ticker
WHERE f.year = (SELECT MAX(year) FROM financials)
  AND f.total_equity_eur_m > 0
ORDER BY roe_pct DESC
LIMIT 10;


-- 3. LEVERAGE ANALYSIS: Debt-to-Equity ratio by sector
SELECT
    c.sector,
    f.year,
    ROUND(AVG(f.total_liabilities_eur_m * 1.0 / NULLIF(f.total_equity_eur_m, 0)), 2) AS avg_de_ratio,
    COUNT(*) AS companies_in_sector
FROM financials f
JOIN companies c ON f.ticker = c.ticker
WHERE f.total_equity_eur_m > 0
GROUP BY c.sector, f.year
ORDER BY f.year DESC, avg_de_ratio DESC;


-- 4. REVENUE GROWTH: Year-over-year revenue growth per company
SELECT
    c.company_name,
    c.country,
    f_curr.year,
    f_curr.revenue_eur_m AS revenue_current,
    f_prev.revenue_eur_m AS revenue_previous,
    ROUND((f_curr.revenue_eur_m - f_prev.revenue_eur_m) * 100.0
          / NULLIF(f_prev.revenue_eur_m, 0), 2) AS revenue_growth_pct
FROM financials f_curr
JOIN financials f_prev
    ON f_curr.ticker = f_prev.ticker
    AND f_curr.year = f_prev.year + 1
JOIN companies c ON f_curr.ticker = c.ticker
WHERE f_prev.revenue_eur_m > 0
ORDER BY revenue_growth_pct DESC;


-- 5. COUNTRY COMPARISON: Average financial metrics by country (latest year)
SELECT
    c.country,
    COUNT(*) AS n_companies,
    ROUND(AVG(f.revenue_eur_m), 0) AS avg_revenue_k,
    ROUND(AVG(f.net_income_eur_m), 0) AS avg_net_income_k,
    ROUND(AVG(f.net_income_eur_m * 100.0 / NULLIF(f.revenue_eur_m, 0)), 2) AS avg_profit_margin_pct,
    ROUND(AVG(f.net_income_eur_m * 100.0 / NULLIF(f.total_equity_eur_m, 0)), 2) AS avg_roe_pct,
    ROUND(AVG(f.total_liabilities_eur_m * 1.0 / NULLIF(f.total_equity_eur_m, 0)), 2) AS avg_de_ratio
FROM financials f
JOIN companies c ON f.ticker = c.ticker
WHERE f.year = (SELECT MAX(year) FROM financials)
  AND f.total_equity_eur_m > 0
GROUP BY c.country
ORDER BY avg_roe_pct DESC;


-- 6. DIVIDEND PAYERS: Companies with consistent dividends
SELECT
    c.company_name,
    c.country,
    c.sector,
    COUNT(CASE WHEN f.dividends_per_share_eur > 0 THEN 1 END) AS years_with_dividends,
    ROUND(AVG(f.dividends_per_share_eur), 3) AS avg_dps_eur,
    MAX(f.dividends_per_share_eur) AS max_dps_eur
FROM financials f
JOIN companies c ON f.ticker = c.ticker
GROUP BY f.ticker
HAVING years_with_dividends > 0
ORDER BY years_with_dividends DESC, avg_dps_eur DESC;


-- 7. SIZE DISTRIBUTION: Companies by asset size quartiles
SELECT
    CASE
        WHEN total_assets_eur_m < q1 THEN 'Small (Q1)'
        WHEN total_assets_eur_m < q2 THEN 'Medium-Small (Q2)'
        WHEN total_assets_eur_m < q3 THEN 'Medium-Large (Q3)'
        ELSE 'Large (Q4)'
    END AS size_bucket,
    COUNT(*) AS company_count,
    ROUND(AVG(net_income_eur_m * 100.0 / NULLIF(total_equity_eur_m, 0)), 2) AS avg_roe_pct
FROM financials f
CROSS JOIN (
    SELECT
        MAX(CASE WHEN rn = cnt/4 THEN total_assets_eur_m END) AS q1,
        MAX(CASE WHEN rn = cnt/2 THEN total_assets_eur_m END) AS q2,
        MAX(CASE WHEN rn = cnt*3/4 THEN total_assets_eur_m END) AS q3
    FROM (
        SELECT total_assets_eur_m,
               ROW_NUMBER() OVER (ORDER BY total_assets_eur_m) AS rn,
               COUNT(*) OVER () AS cnt
        FROM financials
        WHERE year = (SELECT MAX(year) FROM financials)
          AND total_assets_eur_m IS NOT NULL
    )
) q
WHERE f.year = (SELECT MAX(year) FROM financials)
  AND f.total_assets_eur_m IS NOT NULL
  AND f.total_equity_eur_m > 0
GROUP BY size_bucket
ORDER BY size_bucket;


-- 8. STOCK PRICE VOLATILITY: 30-day rolling volatility (top movers)
SELECT
    c.company_name,
    c.country,
    ROUND(AVG(daily_return * daily_return) * 252 * 100, 2) AS annualized_vol_pct
FROM (
    SELECT
        ticker,
        (close - LAG(close) OVER (PARTITION BY ticker ORDER BY date))
        / NULLIF(LAG(close) OVER (PARTITION BY ticker ORDER BY date), 0) AS daily_return
    FROM stock_prices
    WHERE date >= date('now', '-6 months')
) returns
JOIN companies c ON returns.ticker = c.ticker
WHERE daily_return IS NOT NULL
GROUP BY returns.ticker
ORDER BY annualized_vol_pct DESC
LIMIT 10;
