-- Q4. Sale events vs baseline: is the volume lift worth the margin given up?
-- Each event is compared with the (up to) 30 non-sale days immediately before it, so business
-- growth over time is not mistaken for sale lift. Compared per day, so a 6-day and a 16-day
-- event are comparable. Republic Day 2025 has a shorter baseline (data starts 2025-01-01).
WITH daily AS (
    SELECT
        order_date,
        sale_event,
        COUNT(DISTINCT order_id) AS orders,
        SUM(selling_price)       AS gmv,
        SUM(net_revenue)         AS net_rev,
        SUM(contribution)        AS cm,
        AVG(discount_pct)        AS avg_disc
    FROM v_items
    GROUP BY order_date, sale_event
),
events AS (
    SELECT sale_event,
           MIN(order_date) AS start_date,
           COUNT(*)        AS days,
           SUM(orders)     AS orders,
           SUM(gmv)        AS gmv,
           SUM(net_rev)    AS net_rev,
           SUM(cm)         AS cm,
           AVG(avg_disc)   AS avg_disc
    FROM daily
    WHERE sale_event IS NOT NULL
    GROUP BY sale_event
),
baseline AS (
    SELECT e.sale_event,
           COUNT(d.order_date) AS b_days,
           SUM(d.orders)       AS b_orders,
           SUM(d.gmv)          AS b_gmv,
           SUM(d.net_rev)      AS b_net_rev,
           SUM(d.cm)           AS b_cm,
           AVG(d.avg_disc)     AS b_disc
    FROM events e
    JOIN daily d
      ON d.sale_event IS NULL
     AND d.order_date >= date(e.start_date, '-30 day')
     AND d.order_date <  e.start_date
    GROUP BY e.sale_event
)
SELECT
    e.sale_event,
    e.days,
    ROUND(1.0 * e.orders / e.days, 0)                                         AS orders_per_day,
    ROUND(1.0 * b.b_orders / b.b_days, 0)                                     AS baseline_orders_per_day,
    ROUND(100.0 * ((1.0 * e.orders / e.days) / (1.0 * b.b_orders / b.b_days) - 1), 0) AS order_lift_pct,
    ROUND(e.avg_disc, 1)                                                      AS avg_discount_pct,
    ROUND(b.b_disc, 1)                                                        AS baseline_discount_pct,
    ROUND(100.0 * e.cm / e.net_rev, 1)                                        AS cm_margin_pct,
    ROUND(100.0 * b.b_cm / b.b_net_rev, 1)                                    AS baseline_cm_margin_pct,
    ROUND(1.0 * e.cm / e.days, 0)                                             AS cm_per_day,
    ROUND(1.0 * b.b_cm / b.b_days, 0)                                         AS baseline_cm_per_day,
    ROUND(100.0 * ((1.0 * e.cm / e.days) / (1.0 * b.b_cm / b.b_days) - 1), 0) AS cm_lift_pct
FROM events e
JOIN baseline b USING (sale_event)
ORDER BY e.start_date;
