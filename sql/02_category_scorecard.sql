-- Q2. Category scorecard: which categories actually make money after returns and logistics?
SELECT
    category,
    COUNT(*)                                                             AS items_placed,
    SUM(selling_price)                                                   AS gmv,
    ROUND(100.0 * SUM(selling_price) / SUM(SUM(selling_price)) OVER (), 1) AS gmv_share_pct,
    SUM(net_revenue)                                                     AS net_revenue,
    ROUND(AVG(discount_pct), 1)                                          AS avg_discount_pct,
    ROUND(100.0 * SUM(CASE WHEN item_status = 'Returned' THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN item_status IN ('Delivered','Returned') THEN 1 ELSE 0 END), 0), 1)
                                                                         AS return_rate_pct,
    ROUND(SUM(contribution), 0)                                          AS contribution,
    ROUND(100.0 * SUM(contribution) / NULLIF(SUM(net_revenue), 0), 1)    AS contribution_margin_pct
FROM v_items
GROUP BY category
ORDER BY gmv DESC;
