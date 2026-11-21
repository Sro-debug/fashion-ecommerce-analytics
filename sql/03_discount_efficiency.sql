-- Q3. Discount efficiency: does a deeper discount buy profitable growth, or just revenue?
SELECT
    discount_band,
    COUNT(*)                                                             AS items_placed,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)                   AS share_of_items_pct,
    ROUND(AVG(selling_price), 0)                                         AS avg_selling_price,
    ROUND(100.0 * SUM(CASE WHEN item_status = 'Returned' THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN item_status IN ('Delivered','Returned') THEN 1 ELSE 0 END), 0), 1)
                                                                         AS return_rate_pct,
    ROUND(100.0 * SUM(product_margin) / NULLIF(SUM(net_revenue), 0), 1)  AS gross_margin_pct,
    ROUND(100.0 * SUM(contribution)   / NULLIF(SUM(net_revenue), 0), 1)  AS contribution_margin_pct,
    ROUND(1.0 * SUM(contribution) / COUNT(*), 1)                         AS contribution_per_item
FROM v_items
GROUP BY discount_band
ORDER BY discount_band;
