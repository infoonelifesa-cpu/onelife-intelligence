#!/usr/bin/env python3
"""
Onelife Intelligence Dashboard V7 — Builder
Generates index.html from cached Omni/Shopify data.
"""
import json, os, sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict

SAST = timezone(timedelta(hours=2))
NOW = datetime.now(SAST)
WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
OUT_DIR = os.path.join(WORKSPACE, "onelife-intelligence")
TARGETS = {"CEN": 1_450_000, "GVS": 330_000, "EDN": 450_000}

def load_json(path):
    try:
        with open(os.path.join(WORKSPACE, path)) as f:
            return json.load(f)
    except Exception as e:
        print(f"WARN: {path}: {e}", file=sys.stderr)
        return {}

def sup_name(code, names):
    full = names.get(code, code or "Unknown")
    if "(" in full: full = full.split("(")[0].strip()
    if " - " in full: full = full.split(" - ")[0].strip()
    return full[:30]

def fmt_r(v):
    if v >= 1_000_000: return f"R{v/1e6:.2f}M"
    elif v >= 1000: return f"R{v/1e3:.0f}K"
    else: return f"R{v:,.0f}"

def sparkline_svg(values, color="#22c55e", width=120, height=30):
    if not values or max(values) == 0: return ""
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1
    pts = []
    for i, v in enumerate(values):
        x = i / max(len(values)-1, 1) * width
        y = height - ((v - mn) / rng * (height-4) + 2)
        pts.append(f"{x:.1f},{y:.1f}")
    return f'<svg width="{width}" height="{height}" style="vertical-align:middle"><polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2"/></svg>'

