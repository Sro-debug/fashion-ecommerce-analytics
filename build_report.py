"""
Run every SQL query, compute the key findings, render PNG charts and build the HTML dashboard.

    python build_report.py

Outputs
    outputs/tables/*.csv        one CSV per query
    outputs/charts/*.png        static charts (used in the README)
    outputs/key_findings.md     findings + actions, numbers computed from the data
    dashboard.html              self-contained interactive dashboard (Chart.js inlined)
"""
from pathlib import Path
import json
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd

from generate_data import APPAREL, SALES
from run_queries import run_all

ROOT = Path(__file__).parent
OUT = ROOT / "outputs"
CHARTS = OUT / "charts"
CHARTS.mkdir(parents=True, exist_ok=True)

# ILLUSTRATIVE assumption - not derived from the data. Edit to test other scenarios.
ASSUMED_CAC = {"Organic": 100, "Paid Social": 450, "Performance Search": 380,
               "Influencer": 520, "Referral": 250, "Email/CRM": 60}

C = dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
         grid="#e1e0d9", axis="#c3c2b7", s1="#2a78d6", s2="#eb6834")


# --------------------------------------------------------------------------- load
R = run_all(verbose=False)
kpi = R["11_overall_kpis"].iloc[0]
monthly = R["01_monthly_kpis"].copy()
cat = R["02_category_scorecard"].copy()
disc = R["03_discount_efficiency"].copy()
ev = R["04_sale_events"].copy()
coh = R["05_cohort_retention"].copy()
rfm = R["06_rfm_segments"].copy()
chn = R["07_channel_quality"].copy()
cod = R["08_cod_tier_leakage"].copy()
rr = R["09_return_reasons"].copy()
brand = R["10_brand_type_mix"].copy()

month_labels = [pd.Period(m).strftime("%b %y") for m in monthly.order_month]
disc["band"] = disc.discount_band.str.replace(r"^\d\)\s*", "", regex=True)
ev["short"] = (ev.sale_event.str.replace("Big Fashion Festival", "BFF").str.replace(" Sale", "")
               .str.replace(" 2025", " '25").str.replace(" 2026", " '26"))
chn["assumed_cac"] = chn.acquisition_channel.map(ASSUMED_CAC)
chn["cm_to_cac"] = chn.contribution_per_buyer / chn.assumed_cac
cat_by_ret = cat.sort_values("return_rate_pct", ascending=False).reset_index(drop=True)

# cohort retention %, masked where the cohort has not matured yet
piv = coh.pivot(index="cohort", columns="month_n", values="customers")
ret = piv.div(piv[0], axis=0) * 100
last = pd.Period(monthly.order_month.max())
for c_ in ret.index:
    for n_ in ret.columns:
        if pd.Period(c_) + int(n_) > last:
            ret.loc[c_, n_] = np.nan

# return reasons (apparel + footwear only, where size/fit is a real reason)
app = rr[rr.category.isin(APPAREL)].groupby("return_reason").returned_items.sum().sort_values(ascending=False)
reasons = [{"reason": k, "items": int(v), "pct": float(v / app.sum() * 100)} for k, v in app.items()]
size_share_apparel = app.get("Size/Fit issue", 0) / app.sum() * 100
size_share_all = rr[rr.return_reason == "Size/Fit issue"].returned_items.sum() / rr.returned_items.sum()


# --------------------------------------------------------------------------- findings
def lakh(x): return f"₹{x / 1e5:,.1f} lakh"
def pc(x, d=1): return f"{x:.{d}f}%"

d_lo, d_hi = disc.iloc[0], disc.iloc[-1]
med_order_lift, med_cm_lift = ev.order_lift_pct.median(), ev.cm_lift_pct.median()
base_cm, ev_cm = ev.baseline_cm_margin_pct.mean(), ev.cm_margin_pct.mean()
base_disc, ev_disc = ev.baseline_discount_pct.mean(), ev.avg_discount_pct.mean()

worst_cat = cat.sort_values("return_rate_pct").iloc[-1]
size_cut_pts = 0.20 * size_share_all * kpi.return_rate_pct

cod_row = lambda t, p: cod[(cod.city_tier == t) & (cod.payment_type == p)].iloc[0]
t3c, t3p = cod_row(3, "COD"), cod_row(3, "Prepaid")
gap_half = sum(0.5 * cod_row(t, "COD").orders * (cod_row(t, "Prepaid").contribution_per_order
                                                  - cod_row(t, "COD").contribution_per_order) for t in (2, 3))

