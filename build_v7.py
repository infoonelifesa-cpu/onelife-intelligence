#!/usr/bin/env python3
"""
Onelife Intelligence Dashboard V7 — Builder
Generates index.html from cached Omni/Shopify data.
"""
import json, os, sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import calendar

SAST = timezone(timedelta(hours=2))
NOW = datetime.now(SAST)
WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
OUT_DIR = os.path.join(WORKSPACE, "onelife-intelligence")
TARGETS = {"CEN": 1_450_000, "GVS": 330_000, "EDN": 450_000}
STORE_LABELS = {"CEN": "Centurion", "GVS": "Glen Village", "EDN": "Edenvale"}

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
    """Format Rand value compactly: R1.37M, R886K, R45K"""
    if abs(v) >= 1_000_000: return f"R{v/1e6:.2f}M"
    elif abs(v) >= 1000: return f"R{v/1e3:.0f}K"
    else: return f"R{v:,.0f}"

def fmt_r_narrative(v):
    """Even more compact for narrative text: R1.37M, R886K"""
    if abs(v) >= 1_000_000: return f"R{v/1e6:.2f}M"
    elif abs(v) >= 10_000: return f"R{v/1e3:.0f}K"
    elif abs(v) >= 1000: return f"R{v/1e3:.1f}K"
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

    # MTD — compute from daily histories (more accurate than MTD combined endpoint)
    ho_history = omni.get("full_history", [])
    gvs_history = omni.get("gvs_history", [])
    edn_history = omni.get("edn_history", [])

    current_month = NOW.strftime("%Y-%m")
    days_in_month_total = calendar.monthrange(NOW.year, NOW.month)[1]  # 31 for March

    def sum_history(history, month):
        rev = sum(e.get("value_excl_after_discount", 0) for e in history if e.get("document_date", "").startswith(month))
        gp = sum(e.get("gross_profit", 0) for e in history if e.get("document_date", "").startswith(month))
        days = len([e for e in history if e.get("document_date", "").startswith(month)])
        return {"rev": rev, "gp": gp, "days": days}

    cen_mtd_data = sum_history(ho_history, current_month)
    gvs_mtd_data = sum_history(gvs_history, current_month)
    edn_mtd_data = sum_history(edn_history, current_month)

    store_mtd = {"CEN": cen_mtd_data, "GVS": gvs_mtd_data, "EDN": edn_mtd_data}

    mtd_rev = cen_mtd_data["rev"] + gvs_mtd_data["rev"] + edn_mtd_data["rev"]
    mtd_gp = cen_mtd_data["gp"] + gvs_mtd_data["gp"] + edn_mtd_data["gp"]
    mtd_gp_pct = (mtd_gp / mtd_rev * 100) if mtd_rev > 0 else 0

    days_elapsed = NOW.day
    days_remaining = days_in_month_total - days_elapsed

    # Store-level run rates and projections
    store_analysis = {}
    for s in ["CEN", "GVS", "EDN"]:
        data = store_mtd[s]
        trading_days = data["days"]
        run_rate = data["rev"] / trading_days if trading_days > 0 else 0
        # CEN closed Sundays (~22 trading days), GVS+EDN open 7 days (~26-31)
        if s == "CEN":
            remaining_trading = max(0, 22 - trading_days)  # ~22 trading days for CEN
        else:
            remaining_trading = max(0, days_in_month_total - (NOW - timedelta(days=1)).day)
        projected = data["rev"] + (run_rate * remaining_trading)
        pct_of_target = (projected / TARGETS[s] * 100) if TARGETS[s] > 0 else 0
        # Required daily to hit target
        shortfall = TARGETS[s] - data["rev"]
        required_daily = shortfall / remaining_trading if remaining_trading > 0 else 0
        store_analysis[s] = {
            "run_rate": run_rate,
            "projected": projected,
            "pct": pct_of_target,
            "trading_days": trading_days,
            "remaining_trading": remaining_trading,
            "required_daily": required_daily,
            "gap": shortfall,
            "gp": data["gp"],
            "gp_pct": (data["gp"] / data["rev"] * 100) if data["rev"] > 0 else 0,
        }

    # Combined projections
    combined_projected = sum(sa["projected"] for sa in store_analysis.values())
    total_target = sum(TARGETS.values())
    combined_daily_avg = mtd_rev / days_elapsed if days_elapsed > 0 else 0

    yesterday_data = omni.get("yesterday", {})
    yesterday_rev = yesterday_data.get("combined", {}).get("revenue_excl", 0)

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

    # Monthly totals — Omni histories for current month, daily cache for older
    monthly = {}
    for offset in range(3):
        dt = NOW - timedelta(days=30*offset)
        ym = f"{dt.year}-{dt.month:02d}"
        if offset == 0:
            monthly[ym] = {
                "CEN": cen_mtd_data["rev"],
                "GVS": gvs_mtd_data["rev"],
                "EDN": edn_mtd_data["rev"],
            }
        else:
            totals = {"CEN": 0, "GVS": 0, "EDN": 0}
            # Also check Omni history for this month
            cen_hist = sum_history(ho_history, ym)
            gvs_hist = sum_history(gvs_history, ym)
            edn_hist = sum_history(edn_history, ym)
            if cen_hist["rev"] > 0 or gvs_hist["rev"] > 0 or edn_hist["rev"] > 0:
                totals["CEN"] = cen_hist["rev"]
                totals["GVS"] = gvs_hist["rev"]
                totals["EDN"] = edn_hist["rev"]
            else:
                # Fall back to daily cache
                for d_str, d_val in days_data.items():
                    try:
                        dd = datetime.strptime(d_str, "%Y-%m-%d")
                        if dd.year == dt.year and dd.month == dt.month:
                            for s in totals:
                                totals[s] += d_val.get(s, {}).get("revenue", 0)
                    except: pass
            # Check completeness
            month_days = calendar.monthrange(dt.year, dt.month)[1]
            cache_days = len([k for k in days_data if k.startswith(ym)])
            if cache_days < month_days - 2:
                totals["_incomplete"] = True
                totals["_days"] = cache_days
                totals["_expected"] = month_days
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
    sup_agg = defaultdict(lambda: {"rev":0,"gp":0,"qty":0,"prods":set()})
    for r in gp_rows:
        s = r.get("supplier_#", "")
        if not s: continue
        sup_agg[s]["rev"] += r.get("value_excl_after_discount", 0)
        sup_agg[s]["gp"] += r.get("gross_profit", 0)
        sup_agg[s]["qty"] += r.get("quantity", 0)
        sup_agg[s]["prods"].add(r.get("line_item_description", ""))

    # Convert sets to counts for JSON compat
    for code in sup_agg:
        sup_agg[code]["prods"] = len(sup_agg[code]["prods"])

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

    # === AI NARRATIVE (compact numbers, richer analysis) ===
    F = fmt_r_narrative  # shorthand
    parts = []

    # Overview
    pct_target = combined_projected / total_target * 100 if total_target > 0 else 0
    parts.append(f"MTD revenue: {F(mtd_rev)} across 3 stores ({days_elapsed} days in). Running {F(combined_daily_avg)}/day.")

    if pct_target >= 100:
        parts.append(f"Projected {F(combined_projected)} for March ({pct_target:.0f}% of {F(total_target)} target). On track.")
    elif pct_target >= 90:
        parts.append(f"Projected {F(combined_projected)} ({pct_target:.0f}% of target). Close but needs a push in the final {days_remaining} days.")
    else:
        gap = total_target - combined_projected
        parts.append(f"Projected {F(combined_projected)} ({pct_target:.0f}% of target). {F(gap)} shortfall at current pace.")

    # Per-store analysis with run rates
    for s in ["CEN", "GVS", "EDN"]:
        sa = store_analysis[s]
        label = STORE_LABELS[s]
        if sa["pct"] >= 100:
            parts.append(f"{label}: {F(store_mtd[s]['rev'])} MTD at {F(sa['run_rate'])}/day. Projected {F(sa['projected'])} ({sa['pct']:.0f}% of target). Strong.")
        elif sa["pct"] >= 90:
            parts.append(f"{label}: {F(store_mtd[s]['rev'])} MTD at {F(sa['run_rate'])}/day. Needs {F(sa['required_daily'])}/day to hit {F(TARGETS[s])}.")
        else:
            parts.append(f"{label}: {F(store_mtd[s]['rev'])} MTD at {F(sa['run_rate'])}/day. Behind: needs {F(sa['required_daily'])}/day to close {F(sa['gap'])} gap.")

    # GP margin check
    if mtd_gp_pct < 33:
        parts.append(f"Blended GP at {mtd_gp_pct:.1f}%, below 33.8% benchmark. Check supplier pricing or discount controls.")
    else:
        parts.append(f"GP margin healthy at {mtd_gp_pct:.1f}%.")

    # Best/worst store GP
    best_gp_store = max(store_analysis, key=lambda s: store_analysis[s]["gp_pct"])
    worst_gp_store = min(store_analysis, key=lambda s: store_analysis[s]["gp_pct"])
    if store_analysis[best_gp_store]["gp_pct"] - store_analysis[worst_gp_store]["gp_pct"] > 3:
        parts.append(f"GP spread: {STORE_LABELS[best_gp_store]} {store_analysis[best_gp_store]['gp_pct']:.1f}% vs {STORE_LABELS[worst_gp_store]} {store_analysis[worst_gp_store]['gp_pct']:.1f}%. Investigate the gap.")

    # Top performer
    if gp_rows:
        top = gp_rows[0]
        parts.append(f"Top seller: {top.get('line_item_description','?')} ({F(top.get('value_excl_after_discount',0))} rev, {F(top.get('gross_profit',0))} GP).")

    # Cross-store opportunity
    if gaps:
        top10_gap = sum(g["rev"] for g in gaps[:10])
        parts.append(f"Cross-store opportunity: {len(gaps)} CEN products absent from GVS/EDN. Top 10 = {F(top10_gap)} untapped revenue.")

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

