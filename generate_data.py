"""
Generate a synthetic Myntra-style fashion e-commerce dataset (Jan 2025 - Oct 2026).

EVERYTHING HERE IS SYNTHETIC. No real Myntra data is used. Patterns are baked in on
purpose so the analysis has real business stories to find:

  * sale-event seasonality (EORS, Big Fashion Festival, Republic Day) - dates are illustrative
  * deeper discounts -> more volume but thinner / negative contribution margin
  * COD + Tier-3 + size-sensitive categories -> more cancellations, RTO and returns
  * acquisition channels with very different repeat behaviour and return behaviour

Run:  python generate_data.py
Out:  data/myntra_analytics.db (SQLite) and data/csv/*.csv
"""
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

SEED = 7
N_CUSTOMERS = 25_000
START, END = pd.Timestamp("2025-01-01"), pd.Timestamp("2026-10-31")

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "myntra_analytics.db"
CSV_DIR = ROOT / "data" / "csv"

# Illustrative sale windows (not official dates)
SALES = {
    "Republic Day Sale 2025": ("2025-01-22", "2025-01-27"),
    "EORS Jun 2025": ("2025-06-10", "2025-06-20"),
    "Big Fashion Festival 2025": ("2025-09-27", "2025-10-12"),
    "EORS Dec 2025": ("2025-12-20", "2026-01-02"),
    "Republic Day Sale 2026": ("2026-01-22", "2026-01-27"),
    "EORS Jun 2026": ("2026-06-10", "2026-06-20"),
    "Big Fashion Festival 2026": ("2026-09-26", "2026-10-11"),
}

# category: (n_products, (mrp_lo, mrp_hi), base_return_rate, sub_categories)
CATEGORIES = {
    "Men Casual Wear": (300, (499, 2999), 0.17, ["T-Shirts", "Jeans", "Shirts", "Shorts", "Jackets"]),
    "Men Formal Wear": (120, (999, 4999), 0.14, ["Formal Shirts", "Trousers", "Blazers", "Suits"]),
    "Women Western Wear": (320, (599, 3499), 0.24, ["Dresses", "Tops", "Jeans", "Co-ords", "Jumpsuits"]),
    "Women Ethnic Wear": (280, (799, 5999), 0.27, ["Kurtas", "Sarees", "Kurta Sets", "Lehengas", "Dupattas"]),
    "Footwear": (220, (699, 4999), 0.22, ["Sneakers", "Casual Shoes", "Heels", "Flats", "Sandals"]),
    "Sports & Active": (150, (599, 3999), 0.15, ["Track Pants", "Sports Shoes", "Gym Tees", "Jackets"]),
    "Beauty & Personal Care": (200, (199, 1999), 0.04, ["Skincare", "Makeup", "Fragrance", "Haircare"]),
    "Accessories": (160, (299, 2999), 0.08, ["Watches", "Bags", "Sunglasses", "Jewellery", "Wallets"]),
    "Kids Wear": (130, (399, 1999), 0.18, ["Boys Clothing", "Girls Clothing", "Infant Wear"]),
    "Home & Living": (90, (499, 3999), 0.06, ["Bedsheets", "Decor", "Kitchen"]),
}
CAT_NAMES = list(CATEGORIES)
APPAREL = {"Men Casual Wear", "Men Formal Wear", "Women Western Wear", "Women Ethnic Wear",
           "Footwear", "Sports & Active", "Kids Wear"}

BRAND_TYPES = ["Private Label", "National Brand", "Premium"]
BRAND_TYPE_P = [0.45, 0.40, 0.15]
BRAND_PREFIX = {"Private Label": "House", "National Brand": "Nation", "Premium": "Prime"}
BASE_DISC = {"Private Label": (0.35, 0.60), "National Brand": (0.15, 0.40), "Premium": (0.10, 0.30)}
COST_RATIO = {"Private Label": (0.22, 0.32), "National Brand": (0.40, 0.50), "Premium": (0.45, 0.55)}  # share of MRP