ch = chn.set_index("acquisition_channel")
ps, rf = ch.loc["Paid Social"], ch.loc["Referral"]

seg = rfm.set_index("segment")
core_c = seg.loc[["Champions", "Loyal"], "customers_pct"].sum()
core_r = seg.loc[["Champions", "Loyal"], "revenue_pct"].sum()
ar, hib, newp = seg.loc["At Risk"], seg.loc["Hibernating"], seg.loc["New / Promising"]

br = brand.set_index("brand_type")
pl, nb = br.loc["Private Label"], br.loc["National Brand"]

insights = [
    dict(tag="Sale economics",
         head=f"Sales add ~{med_order_lift:.0f}% more orders but only ~{med_cm_lift:.0f}% more contribution",
         evidence=(f"Across {len(ev)} sale windows, median daily orders rose {med_order_lift:.0f}% against the prior 30 non-sale days, "
                   f"but average discount went from {base_disc:.0f}% to {ev_disc:.0f}% and contribution margin fell from "
                   f"{base_cm:.0f}% to {ev_cm:.0f}%. Contribution per day moved from {ev.cm_lift_pct.min():.0f}% to "
                   f"+{ev.cm_lift_pct.max():.0f}% depending on the event."),
         action=("Judge sales on contribution per day, not GMV. Replace blanket discounts with targeted offers (members, larger baskets) "
                 "and cap depth on low-margin brands. Pull-forward demand and post-sale dips are not measured here.")),
    dict(tag="Discounting",
         head=f"Items discounted 60%+ earn {d_hi.contribution_margin_pct:.1f}% margin vs {d_lo.contribution_margin_pct:.1f}% under 20% off",
         evidence=(f"The 60%+ band is {d_hi.share_of_items_pct:.1f}% of items, returns {d_hi.return_rate_pct:.1f}% of the time "
                   f"(vs {d_lo.return_rate_pct:.1f}% under 20% off) and contributes ₹{d_hi.contribution_per_item:.0f} per item against "
                   f"₹{d_lo.contribution_per_item:.0f}. Returns step up at 50% off and above."),
         action="Set a hard floor on contribution per item, flag SKUs that routinely sell at 60%+, and renegotiate cost or retire them."),
    dict(tag="Returns",
         head=f"{worst_cat.category} returns {worst_cat.return_rate_pct:.1f}% of delivered items; size and fit drives {size_share_apparel:.0f}% of apparel returns",
         evidence=(f"Overall item return rate is {kpi.return_rate_pct:.1f}%. Footwear and western wear also sit above 25%. "
                   f"Cutting size/fit returns by one fifth would lower the overall rate by about {size_cut_pts:.1f} points."),
         action="Prioritise size guidance and fit recommendations in ethnic wear and footwear, and track return rate by SKU and size, not just by category."),
    dict(tag="Payment and geography",
         head=f"Tier 3 COD orders lose {t3c.cancel_pct + t3c.rto_pct:.1f}% to cancellation or RTO vs {t3p.cancel_pct:.1f}% for prepaid",
         evidence=(f"Contribution per order is ₹{t3c.contribution_per_order:.0f} for Tier 3 COD vs ₹{t3p.contribution_per_order:.0f} prepaid "
                   f"({(1 - t3c.contribution_per_order / t3p.contribution_per_order) * 100:.0f}% lower). Closing half of the COD gap in Tier 2 and 3 "
                   f"would be worth about {lakh(gap_half)} over the period."),
         action="Offer a prepaid incentive, add OTP or WhatsApp confirmation before dispatch for COD, and restrict COD on high-risk pincodes or very deep-discount baskets."),
    dict(tag="Acquisition",
         head=f"Referral buyers are worth {rf.contribution_per_buyer / ps.contribution_per_buyer:.1f}x Paid Social buyers",
         evidence=(f"90-day repeat: {rf.repeat_90d_pct:.1f}% vs {ps.repeat_90d_pct:.1f}%. Contribution per buyer: ₹{rf.contribution_per_buyer:,.0f} vs "
                   f"₹{ps.contribution_per_buyer:,.0f}. With illustrative CAC assumptions, contribution covers CAC {rf.cm_to_cac:.1f}x for Referral "
                   f"and only {ps.cm_to_cac:.1f}x for Paid Social."),
         action="Shift budget toward referral and CRM, and optimise paid social for repeat propensity rather than first-order volume. CAC figures are assumptions, so replace them with real spend."),
    dict(tag="Customer base",
         head=f"Champions and Loyal are {core_c:.0f}% of customers but {core_r:.0f}% of revenue",
         evidence=(f"At Risk customers ({ar.customers_pct:.1f}% of buyers, average {ar.avg_recency_days:.0f} days since last order) still hold "
                   f"{ar.revenue_pct:.1f}% of revenue. Hibernating customers are {hib.customers_pct:.1f}% of buyers for {hib.revenue_pct:.1f}% of revenue, "
                   f"and {newp.customers_pct:.1f}% are new or promising one-timers."),
         action="Run win-back offers for At Risk first, since they were valuable. Nudge New / Promising buyers toward a second order within 30 to 60 days."),
    dict(tag="Private label",
         head=f"Private label earns {pl.contribution_margin_pct:.1f}% margin vs {nb.contribution_margin_pct:.1f}% for national brands, despite deeper discounts",
         evidence=(f"Private label is {pl.gmv_share_pct:.0f}% of GMV with {pl.avg_discount_pct:.0f}% average discount (national brands: {nb.avg_discount_pct:.0f}%), "
                   f"but its lower cost base absorbs it. Its return rate is higher ({pl.return_rate_pct:.1f}% vs {nb.return_rate_pct:.1f}%)."),
         action="Keep growing private label where return rates are manageable, and treat the margin gap with care: category mix differs between brand types."),
]

