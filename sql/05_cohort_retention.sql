-- Q5. Monthly cohort retention. Cohort = month of a customer's first non-cancelled order.
-- month_n = months since that first order; a customer counts as retained in month_n if they
-- placed any non-cancelled order in that month. Percentages are computed in Python
-- (and masked for cohorts that have not yet had month_n months to mature).
WITH valid AS (
    SELECT DISTINCT customer_id, order_date
    FROM orders
    WHERE order_status <> 'Cancelled'
),
first_order AS (
    SELECT customer_id, MIN(order_date) AS first_date
    FROM valid
    GROUP BY customer_id
),
activity AS (
    SELECT
        f.customer_id,
        substr(f.first_date, 1, 7) AS cohort,
        (CAST(substr(v.order_date, 1, 4) AS INT) * 12 + CAST(substr(v.order_date, 6, 2) AS INT))
      - (CAST(substr(f.first_date, 1, 4) AS INT) * 12 + CAST(substr(f.first_date, 6, 2) AS INT)) AS month_n
    FROM first_order f
    JOIN valid v USING (customer_id)
)
SELECT cohort, month_n, COUNT(DISTINCT customer_id) AS customers
FROM activity
WHERE month_n BETWEEN 0 AND 6
GROUP BY cohort, month_n
ORDER BY cohort, month_n;