# order of CAT_NAMES
CAT_W = {
    "F": [0.02, 0.00, 0.30, 0.24, 0.12, 0.06, 0.12, 0.07, 0.04, 0.03],
    "M": [0.34, 0.16, 0.00, 0.00, 0.20, 0.12, 0.04, 0.08, 0.03, 0.03],
}

CITIES = {
    1: ["Bengaluru", "Mumbai", "Delhi NCR", "Hyderabad", "Chennai", "Pune", "Kolkata"],
    2: ["Jaipur", "Lucknow", "Indore", "Chandigarh", "Bhubaneswar", "Coimbatore", "Nagpur"],
    3: ["Siliguri", "Raipur", "Guwahati", "Ranchi", "Dehradun", "Mysuru", "Patna"],
}

CHANNELS = ["Organic", "Paid Social", "Performance Search", "Influencer", "Referral", "Email/CRM"]
CH_P = [0.30, 0.25, 0.18, 0.12, 0.10, 0.05]
CH_GAP = {"Organic": 1.0, "Paid Social": 1.35, "Performance Search": 1.1,
          "Influencer": 1.25, "Referral": 0.8, "Email/CRM": 0.9}  # >1 = slower repeat purchases
RET_CH = {"Paid Social": 1.15, "Influencer": 1.10}
# share of buyers who never organically come back (before loyalty-member adjustment)
ONE_TIME = {"Organic": 0.50, "Paid Social": 0.62, "Performance Search": 0.55,
            "Influencer": 0.58, "Referral": 0.40, "Email/CRM": 0.45}