method = [
    "<b>All data is synthetic</b>, generated by <code>generate_data.py</code> with a fixed seed. Patterns (sale seasonality, COD leakage, discount vs returns) are deliberate; magnitudes are not real Myntra figures.",
    "<b>GMV</b> = selling price of every item placed. <b>Net revenue</b> = items delivered and kept. <b>Contribution</b> = net revenue minus product cost, shipping, payment fees and reverse logistics (allocated to items by share of order value). It excludes marketing, tech and overheads.",
    "<b>Sale lift</b> compares each event with the 30 non-sale days before it. It does not measure pull-forward demand or post-sale dips. Republic Day 2026 follows straight after the December sale, so its low baseline probably inflates that event's lift.",
    "<b>Retention</b> counts a customer as active in a month if they placed a non-cancelled order. <b>90-day repeat</b> uses only customers whose first order is at least 90 days before the data ends.",
    "<b>Assumed CAC</b> per channel is illustrative and not derived from the data, so use it to rank channels, not to quote real ratios.",
    "Sale-event dates are illustrative, not official campaign calendars.",
]

# --------------------------------------------------------------------------- PNG charts
plt.rcParams.update({
    "figure.facecolor": C["surface"], "axes.facecolor": C["surface"], "savefig.facecolor": C["surface"],
    "axes.edgecolor": C["axis"], "axes.labelcolor": C["ink2"], "xtick.color": C["muted"], "ytick.color": C["muted"],
    "text.color": C["ink2"], "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "font.size": 9, "axes.grid": True, "grid.color": C["grid"], "grid.linewidth": 0.8, "axes.axisbelow": True,
})
pct_fmt = FuncFormatter(lambda v, _: f"{v:.0f}%")
inr_fmt = FuncFormatter(lambda v, _: f"₹{v:,.0f}")


def head(ax, text):
    ax.set_title(text, loc="left", fontsize=11, fontweight="bold", color=C["ink"], pad=10)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(CHARTS / name, dpi=160)
    plt.close(fig)


def hbar(ax, labels, vals, title, fmt, color=None):
    y = np.arange(len(labels))
    ax.barh(y, vals, height=0.55, color=color or C["s1"])
    ax.set_yticks(y, labels)
    ax.set_ylim(len(labels) - 0.5, -0.5)   # first label on top; idempotent, so safe with sharey=True
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(fmt)
    head(ax, title)


def vbar(ax, labels, vals, title, fmt):
    x = np.arange(len(labels))
    ax.bar(x, vals, width=0.55, color=C["s1"])
    ax.set_xticks(x, labels)
    ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(fmt)
    head(ax, title)


def sale_bands(ax):
    months = list(monthly.order_month)
    first = True
    for s, e in SALES.values():
        i0, i1 = months.index(s[:7]), months.index(e[:7])
        ax.axvspan(i0 - 0.4, i1 + 0.4, color=C["grid"], alpha=0.8, lw=0, label="Sale month" if first else None)
        first = False


