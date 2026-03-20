#!/usr/bin/env python3
"""
Onelife Intelligence Dashboard V7
Full rebuild with AI narrative, cross-store gap analysis, supplier ABC scorecard.
"""
import json, os, sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict

SAST = timezone(timedelta(hours=2))
NOW = datetime.now(SAST)
WORKSPACE = os.path.expanduser("~/.openclaw/workspace")

# Store targets (monthly, excl VAT)
TARGETS = {"CEN": 1_450_000, "GVS": 330_000, "EDN": 450_000}

def load_json(path):
    try:
        with open(os.path.join(WORKSPACE, path)) as f:
            return json.load(f)
    except Exception as e:
        print(f"WARN: Could not load {path}: {e}", file=sys.stderr)
        return {}

def main():
    # Load all data
    omni = load_json("memory/omni_cache.json")
    daily_cache = load_json("memory/daily-sales-cache.json")
    supplier_names_raw = load_json("memory/supplier_names.json")
    gp_data = load_json("memory/snapshots/2026-02/ana_popular_gp.json")
    supplier_sales = load_json("memory/snapshots/2026-02/ana_sales_per_supplier.json")
    
    # Supplier name lookup
    sup_names = {}
    if isinstance(supplier_names_raw, dict):
        sup_names = supplier_names_raw
    elif isinstance(supplier_names_raw, list):
        for item in supplier_names_raw:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                sup_names[item[0]] = item[1]
    
    def sup_name(code):
        full = sup_names.get(code, code or "Unknown")
        # Clean up long names
        if "(" in full:
            full = full.split("(")[0].strip()
        if " - " in full:
            full = full.split(" - ")[0].strip()
        return full[:30]

    # === MTD Sales ===
    mtd = omni.get("mtd", {})
    combined_mtd = mtd.get("combined", {})
    mtd_rev = combined_mtd.get("revenue_excl", 0)
    mtd_gp = combined_mtd.get("gross_profit", 0)
    mtd_gp_pct = combined_mtd.get("gp_pct", 0)
    
    # Per-store MTD
    store_mtd = {}
    for code, label in [("HO", "CEN"), ("GVS", "GVS"), ("EDN", "EDN")]:
        s = mtd.get(code, mtd.get(label, {}))
        store_mtd[label] = {
            "rev": s.get("revenue_excl", 0),
            "gp": s.get("gross_profit", 0),
        }
    # Fix: GVS and EDN might be under different keys
    if store_mtd["GVS"]["rev"] == 0:
        gvs = mtd.get("GVS", {})
        store_mtd["GVS"]["rev"] = gvs.get("revenue_excl", 0)
        store_mtd["GVS"]["gp"] = gvs.get("gross_profit", 0)
    if store_mtd["EDN"]["rev"] == 0:
        edn = mtd.get("EDN", {})
        store_mtd["EDN"]["rev"] = edn.get("revenue_excl", 0)
        store_mtd["EDN"]["gp"] = edn.get("gross_profit", 0)
    # CEN might be total minus others
    if store_mtd["CEN"]["rev"] == 0:
        store_mtd["CEN"]["rev"] = mtd_rev - store_mtd["GVS"]["rev"] - store_mtd["EDN"]["rev"]
        store_mtd["CEN"]["gp"] = mtd_gp - store_mtd["GVS"]["gp"] - store_mtd["EDN"]["gp"]
    
    # Today
    today_data = omni.get("today", {})
    today_rev = today_data.get("combined", {}).get("revenue_excl", 0)
    
    # === Daily history for trends ===
    days_data = daily_cache.get("days", {})
    
    # Last 7 days revenue per store
    def get_week_trend(store_key, n_days=7):
        vals = []
        for i in range(n_days):
            d = (NOW - timedelta(days=i+1)).strftime("%Y-%m-%d")
            day = days_data.get(d, {})
            rev = day.get(store_key, {}).get("revenue", 0)
            vals.append(rev)
        return list(reversed(vals))
    
    cen_week = get_week_trend("CEN")
    gvs_week = get_week_trend("GVS")
    edn_week = get_week_trend("EDN")
    
    # Monthly totals for last 3 months
    def get_monthly_total(year, month, store_key):
        total = 0
        for d_str, d_val in days_data.items():
            try:
                dt = datetime.strptime(d_str, "%Y-%m-%d")
                if dt.year == year and dt.month == month:
                    total += d_val.get(store_key, {}).get("revenue", 0)
            except:
                pass
        return total
    
    monthly_totals = {}
    for m_offset in range(3):
        m_date = NOW - timedelta(days=30 * m_offset)
        ym = f"{m_date.year}-{m_date.month:02d}"
        monthly_totals[ym] = {
            "CEN": get_monthly_total(m_date.year, m_date.month, "CEN"),
            "GVS": get_monthly_total(m_date.year, m_date.month, "GVS"),
            "EDN": get_monthly_total(m_date.year, m_date.month, "EDN"),
        }
    
    # === GP Analysis (cross-store gaps + supplier scorecard) ===
    gp_rows = gp_data.get("rows", gp_data if isinstance(gp_data, list) else [])
    
    # Map branch codes
    def norm_branch(b):
        return {"HO": "CEN"}.get(b, b)
    
    # Aggregate by product per store
    product_by_store = defaultdict(lambda: defaultdict(lambda: {"rev": 0, "gp": 0, "qty": 0, "supplier": ""}))
    for r in gp_rows:
        branch = norm_branch(r.get("company_branch_code", ""))
        desc = r.get("line_item_description", "").strip()
        if not desc or branch not in ("CEN", "GVS", "EDN"):
            continue
        product_by_store[desc][branch]["rev"] += r.get("value_excl_after_discount", 0)
        product_by_store[desc][branch]["gp"] += r.get("gross_profit", 0)
        product_by_store[desc][branch]["qty"] += r.get("quantity", 0)
        product_by_store[desc][branch]["supplier"] = r.get("supplier_#", "")
    
    # Cross-store gap analysis: sold at CEN but NOT at GVS or EDN
    gaps = []
    for product, stores in product_by_store.items():
        cen_data = stores.get("CEN", {"rev": 0, "qty": 0})
        if cen_data["rev"] < 5000 and cen_data["qty"] < 20:
            continue
        missing_at = []
        if "GVS" not in stores or stores["GVS"]["rev"] < 100:
            missing_at.append("GVS")
        if "EDN" not in stores or stores["EDN"]["rev"] < 100:
            missing_at.append("EDN")
        if missing_at:
            gaps.append({
                "product": product,
                "cen_rev": cen_data["rev"],
                "cen_qty": cen_data["qty"],
                "cen_gp": cen_data["gp"],
                "supplier": cen_data["supplier"],
                "missing": missing_at
            })
    gaps.sort(key=lambda x: x["cen_rev"], reverse=True)
    
    # === Supplier ABC Scorecard ===
    supplier_agg = defaultdict(lambda: {"rev": 0, "gp": 0, "qty": 0, "products": 0})
    for r in gp_rows:
        sup = r.get("supplier_#", "")
        if not sup:
            continue
        supplier_agg[sup]["rev"] += r.get("value_excl_after_discount", 0)
        supplier_agg[sup]["gp"] += r.get("gross_profit", 0)
        supplier_agg[sup]["qty"] += r.get("quantity", 0)
        supplier_agg[sup]["products"] += 1
    
    # Sort by revenue and classify ABC
    sup_list = sorted(supplier_agg.items(), key=lambda x: x[1]["rev"], reverse=True)
    total_sup_rev = sum(s[1]["rev"] for s in sup_list)
    cumulative = 0
    for i, (code, data) in enumerate(sup_list):
        cumulative += data["rev"]
        pct = cumulative / total_sup_rev if total_sup_rev > 0 else 0
        if pct <= 0.80:
            data["abc"] = "A"
        elif pct <= 0.95:
            data["abc"] = "B"
        else:
            data["abc"] = "C"
        data["gp_pct"] = (data["gp"] / data["rev"] * 100) if data["rev"] > 0 else 0
        data["name"] = sup_name(code)
        data["code"] = code
    
    top_suppliers = sup_list[:30]
    
    # === Store comparison ===
    store_totals = {}
    for store in ["CEN", "GVS", "EDN"]:
        total_rev = sum(
            stores.get(store, {}).get("rev", 0)
            for stores in product_by_store.values()
        )
        total_gp = sum(
            stores.get(store, {}).get("gp", 0)
            for stores in product_by_store.values()
        )
        total_qty = sum(
            stores.get(store, {}).get("qty", 0)
            for stores in product_by_store.values()
        )
        store_totals[store] = {"rev": total_rev, "gp": total_gp, "qty": total_qty}
    
    # Top unique sellers per store (products that sell way more at one store vs others)
    unique_sellers = {}
    for store in ["CEN", "GVS", "EDN"]:
        candidates = []
        for product, stores in product_by_store.items():
            this = stores.get(store, {}).get("rev", 0)
            others = sum(stores.get(s, {}).get("rev", 0) for s in ["CEN", "GVS", "EDN"] if s != store)
            if this > 3000 and (others == 0 or this / max(others, 1) > 3):
                candidates.append({"product": product, "rev": this, "ratio": this / max(others, 1)})
        candidates.sort(key=lambda x: x["rev"], reverse=True)
        unique_sellers[store] = candidates[:5]
    
    # === AI Narrative ===
    days_in_month = NOW.day
    daily_avg = mtd_rev / days_in_month if days_in_month > 0 else 0
    projected_month = daily_avg * 30
    
    # Store tracking vs targets
    narrative_parts = []
    narrative_parts.append(f"Month-to-date revenue stands at R{mtd_rev:,.0f} through {days_in_month} days (R{daily_avg:,.0f}/day avg).")
    
    # Projected vs target
    total_target = sum(TARGETS.values())
    if projected_month > 0:
        pct_of_target = projected_month / total_target * 100
        if pct_of_target >= 100:
            narrative_parts.append(f"At this pace, you're projected to hit R{projected_month:,.0f} — {pct_of_target:.0f}% of the R{total_target/1e6:.1f}M combined target. On track.")
        else:
            shortfall = total_target - projected_month
            narrative_parts.append(f"Projected R{projected_month:,.0f} at current pace — R{shortfall:,.0f} short of the R{total_target/1e6:.1f}M target ({pct_of_target:.0f}%). Need to push.")
    
    # Per store
    for store, target in TARGETS.items():
        rev = store_mtd.get(store, {}).get("rev", 0)
        proj = (rev / days_in_month * 30) if days_in_month > 0 else 0
        pct = proj / target * 100 if target > 0 else 0
        if pct >= 105:
            narrative_parts.append(f"{store} is flying at {pct:.0f}% of target (R{rev:,.0f} MTD).")
        elif pct >= 95:
            narrative_parts.append(f"{store} is tracking on target at {pct:.0f}% (R{rev:,.0f} MTD).")
        elif pct >= 80:
            narrative_parts.append(f"{store} is trailing at {pct:.0f}% of target — needs a push in the last {30 - days_in_month} days.")
        else:
            narrative_parts.append(f"{store} is significantly behind at {pct:.0f}% of target. Red flag.")
    
    # Top mover
    if gp_rows:
        top = gp_rows[0]
        narrative_parts.append(f"Top performer: {top.get('line_item_description', '?')} with R{top.get('value_excl_after_discount', 0):,.0f} revenue and R{top.get('gross_profit', 0):,.0f} GP.")
    
    # Gap opportunity
    if gaps:
        total_gap_rev = sum(g["cen_rev"] for g in gaps[:10])
        narrative_parts.append(f"Cross-store opportunity: {len(gaps)} products selling at CEN but missing from other stores — top 10 represent R{total_gap_rev:,.0f} in CEN revenue that GVS/EDN are leaving on the table.")
    
    # GP concern
    if mtd_gp_pct > 0 and mtd_gp_pct < 33:
        narrative_parts.append(f"Blended GP at {mtd_gp_pct:.1f}% is below the 33.8% benchmark. Watch supplier pricing.")
    
    narrative = " ".join(narrative_parts)
    
    # === GENERATE HTML ===
    
    # Sparkline SVG generator
    def sparkline(values, color="#22c55e", width=120, height=30):
        if not values or max(values) == 0:
            return ""
        mn, mx = min(values), max(values)
        rng = mx - mn if mx != mn else 1
        points = []
        for i, v in enumerate(values):
            x = i / max(len(values) - 1, 1) * width
            y = height - ((v - mn) / rng * (height - 4) + 2)
            points.append(f"{x:.1f},{y:.1f}")
        pts = " ".join(points)
        return f'<svg width="{width}" height="{height}" style="vertical-align:middle"><polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/></svg>'
    
    # Format currency
    def fmt_r(v):
        if v >= 1_000_000:
            return f"R{v/1e6:.2f}M"
        elif v >= 1000:
            return f"R{v/1e3:.0f}K"
        else:
            return f"R{v:,.0f}"
    
    # Build KPI cards
    yesterday_rev = omni.get("yesterday", {}).get("combined", {}).get("revenue_excl", 0)
    
    # Weekly trend for sparkline
    combined_week = [c + g + e for c, g, e in zip(cen_week, gvs_week, edn_week)]
    
    # Store tracking %
    store_pcts = {}
    for store, target in TARGETS.items():
        rev = store_mtd.get(store, {}).get("rev", 0)
        proj = (rev / days_in_month * 30) if days_in_month > 0 else 0
        store_pcts[store] = proj / target * 100 if target > 0 else 0
    
    # Gap table rows
    gap_rows_html = ""
    for g in gaps[:25]:
        missing = ", ".join(g["missing"])
        gp_pct = (g["cen_gp"] / g["cen_rev"] * 100) if g["cen_rev"] > 0 else 0
        gap_rows_html += f"""<tr>
            <td>{g['product']}</td>
            <td>{sup_name(g['supplier'])}</td>
            <td class="num">{fmt_r(g['cen_rev'])}</td>
            <td class="num">{g['cen_qty']}</td>
            <td class="num">{gp_pct:.0f}%</td>
            <td class="missing">{missing}</td>
        </tr>"""
    
    # Supplier scorecard rows
    sup_rows_html = ""
    for code, data in top_suppliers:
        gp_class = "gp-high" if data["gp_pct"] >= 40 else ("gp-mid" if data["gp_pct"] >= 30 else "gp-low")
        abc_class = f"abc-{data['abc'].lower()}"
        sup_rows_html += f"""<tr>
            <td><span class="{abc_class}">{data['abc']}</span></td>
            <td>{data['name']}</td>
            <td class="num">{fmt_r(data['rev'])}</td>
            <td class="num {gp_class}">{data['gp_pct']:.1f}%</td>
            <td class="num">{data['qty']:,}</td>
            <td class="num">{data['products']}</td>
        </tr>"""
    
    # Unique sellers HTML
    unique_html = ""
    for store in ["CEN", "GVS", "EDN"]:
        items = unique_sellers.get(store, [])
        unique_html += f'<div class="unique-store"><h4>{store}</h4>'
        if items:
            for it in items:
                unique_html += f'<div class="unique-item">{it["product"]} <span class="num">{fmt_r(it["rev"])}</span></div>'
        else:
            unique_html += '<div class="unique-item dim">No standout unique sellers</div>'
        unique_html += '</div>'
    
    # Monthly trend chart data
    month_labels = sorted(monthly_totals.keys())
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Onelife Intelligence | V7</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Inter', sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
header {{ text-align: center; padding: 30px 0 20px; }}
header h1 {{ font-size: 28px; font-weight: 800; color: #f8fafc; }}
header h1 span {{ color: #22c55e; }}
header .subtitle {{ color: #94a3b8; font-size: 14px; margin-top: 4px; }}
header .date {{ color: #64748b; font-size: 12px; margin-top: 2px; }}

/* KPI Strip */
.kpi-strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
.kpi-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }}
.kpi-card .label {{ color: #94a3b8; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }}
.kpi-card .value {{ font-size: 28px; font-weight: 800; color: #f8fafc; margin: 8px 0 4px; }}
.kpi-card .sub {{ color: #64748b; font-size: 12px; }}
.kpi-card .value.green {{ color: #22c55e; }}
.kpi-card .value.red {{ color: #ef4444; }}
.kpi-card .value.blue {{ color: #3b82f6; }}

/* Store Progress Bars */
.store-progress {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; margin-bottom: 24px; }}
.store-progress h3 {{ color: #f8fafc; font-size: 16px; margin-bottom: 16px; }}
.progress-row {{ display: flex; align-items: center; margin-bottom: 12px; }}
.progress-row .store-name {{ width: 60px; font-weight: 700; font-size: 14px; }}
.progress-row .bar-container {{ flex: 1; background: #0f172a; border-radius: 6px; height: 24px; margin: 0 12px; position: relative; overflow: hidden; }}
.progress-row .bar {{ height: 100%; border-radius: 6px; transition: width 0.5s; display: flex; align-items: center; padding-left: 8px; font-size: 11px; font-weight: 700; color: #0f172a; }}
.progress-row .bar.on-track {{ background: linear-gradient(90deg, #22c55e, #4ade80); }}
.progress-row .bar.behind {{ background: linear-gradient(90deg, #f59e0b, #fbbf24); }}
.progress-row .bar.danger {{ background: linear-gradient(90deg, #ef4444, #f87171); }}
.progress-row .target {{ width: 120px; text-align: right; color: #64748b; font-size: 12px; }}
.progress-row .sparkline {{ width: 130px; text-align: center; }}

/* AI Narrative */
.narrative {{ background: linear-gradient(135deg, #1e293b, #1a2332); border: 1px solid #334155; border-left: 4px solid #22c55e; border-radius: 12px; padding: 24px; margin-bottom: 24px; }}
.narrative h3 {{ color: #22c55e; font-size: 14px; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }}
.narrative p {{ line-height: 1.7; color: #cbd5e1; font-size: 14px; }}

/* Section headers */
.section {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 24px; margin-bottom: 24px; overflow-x: auto; }}
.section h3 {{ color: #f8fafc; font-size: 16px; margin-bottom: 4px; }}
.section .section-sub {{ color: #64748b; font-size: 12px; margin-bottom: 16px; }}

/* Tables */
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; color: #94a3b8; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; padding: 8px 12px; border-bottom: 2px solid #334155; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; }}
tr:hover {{ background: #1e293b; }}
.section table tr:hover {{ background: #0f172a; }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.missing {{ color: #ef4444; font-weight: 600; }}
.gp-high {{ color: #22c55e; }}
.gp-mid {{ color: #f59e0b; }}
.gp-low {{ color: #ef4444; font-weight: 700; }}

/* ABC badges */
.abc-a {{ background: #22c55e; color: #0f172a; padding: 2px 8px; border-radius: 4px; font-weight: 800; font-size: 11px; }}
.abc-b {{ background: #3b82f6; color: #f8fafc; padding: 2px 8px; border-radius: 4px; font-weight: 800; font-size: 11px; }}
.abc-c {{ background: #64748b; color: #f8fafc; padding: 2px 8px; border-radius: 4px; font-weight: 800; font-size: 11px; }}

/* Unique sellers */
.unique-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
.unique-store h4 {{ color: #94a3b8; font-size: 13px; margin-bottom: 8px; }}
.unique-item {{ padding: 6px 0; border-bottom: 1px solid #334155; font-size: 13px; display: flex; justify-content: space-between; }}
.unique-item .num {{ color: #22c55e; }}
.dim {{ color: #475569; }}

/* Monthly trend */
.monthly-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; text-align: center; }}
.monthly-card {{ background: #0f172a; border-radius: 8px; padding: 16px; }}
.monthly-card .month {{ color: #94a3b8; font-size: 12px; font-weight: 600; }}
.monthly-card .total {{ font-size: 22px; font-weight: 800; color: #f8fafc; margin: 8px 0; }}
.monthly-card .breakdown {{ font-size: 12px; color: #64748b; }}

/* Footer */
footer {{ text-align: center; padding: 30px 0; color: #475569; font-size: 12px; }}
footer .lobster {{ color: #22c55e; }}

/* Responsive */
@media (max-width: 768px) {{
    .kpi-strip {{ grid-template-columns: repeat(2, 1fr); }}
    .unique-grid {{ grid-template-columns: 1fr; }}
    .monthly-grid {{ grid-template-columns: 1fr; }}
    .progress-row .sparkline {{ display: none; }}
}}
</style>
</head>
<body>
<div class="container">

<header>
    <h1>Onelife <span>Intelligence</span></h1>
    <div class="subtitle">3 Stores + Online | Real-time Business Intelligence</div>
    <div class="date">{NOW.strftime('%d %B %Y')} | Data as at {omni.get('last_updated', 'unknown')[:10]}</div>
</header>

<!-- KPI Strip -->
<div class="kpi-strip">
    <div class="kpi-card">
        <div class="label">MTD Revenue</div>
        <div class="value">{fmt_r(mtd_rev)}</div>
        <div class="sub">Day {days_in_month} of ~26 trading days</div>
    </div>
    <div class="kpi-card">
        <div class="label">MTD Gross Profit</div>
        <div class="value green">{fmt_r(mtd_gp)}</div>
        <div class="sub">{mtd_gp_pct:.1f}% blended GP</div>
    </div>
    <div class="kpi-card">
        <div class="label">Daily Average</div>
        <div class="value blue">{fmt_r(daily_avg)}</div>
        <div class="sub">Yesterday: {fmt_r(yesterday_rev)}</div>
    </div>
    <div class="kpi-card">
        <div class="label">Projected Month</div>
        <div class="value {'green' if projected_month >= sum(TARGETS.values()) else 'red'}">{fmt_r(projected_month)}</div>
        <div class="sub">Target: {fmt_r(sum(TARGETS.values()))}</div>
    </div>
</div>

<!-- Store Progress -->
<div class="store-progress">
    <h3>Store Tracking vs Target</h3>
    {"".join(f'''<div class="progress-row">
        <div class="store-name">{store}</div>
        <div class="bar-container">
            <div class="bar {'on-track' if store_pcts[store] >= 95 else ('behind' if store_pcts[store] >= 80 else 'danger')}" style="width: {min(store_pcts[store], 100):.0f}%">{store_pcts[store]:.0f}%</div>
        </div>
        <div class="sparkline">{sparkline({"CEN": cen_week, "GVS": gvs_week, "EDN": edn_week}[store])}</div>
        <div class="target">{fmt_r(store_mtd[store]["rev"])} / {fmt_r(TARGETS[store])}</div>
    </div>''' for store in ["CEN", "GVS", "EDN"])}
</div>

<!-- AI Narrative -->
<div class="narrative">
    <h3>&#x1f9e0; AI Briefing</h3>
    <p>{