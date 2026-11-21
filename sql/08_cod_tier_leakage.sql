-- Q8. Cash-on-delivery vs prepaid across city tiers: where does revenue leak?
SELECT
    city_tier,
    CASE WHEN payment_mode = 'COD' THEN 'COD' ELSE 'Prepaid' END         AS payment_type,
    COUNT(DISTINCT order_id)                                             AS orders,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN order_status = 'Cancelled' THEN order_id END)
          / COUNT(DISTINCT order_id), 1)                                 AS cancel_pct,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN order_status = 'RTO' THEN order_id END)
          / COUNT(DISTINCT order_id), 1)                                 AS rto_pct,
    ROUND(100.0 * SUM(CASE WHEN item_status = 'Returned' THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN item_status IN ('Delivered','Returned') THEN 1 ELSE 0 END), 0), 1)
                                                                         AS return_pct,
    ROUND(1.0 * SUM(selling_price) / COUNT(DISTINCT order_id), 0)        AS aov,
    ROUND(1.0 * SUM(contribution) / COUNT(DISTINCT order_id), 1)         AS contribution_per_order
FROM v_items
GROUP BY city_tier, payment_type
ORDER BY city_tier, payment_type;