# 1 monthly GMV vs net revenue
fig, ax = plt.subplots(figsize=(9, 3.8))
x = np.arange(len(monthly))
ax.plot(x, monthly.gmv / 1e5, color=C["s1"], lw=2, label="GMV (all orders placed)")
ax.plot(x, monthly.net_revenue / 1e5, color=C["s2"], lw=2, label="Net revenue (delivered, kept)")
ax.set_xticks(x[::3], np.array(month_labels)[::3])
ax.set_ylabel("₹ lakh")
ax.set_ylim(bottom=0)
ax.legend(frameon=False, loc="upper left")
head(ax, "Monthly GMV vs net revenue")
save(fig, "01_monthly_gmv_net_revenue.png")

# 2 monthly contribution margin with sale months shaded
fig, ax = plt.subplots(figsize=(9, 3.6))
sale_bands(ax)
ax.plot(x, monthly.contribution_margin_pct, color=C["s1"], lw=2, label="Contribution margin")
ax.set_xticks(x[::3], np.array(month_labels)[::3])
ax.yaxis.set_major_formatter(pct_fmt)
ax.set_ylim(15, 36)
ax.legend(frameon=False, loc="lower right")
head(ax, "Contribution margin dips in every sale month")
save(fig, "02_monthly_contribution_margin.png")

# 3 category return rate and margin (same order)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.2), sharey=True)
hbar(a1, cat_by_ret.category, cat_by_ret.return_rate_pct, "Return rate by category", pct_fmt)
hbar(a2, cat_by_ret.category, cat_by_ret.contribution_margin_pct, "Contribution margin by category", pct_fmt)
a2.tick_params(axis="y", left=False)
save(fig, "03_category_returns_margin.png")

# 4 discount bands
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.8))
vbar(a1, disc.band, disc.return_rate_pct, "Return rate by discount depth", pct_fmt)
vbar(a2, disc.band, disc.contribution_per_item, "Contribution per item by discount depth", inr_fmt)
save(fig, "04_discount_efficiency.png")

# 5 sale events
fig, ax = plt.subplots(figsize=(9.5, 3.9))
xs = np.arange(len(ev))
ax.bar(xs - 0.2, ev.order_lift_pct, width=0.36, color=C["s1"], label="Orders per day", edgecolor=C["surface"], linewidth=2)
ax.bar(xs + 0.2, ev.cm_lift_pct, width=0.36, color=C["s2"], label="Contribution per day", edgecolor=C["surface"], linewidth=2)
ax.set_xticks(xs, ev.short)
ax.grid(axis="x", visible=False)
ax.yaxis.set_major_formatter(pct_fmt)
ax.set_ylabel("% lift vs prior 30 non-sale days")
ax.legend(frameon=False, loc="upper right")
head(ax, "Sale lift: orders jump sharply, contribution rises far less")
save(fig, "05_sale_event_lift.png")

# 6 cohort heatmap
cmap = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#86b6ef", "#3987e5", "#184f95"])
fig, ax = plt.subplots(figsize=(7.5, 7.2))
ret_m = ret.drop(columns=[0])            # M0 is 100% by definition; leaving it out keeps the scale readable
arr = np.ma.masked_invalid(ret_m.values.astype(float))
ax.imshow(arr, cmap=cmap, vmin=0, vmax=30, aspect="auto")
ax.grid(False)
ax.set_xticks(range(ret_m.shape[1]), [f"M{c}" for c in ret_m.columns])
ax.set_yticks(range(len(ret_m)), [f"{pd.Period(c).strftime('%b %y')}  (n={int(piv.loc[c, 0]):,})" for c in ret_m.index])
ax.xaxis.tick_top()
for i in range(arr.shape[0]):
    for j in range(arr.shape[1]):
        if not arr.mask[i, j]:
            v = arr[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8, color="#fff" if v >= 18 else C["ink"])
for s in ax.spines.values():
    s.set_visible(False)
ax.set_title("Cohort retention: % of cohort buying again in month M (colour capped at 30%)", loc="left",
             fontsize=10.5, fontweight="bold", color=C["ink"], pad=26)
save(fig, "06_cohort_retention.png")

# 7 channel quality
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
hbar(a1, chn.acquisition_channel, chn.repeat_90d_pct, "90-day repeat rate", pct_fmt)
hbar(a2, chn.acquisition_channel, chn.contribution_per_buyer, "Contribution per buyer", inr_fmt)
a2.tick_params(axis="y", left=False)
save(fig, "07_channel_quality.png")