def main():
    rng = np.random.default_rng(SEED)

    # ------------------------------------------------------------------ calendar
    days = pd.date_range(START, END)
    n_days = len(days)
    is_sale = np.zeros(n_days, dtype=bool)
    sale_name = np.full(n_days, None, dtype=object)
    sale_ranges = []
    for name, (s, e) in SALES.items():
        s_i = (pd.Timestamp(s) - START).days
        e_i = min((pd.Timestamp(e) - START).days, n_days - 1)
        is_sale[s_i:e_i + 1] = True
        sale_name[s_i:e_i + 1] = name
        sale_ranges.append((s_i, e_i))

    # ------------------------------------------------------------------ products
    prod_rows = []
    for cat, (n, (lo, hi), _, subs) in CATEGORIES.items():
        for _ in range(n):
            btype = rng.choice(BRAND_TYPES, p=BRAND_TYPE_P)
            mrp = int(round(float(np.exp(rng.uniform(np.log(lo), np.log(hi)))), -1)) - 1
            prod_rows.append({
                "category": cat,
                "sub_category": rng.choice(subs),
                "brand": f"{BRAND_PREFIX[btype]} {rng.integers(1, 7)}",
                "brand_type": btype,
                "mrp": mrp,
                "cost_price": round(mrp * rng.uniform(*COST_RATIO[btype])),
                "base_disc": rng.uniform(*BASE_DISC[btype]),
                "popularity": rng.pareto(1.6) + 1.0,
            })
    products = pd.DataFrame(prod_rows)
    products.insert(0, "product_id", 5000 + np.arange(len(products)))

    # ----------------------------------------------------------------- customers
    N = N_CUSTOMERS
    w = (1 + 0.003 * np.arange(n_days)) * np.where(is_sale, 2.5, 1.0)
    signup_idx = rng.choice(n_days, N, p=w / w.sum())
    gender = rng.choice(["F", "M"], N, p=[0.56, 0.44])
    age_group = rng.choice(["18-24", "25-34", "35-44", "45+"], N, p=[0.34, 0.40, 0.18, 0.08])
    tier = rng.choice([1, 2, 3], N, p=[0.42, 0.34, 0.24])
    city = np.array([rng.choice(CITIES[t]) for t in tier])
    channel = rng.choice(CHANNELS, N, p=CH_P)
    member = rng.random(N) < 0.28
    activity = rng.lognormal(0, 0.45, N)

    customers = pd.DataFrame({
        "customer_id": np.arange(1, N + 1),
        "signup_date": np.array(days[signup_idx].strftime("%Y-%m-%d")),
        "gender": gender,
        "age_group": age_group,
        "city": city,
        "city_tier": tier,
        "acquisition_channel": channel,
        "loyalty_member": member.astype(int),
    })

    # -------------------------------------------------------------------- orders
    order_rows = []
    for i in range(N):
        if rng.random() > 0.90:          # signed up, never bought
            continue
        d = int(signup_idx[i]) + int(rng.geometric(0.45)) - 1
        if d >= n_days:
            continue
        order_rows.append((i, d))
        p_one = ONE_TIME[channel[i]] * (0.7 if member[i] else 1.0)
        if rng.random() < p_one:         # one-and-done buyer (only returns via the sale boost below)
            continue
        mean_gap = 110 * CH_GAP[channel[i]] * (0.7 if member[i] else 1.0) / activity[i]
        d += 2 + int(rng.exponential(mean_gap))
        while d < n_days:
            order_rows.append((i, d))
            d += 2 + int(rng.exponential(mean_gap))

    # sale-event boost: existing customers come back during sales
    for s_i, e_i in sale_ranges:
        eligible = np.where(signup_idx < s_i)[0]
        p = np.where(member[eligible], 0.18, 0.09)
        for i in eligible[rng.random(len(eligible)) < p]:
            order_rows.append((int(i), int(rng.integers(s_i, e_i + 1))))

    orders = (pd.DataFrame(order_rows, columns=["cust_idx", "day_idx"])
              .sort_values(["cust_idx", "day_idx"], kind="stable").reset_index(drop=True))
    n_orders = len(orders)
    orders["order_id"] = 100001 + np.arange(n_orders)
    orders["order_seq"] = orders.groupby("cust_idx").cumcount() + 1

    ci, di = orders.cust_idx.values, orders.day_idx.values
    o_tier, o_member, o_gender = tier[ci], member[ci], gender[ci]
    o_channel = channel[ci]
    sale_o = is_sale[di]

    is_cod = rng.random(n_orders) < np.array([0.18, 0.30, 0.45])[o_tier - 1]
    pay_mode = np.where(
        is_cod, "COD",
        rng.choice(["UPI", "Credit/Debit Card", "Net Banking", "Wallet"], n_orders, p=[0.52, 0.33, 0.08, 0.07]))

    cancelled = rng.random(n_orders) < (0.04 + 0.04 * is_cod + 0.01 * sale_o)
    rto_p = np.where(is_cod, np.array([0.03, 0.06, 0.10])[o_tier - 1], 0.0)
    rto = (~cancelled) & (rng.random(n_orders) < rto_p)
    status = np.where(cancelled, "Cancelled", np.where(rto, "RTO", "Delivered"))

    delivery_days = np.where(
        status == "Delivered",
        np.array([2, 3, 5])[o_tier - 1] + rng.integers(0, 3, n_orders) + sale_o.astype(int),
        np.nan)
    ship = np.array([55, 75, 105])[o_tier - 1] + rng.integers(-8, 9, n_orders)
    fulfil = np.where(status == "Cancelled", 0, np.where(status == "RTO", ship * 2, ship))

    # --------------------------------------------------------------------- items
    n_items = np.where(
        sale_o,
        rng.choice([1, 2, 3, 4], n_orders, p=[0.40, 0.30, 0.18, 0.12]),
        rng.choice([1, 2, 3, 4], n_orders, p=[0.55, 0.28, 0.12, 0.05]))
    order_idx = np.repeat(np.arange(n_orders), n_items)
    total = len(order_idx)

    item_gender = o_gender[order_idx]
    item_cat = np.zeros(total, dtype=int)
    for g, wts in CAT_W.items():
        m = item_gender == g
        item_cat[m] = rng.choice(len(CAT_NAMES), m.sum(), p=wts)

    item_prod = np.zeros(total, dtype=int)          # row position in `products`
    for c, name in enumerate(CAT_NAMES):
        m = item_cat == c
        pool = products.index[products.category == name].values
        pop = products.popularity.values[pool]
        item_prod[m] = rng.choice(pool, m.sum(), p=pop / pop.sum())

    item_sale = sale_o[order_idx]
    disc = (products.base_disc.values[item_prod]
            + np.where(item_sale, rng.uniform(0.08, 0.20, total), 0.0)
            + rng.normal(0, 0.03, total))
    disc_pct = np.round(np.clip(disc, 0.05, 0.80) * 100).astype(int)
    mrp = products.mrp.values[item_prod]
    selling = np.round(mrp * (1 - disc_pct / 100)).astype(int)

    # returns
    p_ret = np.array([CATEGORIES[c][2] for c in CAT_NAMES])[item_cat].astype(float)
    p_ret *= np.where(disc_pct >= 50, 1.35, 1.0)
    p_ret *= np.where(is_cod[order_idx], 1.20, 1.0)
    p_ret *= np.where(orders.order_seq.values[order_idx] == 1, 1.15, 1.0)
    p_ret *= np.where(o_member[order_idx], 0.90, 1.0)
    p_ret *= pd.Series(o_channel).map(RET_CH).fillna(1.0).values[order_idx]
    p_ret = np.clip(p_ret, 0, 0.6)
    returned = (rng.random(total) < p_ret) & (status[order_idx] == "Delivered")

    cat_is_apparel = np.array([c in APPAREL for c in CAT_NAMES])[item_cat]
    reason = np.full(total, None, dtype=object)
    app_mask = returned & cat_is_apparel
    oth_mask = returned & ~cat_is_apparel
    reason[app_mask] = rng.choice(
        ["Size/Fit issue", "Not as shown in photos", "Quality issue", "Changed my mind", "Wrong item received"],
        app_mask.sum(), p=[0.46, 0.22, 0.14, 0.13, 0.05])
    reason[oth_mask] = rng.choice(
        ["Damaged / defective", "Changed my mind", "Not as described", "Wrong item received"],
        oth_mask.sum(), p=[0.32, 0.30, 0.28, 0.10])

    item_status = np.where(status[order_idx] != "Delivered", status[order_idx],
                           np.where(returned, "Returned", "Delivered"))
    return_cost = np.where(returned, rng.integers(80, 131, total), 0)

    # order-level payment cost needs order value
    order_gmv = np.bincount(order_idx, weights=selling, minlength=n_orders)
    pay_cost = np.where(status == "Delivered", np.where(is_cod, 40.0, np.round(0.018 * order_gmv, 1)), 0.0)

    # ------------------------------------------------------------------- tables
    orders_df = pd.DataFrame({
        "order_id": orders.order_id.values,
        "customer_id": ci + 1,
        "order_date": np.array(days[di].strftime("%Y-%m-%d")),
        "payment_mode": pay_mode,
        "order_status": status,
        "delivery_days": delivery_days,
        "fulfilment_cost": fulfil,
        "payment_cost": pay_cost,
        "sale_event": sale_name[di],
    })
    items_df = pd.DataFrame({
        "item_id": 1_000_001 + np.arange(total),
        "order_id": orders.order_id.values[order_idx],
        "product_id": products.product_id.values[item_prod],
        "quantity": 1,
        "mrp": mrp,
        "discount_pct": disc_pct,
        "selling_price": selling,
        "item_status": item_status,
        "return_reason": reason,
        "return_logistics_cost": return_cost,
    })
    products_df = products.drop(columns=["base_disc", "popularity"])

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    tables = {"customers": customers, "products": products_df, "orders": orders_df, "order_items": items_df}
    for name, df in tables.items():
        df.to_sql(name, con, index=False)
        df.to_csv(CSV_DIR / f"{name}.csv", index=False)
    con.executescript("""
        CREATE INDEX ix_orders_cust ON orders(customer_id);
        CREATE INDEX ix_orders_date ON orders(order_date);
        CREATE INDEX ix_items_order ON order_items(order_id);
        CREATE INDEX ix_items_prod  ON order_items(product_id);
    """)
    con.commit()
    con.close()

    print(f"customers: {len(customers):,} | products: {len(products_df):,} | "
          f"orders: {len(orders_df):,} | items: {len(items_df):,}")
    print(f"GMV (all placed): Rs {selling.sum() / 1e7:.2f} Cr")
    print(orders_df.order_status.value_counts(normalize=True).round(3).to_dict())
    print(f"DB written to {DB_PATH}")


if __name__ == "__main__":
    main()
