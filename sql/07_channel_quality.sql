-- Q7. Acquisition-channel quality: who comes back, who returns, who is worth paying for?
-- repeat_90d_pct only uses customers whose first order is at least 90 days before the data end,
-- so recent cohorts do not look artificially bad.
WITH o AS (
    SELECT customer_id, order_id, order_date
    FROM orders
    WHERE order_status <> 'Cancelled'
),
f AS (
    SELECT customer_id, MIN(order_date) AS first_date FROM o GROUP BY customer_id
),
r AS (
    SELECT f.customer_id,
           MAX(CASE WHEN julianday(o.order_date) - julianday(f.first_date) BETWEEN 1 AND 90
                    THEN 1 ELSE 0 END) AS repeat90
    FROM f JOIN o USING (customer_id)
    GROUP BY f.customer_id
),
rep AS (
    SELECT c.acquisition_channel AS ch,
           ROUND(100.0 * AVG(r.repeat90), 1) AS repeat_90d_pct
    FROM f
    JOIN r USING (customer_id)
    JOIN customers c USING (customer_id)
    WHERE f.first_date <= date('2026-10-31', '-90 day')
    GROUP BY c.acquisition_channel
),
econ AS (
    SELECT
        acquisition_channel                                               AS ch,
        COUNT(DISTINCT customer_id)                                       AS buyers,
        ROUND(1.0 * COUNT(DISTINCT order_id) / COUNT(DISTINCT customer_id), 2) AS orders_per_buyer,
        ROUND(100.0 * SUM(CASE WHEN item_status = 'Returned' THEN 1 ELSE 0 END)
              / NULLIF(SUM(CASE WHEN item_status IN ('Delivered','Returned') THEN 1 ELSE 0 END), 0), 1)
                                                                          AS return_rate_pct,
        ROUND(SUM(net_revenue) * 1.0 / COUNT(DISTINCT customer_id), 0)    AS net_revenue_per_buyer,
        ROUND(SUM(contribution) * 1.0 / COUNT(DISTINCT customer_id), 0)   AS contribution_per_buyer
    FROM v_items
    GROUP BY acquisition_channel
)
SELECT econ.ch AS acquisition_channel, buyers, orders_per_buyer, repeat_90d_pct,
       return_rate_pct, net_revenue_per_buyer, contribution_per_buyer
FROM econ
JOIN rep ON rep.ch = econ.ch
ORDER BY contribution_per_buyer DESC;