# 8 RFM
fig, ax = plt.subplots(figsize=(9, 3.9))
yy = np.arange(len(rfm))
ax.barh(yy - 0.2, rfm.customers_pct, height=0.36, color=C["s1"], label="% of customers", edgecolor=C["surface"], linewidth=2)
ax.barh(yy + 0.2, rfm.revenue_pct, height=0.36, color=C["s2"], label="% of revenue", edgecolor=C["surface"], linewidth=2)
ax.set_yticks(yy, rfm.segment)
ax.invert_yaxis()
ax.grid(axis="y", visible=False)
ax.xaxis.set_major_formatter(pct_fmt)
ax.legend(frameon=False, loc="lower right")
head(ax, "RFM segments: share of customers vs share of revenue")
save(fig, "08_rfm_segments.png")

# 9 COD vs prepaid
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.7))
xt = np.arange(3)
for ax_, col, ttl, fmt in ((a1, "contribution_per_order", "Contribution per order", inr_fmt),
                           (a2, None, "Cancelled + RTO share of orders", pct_fmt)):
    for k, (pt, color) in enumerate((("Prepaid", C["s1"]), ("COD", C["s2"]))):
        sub = cod[cod.payment_type == pt].sort_values("city_tier")
        vals = sub[col] if col else sub.cancel_pct + sub.rto_pct
        ax_.bar(xt + (k - 0.5) * 0.36, vals, width=0.34, color=color, label=pt, edgecolor=C["surface"], linewidth=2)
    ax_.set_xticks(xt, ["Tier 1", "Tier 2", "Tier 3"])
    ax_.grid(axis="x", visible=False)
    ax_.yaxis.set_major_formatter(fmt)
    ax_.legend(frameon=False)
    head(ax_, ttl)
save(fig, "09_cod_vs_prepaid.png")

# --------------------------------------------------------------------------- dashboard
def recs(df):
    return json.loads(df.to_json(orient="records"))


cohort_rows = []
for c_ in ret.index:
    cohort_rows.append({
        "label": pd.Period(c_).strftime("%b %y"), "size": int(piv.loc[c_, 0]),
        "ret": [None if pd.isna(v) else round(float(v), 1) for v in ret.loc[c_].values],
    })

data = {
    "scope": f"{pd.Period(monthly.order_month.min()).strftime('%b %Y')} to {pd.Period(monthly.order_month.max()).strftime('%b %Y')} "
             f"· {int(kpi.customers):,} buyers · {int(kpi.orders):,} orders",
    "kpi": json.loads(kpi.to_json()),
    "insights": insights,
    "method": method,
    "month_labels": month_labels,
    "monthly": recs(monthly),
    "category": recs(cat_by_ret),
    "discount": recs(disc),
    "events": recs(ev),
    "cohort": cohort_rows,
    "rfm": recs(rfm),
    "channel": recs(chn),
    "cod": recs(cod),
    "reasons": reasons,
    "brand": recs(brand),
}
payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
html = (ROOT / "templates" / "dashboard.html").read_text()
html = html.replace("__CHARTJS__", (ROOT / "vendor" / "chart.umd.js").read_text().replace("</script", "<\\/script"))
html = html.replace("__DATA__", payload)
(ROOT / "dashboard.html").write_text(html)

# key findings markdown
md = ["# Key findings\n", "_All figures computed from the synthetic dataset by `build_report.py`._\n"]
for i, ins in enumerate(insights, 1):
    md.append(f"## {i}. {ins['head']}\n")
    md.append(f"**{ins['tag']}.** {ins['evidence']}\n")
    md.append(f"**Action:** {ins['action']}\n")
(OUT / "key_findings.md").write_text("\n".join(md))

# Excel workbook of every query result (for Excel / Power BI / Tableau users)
try:
    with pd.ExcelWriter(OUT / "analysis_tables.xlsx") as xw:
        for name, df in R.items():
            df.to_excel(xw, sheet_name=name[:31], index=False)
except ImportError:
    print("openpyxl not installed - skipped analysis_tables.xlsx")

print("charts:", len(list(CHARTS.glob("*.png"))), "| dashboard:", round((ROOT / "dashboard.html").stat().st_size / 1024), "KB")
for ins in insights:
    print("-", ins["head"])
