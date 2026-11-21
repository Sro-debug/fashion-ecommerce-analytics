-- Q6. RFM customer segmentation on delivered orders (snapshot date = 2026-10-31).
-- Recency and frequency use fixed business-readable thresholds (deterministic, explainable);
-- monetary value is reported per segment rather than scored.
WITH base AS (
    SELECT
        customer_id,
        CAST(julianday('2026-10-31') - julianday(MAX(order_date)) AS INT) AS recency_days,
        COUNT(DISTINCT order_id)                                          AS frequency,
        SUM(net_revenue)                                                  AS monetary
    FROM v_items
    WHERE order_status = 'Delivered'
    GROUP BY customer_id
),
scored AS (
    SELECT *,
        CASE WHEN recency_days <= 30 THEN 5 WHEN recency_days <= 60 THEN 4
             WHEN recency_days <= 120 THEN 3 WHEN recency_days <= 240 THEN 2 ELSE 1 END AS r,
        CASE WHEN frequency >= 6 THEN 5 WHEN frequency >= 4 THEN 4
             WHEN frequency >= 3 THEN 3 WHEN frequency = 2 THEN 2 ELSE 1 END            AS f
    FROM base
),
segmented AS (
    SELECT *,
        CASE WHEN r >= 4 AND f >= 4 THEN 'Champions'
             WHEN r >= 3 AND f >= 3 THEN 'Loyal'
             WHEN r >= 4 AND f <= 2 THEN 'New / Promising'
             WHEN r <= 2 AND f >= 3 THEN 'At Risk'
             WHEN r <= 2 AND f <= 2 THEN 'Hibernating'
             ELSE 'Needs Attention' END AS segment
    FROM scored
)
SELECT
    segment,
    COUNT(*)                                                       AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)             AS customers_pct,
    ROUND(SUM(monetary), 0)                                        AS net_revenue,
    ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 1)   AS revenue_pct,
    ROUND(AVG(frequency), 1)                                       AS avg_orders,
    ROUND(AVG(recency_days), 0)                                    AS avg_recency_days,
    ROUND(AVG(monetary), 0)                                        AS avg_spend
FROM segmented
GROUP BY segment
ORDER BY revenue_pct DESC;