def main():
    # Load data
    omni = load_json("memory/omni_cache.json")
    daily_cache = load_json("memory/daily-sales-cache.json")
    sup_names = load_json("memory/supplier_names.json")
    if isinstance(sup_names, list):
        sup_names = dict(sup_names)
    gp_data = load_json("memory/snapshots/2026-02/ana_popular_gp.json")
    
    # MTD
    mtd = omni.get("mtd", {})
    combined = mtd.get("combined", {})
    mtd_rev = combined.get("revenue_excl", 0)
    mtd_gp = combined.get("gross_profit", 0)
    mtd_gp_pct = combined.get("gp_pct", 0)
    days_in_month = NOW.day
    daily_avg = mtd_rev / days_in_month if days_in_month > 0 else 0
    projected = daily_avg * 30
    yesterday_rev = omni.get("yesterday", {}).get("combined", {}).get("revenue_excl", 0)
    
    # Store MTD
    store_mtd = {}
    for code in ["GVS", "EDN"]:
        s = mtd.get(code, {})
        store_mtd[code] = {"rev": s.get("revenue_excl", 0), "gp": s.get("gross_profit", 0)}
    store_mtd["CEN"] = {
        "rev": mtd_rev - store_mtd["GVS"]["rev"] - store_mtd["EDN"]["rev"],
        "gp": mtd_gp - store_mtd["GVS"]["gp"] - store_mtd["EDN"]["gp"],
    }
    
    # Weekly trends
    days_data = daily_cache.get("days", {})
    def week_trend(key, n=7):
        vals = []
        for i in range(n):
            d = (NOW - timedelta(days=i+1)).strftime("%Y-%m-%d")
            vals.append(days_data.get(d, {}).get(key, {}).get("revenue", 0))
        return list(reversed(vals))
    
    cen_week = week_trend("CEN")
    gvs_week = week_trend("GVS")
    edn_week = week_trend("EDN")
    
    # Monthly totals
    monthly = {}
    for offset in range(3):
        dt = NOW - timedelta(days=30*offset)
        ym = f"{dt.year}-{dt.month:02d}"
        totals = {"CEN": 0, "GVS": 0, "EDN": 0}
        for d_str, d_val in days_data.items():
            try:
                dd = datetime.strptime(d_str, "%Y-%m-%d")
                if dd.year == dt.year and dd.month == dt.month:
                    for s in totals:
                        totals[s] += d_val.get(s, {}).get("revenue", 0)
            except: pass
        monthly[ym] = totals
    
    # GP analysis
    gp_rows = gp_data.get("rows", gp_data if isinstance(gp_data, list) else [])
    norm = lambda b: "CEN" if b == "HO" else b
    
    # Product by store
    pbs = defaultdict(lambda: defaultdict(lambda: {"rev": 0, "gp": 0, "qty": 0, "sup": ""}))
    for r in gp_rows:
        b = norm(r.get("company_branch_code", ""))
        desc = r.get("line_item_description", "").strip()
        if not desc or b not in ("CEN", "GVS", "EDN"): continue
        pbs[desc][b]["rev"] += r.get("value_excl_after_discount", 0)
        pbs[desc][b]["gp"] += r.get("gross_profit", 0)
        pbs[desc][b]["qty"] += r.get("quantity", 0)
        pbs[desc][b]["sup"] = r.get("supplier_#", "")
    
    # Cross-store gaps
    gaps = []
    for prod, stores in pbs.items():
        cen = stores.get("CEN", {"rev":0,"qty":0,"gp":0,"sup":""})
        if cen["rev"] < 5000 and cen["qty"] < 20: continue
        missing = []
        if "GVS" not in stores or stores["GVS"]["rev"] < 100: missing.append("GVS")
        if "EDN" not in stores or stores["EDN"]["rev"] < 100: missing.append("EDN")
        if missing:
            gaps.append({"p": prod, "rev": cen["rev"], "qty": cen["qty"], "gp": cen["gp"], "sup": cen["sup"], "m": missing})
    gaps.sort(key=lambda x: x["rev"], reverse=True)
    
    # Supplier scorecard
    sup_agg = defaultdict(lambda: {"rev":0,"gp":0,"qty":0,"prods":0})
    for r in gp_rows:
        s = r.get("supplier_#", "")
        if not s: continue
        sup_agg[s]["rev"] += r.get("value_excl_after_discount", 0)
        sup_agg[s]["gp"] += r.get("gross_profit", 0)
        sup_agg[s]["qty"] += r.get("quantity", 0)
        sup_agg[s]["prods"] += 1
    
    sup_sorted = sorted(sup_agg.items(), key=lambda x: x[1]["rev"], reverse=True)
    total_rev_all = sum(s[1]["rev"] for s in sup_sorted)
    cum = 0
    for code, data in sup_sorted:
        cum += data["rev"]
        pct = cum / total_rev_all if total_rev_all > 0 else 0
        data["abc"] = "A" if pct <= 0.80 else ("B" if pct <= 0.95 else "C")
        data["gp_pct"] = (data["gp"]/data["rev"]*100) if data["rev"]>0 else 0
    
    # Unique sellers per store
    unique = {}
    for store in ["CEN","GVS","EDN"]:
        cands = []
        for prod, stores in pbs.items():
            this = stores.get(store, {}).get("rev", 0)
            others = sum(stores.get(s,{}).get("rev",0) for s in ["CEN","GVS","EDN"] if s!=store)
            if this > 3000 and (others == 0 or this/max(others,1) > 3):
                cands.append({"p": prod, "rev": this})
        cands.sort(key=lambda x: x["rev"], reverse=True)
        unique[store] = cands[:5]
    
    # Store pcts
    store_pcts = {}
    for s, t in TARGETS.items():
        r = store_mtd[s]["rev"]
        p = (r/days_in_month*30) if days_in_month > 0 else 0
        store_pcts[s] = p/t*100 if t > 0 else 0
    
    # === AI NARRATIVE ===
    parts = []
    parts.append(f"Month-to-date revenue is R{mtd_rev:,.0f} through {days_in_month} trading days (R{daily_avg:,.0f}/day average).")
    total_target = sum(TARGETS.values())
    pct_target = projected/total_target*100 if total_target > 0 else 0
    if pct_target >= 100:
        parts.append(f"Projected R{projected:,.0f} for the month, {pct_target:.0f}% of the R{total_target/1e6:.1f}M target. On track.")
    else:
        parts.append(f"Projected R{projected:,.0f} at current pace: {pct_target:.0f}% of target. Need R{(total_target-projected):,.0f} more run rate.")
    
    for s in ["CEN","GVS","EDN"]:
        p = store_pcts[s]
        r = store_mtd[s]["rev"]
        if p >= 105: parts.append(f"{s} is flying at {p:.0f}% of target (R{r:,.0f} MTD).")
        elif p >= 95: parts.append(f"{s} tracking on target at {p:.0f}%.")
        elif p >= 80: parts.append(f"{s} trailing at {p:.0f}% of target. Needs a push.")
        else: parts.append(f"{s} significantly behind at {p:.0f}%. Red flag.")
    
    if gp_rows:
        top = gp_rows[0]
        parts.append(f"Top performer: {top.get('line_item_description','?')} (R{top.get('value_excl_after_discount',0):,.0f} rev, R{top.get('gross_profit',0):,.0f} GP).")
    
    if gaps:
        top10_gap = sum(g["rev"] for g in gaps[:10])
        parts.append(f"Cross-store opportunity: {len(gaps)} products selling at CEN but absent from other stores. Top 10 represent R{top10_gap:,.0f} in untapped revenue for GVS/EDN.")
    
    if mtd_gp_pct and mtd_gp_pct < 33:
        parts.append(f"GP margin at {mtd_gp_pct:.1f}% is below the 33.8% benchmark. Check supplier pricing.")
    
    narrative = " ".join(parts)
    
    # === BUILD HTML ===
    lines = []
    w = lines.append
    
    w('<!DOCTYPE html>')
    w('<html lang="en"><head>')
    w('<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">')
    w('<title>Onelife Intelligence | V7</title>')
    w('<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">')
    w('<style>')
    w("""
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
.container{max-width:1400px;margin:0 auto;padding:20px}
header{text-align:center;padding:30px 0 20px}
header h1{font-size:28px;font-weight:800;color:#f8fafc}
header h1 span{color:#22c55e}
header .sub{color:#94a3b8;font-size:14px;margin-top:4px}
header .date{color:#64748b;font-size:12px;margin-top:2px}

.kpi-strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}
.kpi{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px}
.kpi .label{color:#94a3b8;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.05em}
.kpi .val{font-size:28px;font-weight:800;color:#f8fafc;margin:8px 0 4px}
.kpi .note{color:#64748b;font-size:12px}
.green{color:#22c55e!important} .red{color:#ef4444!important} .blue{color:#3b82f6!important} .yellow{color:#f59e0b!important}

.card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px;margin-bottom:24px;overflow-x:auto}
.card h3{color:#f8fafc;font-size:16px;margin-bottom:4px}
.card .desc{color:#64748b;font-size:12px;margin-bottom:16px}

.narrative{background:linear-gradient(135deg,#1e293b,#1a2332);border:1px solid #334155;border-left:4px solid #22c55e;border-radius:12px;padding:24px;margin-bottom:24px}
.narrative h3{color:#22c55e;font-size:14px;margin-bottom:12px}
.narrative p{line-height:1.7;color:#cbd5e1;font-size:14px}

.progress-row{display:flex;align-items:center;margin-bottom:12px}
.progress-row .sn{width:60px;font-weight:700;font-size:14px}
.progress-row .bar-wrap{flex:1;background:#0f172a;border-radius:6px;height:24px;margin:0 12px;overflow:hidden}
.progress-row .bar{height:100%;border-radius:6px;display:flex;align-items:center;padding-left:8px;font-size:11px;font-weight:700;color:#0f172a}
.bar.ok{background:linear-gradient(90deg,#22c55e,#4ade80)}
.bar.warn{background:linear-gradient(90deg,#f59e0b,#fbbf24)}
.bar.bad{background:linear-gradient(90deg,#ef4444,#f87171)}
.progress-row .spark{width:130px;text-align:center}
.progress-row .tgt{width:140px;text-align:right;color:#64748b;font-size:12px}

table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:#94a3b8;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.05em;padding:8px 12px;border-bottom:2px solid #334155}
td{padding:8px 12px;border-bottom:1px solid #1e293b22}
.card table tr:hover{background:#0f172a}
.num{text-align:right;font-variant-numeric:tabular-nums}
.miss{color:#ef4444;font-weight:600}
.gph{color:#22c55e} .gpm{color:#f59e0b} .gpl{color:#ef4444;font-weight:700}

.abc-a{background:#22c55e;color:#0f172a;padding:2px 8px;border-radius:4px;font-weight:800;font-size:11px}
.abc-b{background:#3b82f6;color:#f8fafc;padding:2px 8px;border-radius:4px;font-weight:800;font-size:11px}
.abc-c{background:#64748b;color:#f8fafc;padding:2px 8px;border-radius:4px;font-weight:800;font-size:11px}

.ugrid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.ustore h4{color:#94a3b8;font-size:13px;margin-bottom:8px}
.uitem{padding:6px 0;border-bottom:1px solid #334155;font-size:13px;display:flex;justify-content:space-between}
.uitem .num{color:#22c55e}
.dim{color:#475569}

.mgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;text-align:center}
.mcard{background:#0f172a;border-radius:8px;padding:16px}
.mcard .mo{color:#94a3b8;font-size:12px;font-weight:600}
.mcard .tot{font-size:22px;font-weight:800;color:#f8fafc;margin:8px 0}
.mcard .bd{font-size:12px;color:#64748b}

footer{text-align:center;padding:30px 0;color:#475569;font-size:12px}
footer .lo{color:#22c55e}

@media(max-width:768px){
.kpi-strip{grid-template-columns:repeat(2,1fr)}
.ugrid,.mgrid{grid-template-columns:1fr}
.progress-row .spark{display:none}
}
""")
    w('</style></head><body><div class="container">')
    
    # Header
    w(f'<header><h1>Onelife <span>Intelligence</span></h1>')
    w(f'<div class="sub">3 Stores + Online | Real-time Business Intelligence</div>')
    w(f'<div class="date">{NOW.strftime("%d %B %Y")} | Data as at {omni.get("last_updated","unknown")[:10]}</div>')
    w('</header>')
    
    # KPI Strip
    proj_class = "green" if projected >= total_target else "red"
    w('<div class="kpi-strip">')
    w(f'<div class="kpi"><div class="label">MTD Revenue</div><div class="val">{fmt_r(mtd_rev)}</div><div class="note">Day {days_in_month} of ~26 trading days</div></div>')
    w(f'<div class="kpi"><div class="label">MTD Gross Profit</div><div class="val green">{fmt_r(mtd_gp)}</div><div class="note">{mtd_gp_pct:.1f}% blended GP</div></div>')
    w(f'<div class="kpi"><div class="label">Daily Average</div><div class="val blue">{fmt_r(daily_avg)}</div><div class="note">Yesterday: {fmt_r(yesterday_rev)}</div></div>')
    w(f'<div class="kpi"><div class="label">Projected Month</div><div class="val {proj_class}">{fmt_r(projected)}</div><div class="note">Target: {fmt_r(total_target)}</div></div>')
    w('</div>')
    
    # Store Progress
    w('<div class="card"><h3>Store Tracking vs Target</h3><div class="desc">Projected month-end based on MTD daily average</div>')
    for s in ["CEN","GVS","EDN"]:
        p = store_pcts[s]
        cls = "ok" if p>=95 else ("warn" if p>=80 else "bad")
        spark = sparkline_svg({"CEN":cen_week,"GVS":gvs_week,"EDN":edn_week}[s])
        w(f'<div class="progress-row"><div class="sn">{s}</div>')
        w(f'<div class="bar-wrap"><div class="bar {cls}" style="width:{min(p,100):.0f}%">{p:.0f}%</div></div>')
        w(f'<div class="spark">{spark}</div>')
        w(f'<div class="tgt">{fmt_r(store_mtd[s]["rev"])} / {fmt_r(TARGETS[s])}</div></div>')
    w('</div>')
    
    # AI Narrative
    w(f'<div class="narrative"><h3>&#x1f9e0; AI Briefing</h3><p>{narrative}</p></div>')
    
    # Cross-Store Gap Analysis
    w('<div class="card"><h3>Cross-Store Product Gaps</h3>')
    w(f'<div class="desc">Products selling well at CEN but missing from other stores. {len(gaps)} opportunities found.</div>')
    w('<table><thead><tr><th>Product</th><th>Supplier</th><th class="num">CEN Revenue</th><th class="num">CEN Units</th><th class="num">GP%</th><th>Missing At</th></tr></thead><tbody>')
    for g in gaps[:25]:
        gpp = (g["gp"]/g["rev"]*100) if g["rev"]>0 else 0
        gpc = "gph" if gpp>=40 else ("gpm" if gpp>=30 else "gpl")
        w(f'<tr><td>{g["p"]}</td><td>{sup_name(g["sup"], sup_names)}</td><td class="num">{fmt_r(g["rev"])}</td><td class="num">{g["qty"]}</td><td class="num {gpc}">{gpp:.0f}%</td><td class="miss">{", ".join(g["m"])}</td></tr>')
    w('</tbody></table></div>')
    
    # Supplier ABC Scorecard
    w('<div class="card"><h3>Supplier ABC Scorecard</h3>')
    w(f'<div class="desc">Top 30 suppliers by revenue. A = top 80% cumulative, B = next 15%, C = bottom 5%.</div>')
    w('<table><thead><tr><th>Class</th><th>Supplier</th><th class="num">Revenue</th><th class="num">GP%</th><th class="num">Units</th><th class="num">Products</th></tr></thead><tbody>')
    for code, data in sup_sorted[:30]:
        gpc = "gph" if data["gp_pct"]>=40 else ("gpm" if data["gp_pct"]>=30 else "gpl")
        ac = f'abc-{data["abc"].lower()}'
        w(f'<tr><td><span class="{ac}">{data["abc"]}</span></td><td>{sup_name(code, sup_names)}</td><td class="num">{fmt_r(data["rev"])}</td><td class="num {gpc}">{data["gp_pct"]:.1f}%</td><td class="num">{data["qty"]:,}</td><td class="num">{data["prods"]}</td></tr>')
    w('</tbody></table></div>')
    
    # Store Comparison
    w('<div class="card"><h3>Store Comparison</h3><div class="desc">Revenue, GP, and unique sellers per store (snapshot period)</div>')
    w('<table><thead><tr><th>Metric</th><th class="num">CEN</th><th class="num">GVS</th><th class="num">EDN</th></tr></thead><tbody>')
    for label, key in [("Revenue (snapshot)", "rev"), ("Gross Profit", "gp"), ("Units Sold", "qty")]:
        vals = {}
        for s in ["CEN","GVS","EDN"]:
            vals[s] = sum(stores.get(s,{}).get(key,0) for stores in pbs.values())
        if key == "qty":
            w(f'<tr><td>{label}</td><td class="num">{vals["CEN"]:,}</td><td class="num">{vals["GVS"]:,}</td><td class="num">{vals["EDN"]:,}</td></tr>')
        else:
            w(f'<tr><td>{label}</td><td class="num">{fmt_r(vals["CEN"])}</td><td class="num">{fmt_r(vals["GVS"])}</td><td class="num">{fmt_r(vals["EDN"])}</td></tr>')
    
    # GP%
    for s in ["CEN","GVS","EDN"]:
        tr = sum(stores.get(s,{}).get("rev",0) for stores in pbs.values())
        tg = sum(stores.get(s,{}).get("gp",0) for stores in pbs.values())
        store_pbs_gp = (tg/tr*100) if tr>0 else 0
        # Store it for the row
    rev_all = {s: sum(stores.get(s,{}).get("rev",0) for stores in pbs.values()) for s in ["CEN","GVS","EDN"]}
    gp_all = {s: sum(stores.get(s,{}).get("gp",0) for stores in pbs.values()) for s in ["CEN","GVS","EDN"]}
    gp_pcts = {s: (gp_all[s]/rev_all[s]*100 if rev_all[s]>0 else 0) for s in ["CEN","GVS","EDN"]}
    w(f'<tr><td>GP%</td><td class="num">{gp_pcts["CEN"]:.1f}%</td><td class="num">{gp_pcts["GVS"]:.1f}%</td><td class="num">{gp_pcts["EDN"]:.1f}%</td></tr>')
    w('</tbody></table>')
    
    # Unique sellers
    w('<h3 style="margin-top:20px;color:#f8fafc;font-size:14px">Unique Sellers by Store</h3>')
    w('<div class="desc">Products that sell 3x+ more at one store vs others</div>')
    w('<div class="ugrid">')
    for s in ["CEN","GVS","EDN"]:
        w(f'<div class="ustore"><h4>{s}</h4>')
        items = unique.get(s, [])
        if items:
            for it in items:
                w(f'<div class="uitem">{it["p"]} <span class="num">{fmt_r(it["rev"])}</span></div>')
        else:
            w('<div class="uitem dim">No standout unique sellers</div>')
        w('</div>')
    w('</div></div>')
    
    # Monthly Trends
    w('<div class="card"><h3>Monthly Revenue Trends</h3><div class="desc">Last 3 months by store</div>')
    w('<div class="mgrid">')
    for ym in sorted(monthly.keys()):
        t = monthly[ym]
        total = sum(t.values())
        w(f'<div class="mcard"><div class="mo">{ym}</div><div class="tot">{fmt_r(total)}</div>')
        w(f'<div class="bd">CEN: {fmt_r(t["CEN"])} | GVS: {fmt_r(t["GVS"])} | EDN: {fmt_r(t["EDN"])}</div></div>')
    w('</div></div>')
    
    # Footer
    w(f'<footer>Onelife Intelligence V7 &middot; {NOW.strftime("%d %B %Y %H:%M")} SAST &middot; 3 stores + online &middot; Powered by <span class="lo">Jarvis</span> &#x1f99e;</footer>')
    w('</div></body></html>')
    
    # Write
    html = "\n".join(lines)
    out_path = os.path.join(OUT_DIR, "index.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Dashboard written: {len(html):,} bytes -> {out_path}")
    print(f"Sections: KPIs, Store Progress, AI Narrative, Cross-Store Gaps ({len(gaps)}), Supplier ABC ({len(sup_sorted[:30])}), Store Comparison, Unique Sellers, Monthly Trends")

if __name__ == "__main__":
    main()
