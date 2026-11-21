-- Q9. Why do customers return? Reason mix by category (share of that category's returns).
SELECT
    category,
    return_reason,
    COUNT(*)                                                             AS returned_items,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY category), 1) AS pct_of_category_returns
FROM v_items
WHERE item_status = 'Returned'
GROUP BY category, return_reason
ORDER BY category, returned_items DESC;
