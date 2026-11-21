-- Q11. Headline KPIs for the whole period (feeds the dashboard stat tiles).
SELECT
    COUNT(DISTINCT order_id)                                             AS orders,
    COUNT(DISTINCT customer_id)                                          AS customers,
    SUM(selling_price)                                                   AS gmv,
    SUM(net_revenue)                                                     AS net_revenue,
    ROUND(100.0 * (1 - SUM(net_revenue) * 1.0 / SUM(selling_price)), 1)  AS revenue_leakage_pct,
    ROUND(1.0 * SUM(selling_price) / COUNT(DISTINCT order_id), 0)        AS aov,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN order_status IN ('Cancelled','RTO') THEN order_id END)
          / COUNT(DISTINCT order_id), 1)                                 AS cancel_rto_pct,
    ROUND(100.0 * SUM(CASE WHEN item_status = 'Returned' THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN item_status IN ('Delivered','Returned') THEN 1 ELSE 0 END), 0), 1)
                                                                         AS return_rate_pct,
    ROUND(SUM(contribution), 0)                                          AS contribution,
    ROUND(100.0 * SUM(contribution) / NULLIF(SUM(net_revenue), 0), 1)    AS contribution_margin_pct
FROM v_items;
