-- Shared item-level view with unit economics. Every other query reads from this.
--
-- Definitions
--   GMV            = selling_price of every item placed (before cancellations / returns)
--   net_revenue    = selling_price of items that were delivered AND kept
--   contribution   = (selling_price - cost_price) on kept items
--                    - order-level fulfilment + payment cost, allocated by item share of order value
--                    - reverse logistics on returned items
--   Returned items: revenue is refunded (net_revenue = 0) but outbound shipping is already sunk.
--   RTO / Cancelled: no revenue; RTO still carries the (2x) shipping cost.

DROP VIEW IF EXISTS v_items;
CREATE VIEW v_items AS
SELECT
    oi.item_id,
    oi.order_id,
    o.customer_id,
    o.order_date,
    substr(o.order_date, 1, 7)                          AS order_month,
    o.payment_mode,
    o.order_status,
    o.sale_event,
    o.delivery_days,
    c.city_tier,
    c.acquisition_channel,
    c.gender,
    c.loyalty_member,
    p.category,
    p.sub_category,
    p.brand_type,
    p.cost_price,
    oi.mrp,
    oi.discount_pct,
    oi.selling_price,
    oi.item_status,
    oi.return_reason,
    CASE WHEN oi.discount_pct < 20 THEN '1) <20%'
         WHEN oi.discount_pct < 40 THEN '2) 20-39%'
         WHEN oi.discount_pct < 50 THEN '3) 40-49%'
         WHEN oi.discount_pct < 60 THEN '4) 50-59%'
         ELSE                           '5) 60%+' END   AS discount_band,
    CASE WHEN oi.item_status = 'Delivered' THEN oi.selling_price ELSE 0 END AS net_revenue,
    CASE WHEN oi.item_status = 'Delivered' THEN oi.selling_price - p.cost_price ELSE 0 END AS product_margin,
    ( CASE WHEN oi.item_status = 'Delivered' THEN oi.selling_price - p.cost_price ELSE 0 END
      - (o.fulfilment_cost + o.payment_cost)
          * 1.0 * oi.selling_price / SUM(oi.selling_price) OVER (PARTITION BY oi.order_id)
      - oi.return_logistics_cost )                      AS contribution
FROM order_items oi
JOIN orders    o ON o.order_id    = oi.order_id
JOIN products  p ON p.product_id  = oi.product_id
JOIN customers c ON c.customer_id = o.customer_id;