.kpi-strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px}
.kpi{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:16px}
.kpi .label{color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em}
.kpi .val{font-size:24px;font-weight:800;color:#f8fafc;margin:6px 0 4px}
.kpi .note{color:#64748b;font-size:11px}
.green{color:#22c55e!important} .red{color:#ef4444!important} .blue{color:#3b82f6!important} .yellow{color:#f59e0b!important} .grey{color:#94a3b8!important}

.card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;margin-bottom:20px;overflow-x:auto}
.card h3{color:#f8fafc;font-size:15px;margin-bottom:4px}
.card .desc{color:#64748b;font-size:11px;margin-bottom:14px}

.narrative{background:linear-gradient(135deg,#1e293b,#1a2332);border:1px solid #334155;border-left:4px solid #22c55e;border-radius:12px;padding:20px;margin-bottom:20px}
.narrative h3{color:#22c55e;font-size:13px;margin-bottom:10px}
.narrative p{line-height:1.7;color:#cbd5e1;font-size:13px}

/* Store Detail Cards */
.store-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px}
.store-card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:16px}
.store-card .sname{font-size:12px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}
.store-card .srev{font-size:22px;font-weight:800;color:#f8fafc;margin-bottom:4px}
.store-card .srow{display:flex;justify-content:space-between;font-size:12px;color:#94a3b8;padding:3px 0;border-bottom:1px solid #0f172a}
.store-card .srow .sv{color:#e2e8f0;font-weight:600}
.store-card .bar-mini{background:#0f172a;border-radius:4px;height:6px;margin:8px 0;overflow:hidden}
.store-card .bar-fill{height:100%;border-radius:4px}
.bar-fill.ok{background:#22c55e} .bar-fill.warn{background:#f59e0b} .bar-fill.bad{background:#ef4444}
.store-card .spct{font-size:11px;color:#64748b;text-align:right}
.store-card .highlight{color:#22c55e;font-weight:700}
.store-card .alert{color:#ef4444;font-weight:700}

.progress-row{display:flex;align-items:center;margin-bottom:12px}
.progress-row .sn{width:60px;font-weight:700;font-size:14px}
.progress-row .bar-wrap{flex:1;background:#0f172a;border-radius:6px;height:24px;margin:0 12px;overflow:hidden}
.progress-row .bar{height:100%;border-radius:6px;display:flex;align-items:center;padding-left:8px;font-size:11px;font-weight:700;color:#0f172a}
.bar.ok{background:linear-gradient(90deg,#22c55e,#4ade80)}
.bar.warn{background:linear-gradient(90deg,#f59e0b,#fbbf24)}
.bar.bad{background:linear-gradient(90deg,#ef4444,#f87171)}
.progress-row .spark{width:130px;text-align:center}
.progress-row .tgt{width:140px;text-align:right;color:#64748b;font-size:12px}

table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;color:#94a3b8;font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:.05em;padding:6px 10px;border-bottom:2px solid #334155}
td{padding:6px 10px;border-bottom:1px solid #1e293b22}
.card table tr:hover{background:#0f172a}
.num{text-align:right;font-variant-numeric:tabular-nums}
.miss{color:#ef4444;font-weight:600}
.gph{color:#22c55e} .gpm{color:#f59e0b} .gpl{color:#ef4444;font-weight:700}

.abc-a{background:#22c55e;color:#0f172a;padding:2px 6px;border-radius:4px;font-weight:800;font-size:10px}
.abc-b{background:#3b82f6;color:#f8fafc;padding:2px 6px;border-radius:4px;font-weight:800;font-size:10px}
.abc-c{background:#64748b;color:#f8fafc;padding:2px 6px;border-radius:4px;font-weight:800;font-size:10px}

.ugrid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.ustore h4{color:#94a3b8;font-size:12px;margin-bottom:6px}
.uitem{padding:5px 0;border-bottom:1px solid #334155;font-size:12px;display:flex;justify-content:space-between}
.uitem .num{color:#22c55e}
.dim{color:#475569}

.mgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;text-align:center}
.mcard{background:#0f172a;border-radius:8px;padding:14px}
.mcard .mo{color:#94a3b8;font-size:11px;font-weight:600}
.mcard .tot{font-size:20px;font-weight:800;color:#f8fafc;margin:6px 0}
.mcard .bd{font-size:11px;color:#64748b}
.mcard .incomplete{color:#f59e0b;font-size:10px;font-style:italic;margin-top:4px}

.data-warning{background:#1e293b;border:1px solid #f59e0b;border-radius:8px;padding:12px;margin-bottom:16px;font-size:12px;color:#fbbf24;display:flex;align-items:center;gap:8px}
.data-warning .icon{font-size:16px}

footer{text-align:center;padding:24px 0;color:#475569;font-size:11px}
footer .lo{color:#22c55e}

@media(max-width:768px){
.kpi-strip{grid-template-columns:repeat(2,1fr)}
.ugrid,.mgrid,.store-grid{grid-template-columns:1fr}
.progress-row .spark{display:none}
}
""")
    w('</style></head><body><div class="container">')

    # Header
    w(f'<header><h1>Onelife <span>Intelligence</span></h1>')
    w(f'<div class="sub">3 Stores + Online | Real-time Business Intelligence</div>')
    last_updated = omni.get("last_updated", "unknown")[:16].replace("T", " ")
    w(f'<div class="date">{NOW.strftime("%d %B %Y")} | Data as at {last_updated}</div>')
    w('</header>')

    # Data health warning if Omni API is down
    fetch_status = omni.get("fetch_status", "")
    if "error" in str(fetch_status).lower() or "Version" in str(fetch_status):
        w('<div class="data-warning"><span class="icon">&#x26a0;</span> Omni API may be down. Using cached data. Numbers may not reflect today\'s full trading.</div>')

    # KPI Strip
    proj_class = "green" if combined_projected >= total_target * 0.95 else ("yellow" if combined_projected >= total_target * 0.80 else "red")
    w('<div class="kpi-strip">')
    w(f'<div class="kpi"><div class="label">MTD Revenue</div><div class="val">{fmt_r(mtd_rev)}</div><div class="note">Day {days_elapsed} of {days_in_month_total}</div></div>')
    w(f'<div class="kpi"><div class="label">MTD Gross Profit</div><div class="val green">{fmt_r(mtd_gp)}</div><div class="note">{mtd_gp_pct:.1f}% blended GP</div></div>')
    w(f'<div class="kpi"><div class="label">Daily Run Rate</div><div class="val blue">{fmt_r(combined_daily_avg)}</div><div class="note">Yesterday: {fmt_r(yesterday_rev)}</div></div>')
    w(f'<div class="kpi"><div class="label">Projected Month</div><div class="val {proj_class}">{fmt_r(combined_projected)}</div><div class="note">Target: {fmt_r(total_target)}</div></div>')
    w('</div>')

    # === STORE DETAIL CARDS (NEW: per-store revenue, run rate, required rate, GP) ===
    w('<div class="store-grid">')
    for s in ["CEN", "GVS", "EDN"]:
        sa = store_analysis[s]
        data = store_mtd[s]
        cls = "ok" if sa["pct"] >= 95 else ("warn" if sa["pct"] >= 80 else "bad")
        status_cls = "highlight" if sa["pct"] >= 95 else ("alert" if sa["pct"] < 80 else "")

        w(f'<div class="store-card">')
        w(f'<div class="sname">{STORE_LABELS[s]}</div>')
        w(f'<div class="srev">{fmt_r(data["rev"])}</div>')
        w(f'<div class="bar-mini"><div class="bar-fill {cls}" style="width:{min(sa["pct"],100):.0f}%"></div></div>')
        w(f'<div class="spct">{sa["pct"]:.0f}% of {fmt_r(TARGETS[s])} target</div>')
        w(f'<div class="srow"><span>Run Rate</span><span class="sv">{fmt_r(sa["run_rate"])}/day</span></div>')
        w(f'<div class="srow"><span>Required Rate</span><span class="sv {status_cls}">{fmt_r(sa["required_daily"])}/day</span></div>')
        w(f'<div class="srow"><span>Projected</span><span class="sv">{fmt_r(sa["projected"])}</span></div>')
        w(f'<div class="srow"><span>GP Margin</span><span class="sv">{sa["gp_pct"]:.1f}%</span></div>')
        w(f'<div class="srow"><span>Trading Days</span><span class="sv">{sa["trading_days"]} done, {sa["remaining_trading"]} left</span></div>')
        w(f'</div>')
    w('</div>')

    # Store Progress Bars (kept for visual overview)
    w('<div class="card"><h3>Store Tracking vs Target</h3><div class="desc">Projected month-end based on current run rate</div>')
    for s in ["CEN","GVS","EDN"]:
        sa = store_analysis[s]
        cls = "ok" if sa["pct"]>=95 else ("warn" if sa["pct"]>=80 else "bad")
        spark = sparkline_svg({"CEN":cen_week,"GVS":gvs_week,"EDN":edn_week}[s])
        w(f'<div class="progress-row"><div class="sn">{s}</div>')
        w(f'<div class="bar-wrap"><div class="bar {cls}" style="width:{min(sa["pct"],100):.0f}%">{sa["pct"]:.0f}%</div></div>')
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
    rev_all = {s: sum(stores.get(s,{}).get("rev",0) for stores in pbs.values()) for s in ["CEN","GVS","EDN"]}
    gp_all = {s: sum(stores.get(s,{}).get("gp",0) for stores in pbs.values()) for s in ["CEN","GVS","EDN"]}
    gp_pcts = {s: (gp_all[s]/rev_all[s]*100 if rev_all[s]>0 else 0) for s in ["CEN","GVS","EDN"]}
    w(f'<tr><td>GP%</td><td class="num">{gp_pcts["CEN"]:.1f}%</td><td class="num">{gp_pcts["GVS"]:.1f}%</td><td class="num">{gp_pcts["EDN"]:.1f}%</td></tr>')
    w('</tbody></table>')

    # Unique sellers
    w('<h3 style="margin-top:16px;color:#f8fafc;font-size:13px">Unique Sellers by Store</h3>')
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
        total = sum(v for k,v in t.items() if not k.startswith("_"))
        w(f'<div class="mcard"><div class="mo">{ym}</div><div class="tot">{fmt_r(total)}</div>')
        w(f'<div class="bd">CEN: {fmt_r(t["CEN"])} | GVS: {fmt_r(t["GVS"])} | EDN: {fmt_r(t["EDN"])}</div>')
        if t.get("_incomplete"):
            w(f'<div class="incomplete">&#x26a0; Partial data ({t["_days"]}/{t["_expected"]} days)</div>')
        w('</div>')
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
    print(f"Sections: KPIs, Store Detail Cards, Store Progress, AI Narrative, Cross-Store Gaps ({len(gaps)}), Supplier ABC ({len(sup_sorted[:30])}), Store Comparison, Unique Sellers, Monthly Trends")

if __name__ == "__main__":
    main()