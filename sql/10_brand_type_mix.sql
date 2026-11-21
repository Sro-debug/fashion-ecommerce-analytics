-- Q10. Private label vs national brand vs premium: mix, discounting and profitability.
SELECT
    brand_type,
    ROUND(100.0 * SUM(selling_price) / SUM(SUM(selling_price)) OVER (), 1) AS gmv_share_pct,
    ROUND(AVG(discount_pct), 1)                                          AS avg_discount_pct,
    ROUND(100.0 * SUM(CASE WHEN item_status = 'Returned' THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN item_status IN ('Delivered','Returned') THEN 1 ELSE 0 END), 0), 1)
                                                                         AS return_rate_pct,
    ROUND(100.0 * SUM(product_margin) / NULLIF(SUM(net_revenue), 0), 1)  AS gross_margin_pct,
    ROUND(100.0 * SUM(contribution)   / NULLIF(SUM(net_revenue), 0), 1)  AS contribution_margin_pct,
    ROUND(SUM(contribution), 0)                                          AS contribution
FROM v_items
GROUP BY brand_type
ORDER BY gmv_share_pct DESC;
