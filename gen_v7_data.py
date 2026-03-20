#!/usr/bin/env python3
"""V7 data cruncher - produces v7_data.json for the HTML builder"""
import json
from collections import defaultdict
from datetime import datetime

BASE = "/Users/naadir/.openclaw/workspace/memory"
SNAP = f"{BASE}/snapshots/2026-02"

def load(p):
    with open(p) as f: return json.load(f)

print("Loading data...")
gp_data     = load(f"{SNAP}/ana_popular_gp.json")
sales_data  = load(f"{SNAP}/ana_sales_per_supplier.json")
omni        = load(f"{BASE}/omni_cache.json")
daily_cache = load(f"{BASE}/daily-sales-cache.json")
sup_map     = load(f"{BASE}/supplier_names.json")
edn_al      = load(f"{BASE}/edn-stock-alert-latest.json")

gp_rows    = gp_data["rows"]
sales_rows = sales_data["rows"]
print(f"  {len(gp_rows):,} GP rows, {len(sales_rows):,} sales rows")

# ── KPI ───────────────────────────────────────────────────────────────────────
mtd       = omni["mtd"]
full_hist = omni.get("full_history",[])
week_data = omni.get("week",[])
gvs_wk    = omni.get("gvs_week",[])
edn_wk    = omni.get("edn_week",[])
mtd_rev   = mtd["combined"]["revenue_excl"]
mtd_gp    = mtd["combined"]["gp_pct"]
mtd_days  = len(full_hist) or 1
avg_daily = mtd_rev / mtd_days
cen_mtd   = mtd["HO"]["revenue_excl"]
gvs_mtd   = mtd["GVS"]["revenue_excl"]
edn_mtd   = mtd["EDN"]["revenue_excl"]
today_d   = omni.get("today",{})
today_rev = today_d.get("combined",{}).get("revenue_excl",0)
today_gp  = today_d.get("combined",{}).get("gp_pct",0)

# ── DAILY TRENDS ─────────────────────────────────────────────────────────────
daily_days = daily_cache["days"]
feb_days = {k:v for k,v in daily_days.items() if k.startswith("2026-02")}
mar_days = {k:v for k,v in daily_days.items() if k.startswith("2026-03")}

def ssum(dd,s): return sum(v.get(s,{}).get("revenue",0) for v in dd.values())
feb_cen = ssum(feb_days,"CEN"); feb_gvs = ssum(feb_days,"GVS"); feb_edn = ssum(feb_days,"EDN")
nf = len(feb_days) or 1; nm = len(mar_days) or 1

def tpct(old,new): return ((new-old)/old*100) if old else 0
cen_trend = tpct(feb_cen/nf, cen_mtd/nm)
gvs_trend = tpct(feb_gvs/nf, gvs_mtd/nm)
edn_trend = tpct(feb_edn/nf, edn_mtd/nm)

# ── PRODUCT INDEX ─────────────────────────────────────────────────────────────
skip = ["posgeld","postage","courier","voucher"]
by_code = defaultdict(lambda: defaultdict(lambda:{"revenue":0,"gp":0,"qty":0,"desc":""}))
for r in gp_rows:
    c = r["stock_code"]; b = r["company_branch_code"]
    by_code[c][b]["revenue"] += r.get("value_excl_after_discount",0)
    by_code[c][b]["gp"]      += r.get("gross_profit",0)
    by_code[c][b]["qty"]     += r.get("quantity",0)
    if not by_code[c][b]["desc"]:
        by_code[c][b]["desc"] = r.get("line_item_description","")

top_cen = sorted(
    [(c,d["HO"]) for c,d in by_code.items()
     if "HO" in d and not any(k in d["HO"]["desc"].lower() for k in skip)],
    key=lambda x: x[1]["revenue"], reverse=True)
top_prod     = top_cen[0][1]["desc"] if top_cen else "N/A"
top_prod_rev = top_cen[0][1]["revenue"] if top_cen else 0

# ── CROSS-STORE GAPS ──────────────────────────────────────────────────────────
gaps = []
for code, stores in by_code.items():
    if "HO" not in stores: continue
    ho = stores["HO"]
    if any(k in ho["desc"].lower() for k in skip): continue
    if ho["revenue"] < 5000 and ho["qty"] < 20: continue
    miss = [b for b in ["GVS","EDN"] if b not in stores]
    if not miss: continue
    gp = (ho["gp"]/ho["revenue"]*100) if ho["revenue"] else 0
    gaps.append({"desc":ho["desc"],"rev":round(ho["revenue"],0),
                 "qty":ho["qty"],"gp":round(gp,1),"miss":miss})
gaps.sort(key=lambda x: x["rev"], reverse=True)
print(f"  Gap products: {len(gaps)}")

# ── SUPPLIER ABC ──────────────────────────────────────────────────────────────
sup_d = defaultdict(lambda:{"revenue":0,"gp":0,"qty":0})
for r in gp_rows:
    s = r.get("supplier_#","")
    if not s: continue
    sup_d[s]["revenue"] += r.get("value_excl_after_discount",0)
    sup_d[s]["gp"]      += r.get("gross_profit",0)
    sup_d[s]["qty"]     += r.get("quantity",0)

top30 = sorted(sup_d.items(), key=lambda x: x[1]["revenue"], reverse=True)[:30]
tot_r = sum(d["revenue"] for _,d in top30)
cum = 0; abc_sups = []
for s,d in top30:
    cum += d["revenue"]
    pct = cum/tot_r*100 if tot_r else 0
    abc = "A" if pct<=80 else ("B" if pct<=95 else "C")
    gp = (d["gp"]/d["revenue"]*100) if d["revenue"] else 0
    name = sup_map.get(s,s).split("(")[0].strip()[:28]
    abc_sups.append({"code":s,"name":name,"rev":round(d["revenue"],0),
                     "gp":round(gp,1),"qty":d["qty"],"abc":abc})

lowest_gp = min(abc_sups[:20], key=lambda x: x["gp"])

# ── STORE MATRIX ──────────────────────────────────────────────────────────────
s_rev = defaultdict(float); s_gp = defaultdict(float); s_ref = defaultdict(set)
for r in sales_rows:
    b = r.get("company_branch_code","")
    if b in ("HO","GVS","EDN"):
        s_rev[b] += r.get("value_excl_after_discount",0)
        if r.get("reference"): s_ref[b].add(r["reference"])
for r in gp_rows:
    b = r.get("company_branch_code","")
    if b in ("HO","GVS","EDN"): s_gp[b] += r.get("gross_profit",0)

sp = defaultdict(lambda: defaultdict(lambda:{"revenue":0,"desc":""}))
for r in gp_rows:
    b = r.get("company_branch_code",""); c = r["stock_code"]
    sp[b][c]["revenue"] += r.get("value_excl_after_discount",0)
    if not sp[b][c]["desc"]: sp[b][c]["desc"] = r.get("line_item_description","")

def top_uniq(branch, n=5):
    tb = s_rev.get(branch,1) or 1
    ta = sum(s_rev.values()) or 1; ot = (ta-tb) or 1
    scored = []
    for code,d in sp[branch].items():
        if not d["desc"] or any(k in d["desc"].lower() for k in skip) or d["revenue"]<500:
            continue
        bs = d["revenue"]/tb
        ore = sum(sp[b2][code]["revenue"] for b2 in sp if b2 != branch)
        os_ = ore/ot
        idx = (bs/os_) if os_ > 0 else 999
        scored.append({"desc":d["desc"],"rev":round(d["revenue"],0),"idx":round(idx,1)})
    scored.sort(key=lambda x: x["idx"], reverse=True)
    return scored[:n]

matrix = {}
for b,lbl in [("HO","CEN"),("GVS","GVS"),("EDN","EDN")]:
    rev = s_rev.get(b,0); gp = s_gp.get(b,0); txn = len(s_ref.get(b,set()))
    matrix[lbl] = {"rev":round(rev,0),"gp":round((gp/rev*100) if rev else 0,1),
                   "txn":txn,"basket":round(rev/txn if txn else 0,0),"top":top_uniq(b)}

# ── 30-DAY TREND ─────────────────────────────────────────────────────────────
trend = []
for day in sorted(daily_days.keys())[-30:]:
    d = daily_days[day]
    cen_ = d.get("CEN",{}).get("revenue",0) or d.get("HO",{}).get("revenue",0)
    gvs_ = d.get("GVS",{}).get("revenue",0)
    edn_ = d.get("EDN",{}).get("revenue",0)
    trend.append({"date":day[-5:],"cen":round(cen_,0),"gvs":round(gvs_,0),
                  "edn":round(edn_,0),"total":round(d.get("total_revenue",cen_+gvs_+edn_),0)})

# ── WEEK TOTALS ───────────────────────────────────────────────────────────────
wk_t = sum(d.get("value_excl_after_discount",0) for d in week_data)
wk_g = sum(d.get("value_excl_after_discount",0) for d in gvs_wk)
wk_e = sum(d.get("value_excl_after_discount",0) for d in edn_wk)
wk_c = wk_t - wk_g - wk_e

# ── ALERTS ────────────────────────────────────────────────────────────────────
alerts = {
    "critical": edn_al["alerts"]["critical"][:22],
    "warning":  edn_al["alerts"]["warning"][:20],
    "info":     edn_al["alerts"].get("info",[])[:9]
}

# ── NARRATIVE ─────────────────────────────────────────────────────────────────
cen_dir = "above" if cen_trend >= 0 else "below"
gvs_dir = "ahead of" if gvs_trend >= 0 else "behind"
edn_dir = "ahead of" if edn_trend >= 0 else "behind"
gvs_cmt = "strong growth" if gvs_trend >= 5 else ("steady" if gvs_trend >= 0 else "needs a push")
edn_cmt = "on track" if edn_trend >= -5 else "worth investigating"

narrative = (
    f"March is tracking well \u2014 <strong>R{mtd_rev:,.0f} MTD</strong> across 3 stores over "
    f"{mtd_days} trading days. "
    f"CEN is your engine: <strong>R{cen_mtd:,.0f} MTD</strong>, running {abs(cen_trend):.0f}% "
    f"{cen_dir} Feb\u2019s daily pace. "
    f"GVS at R{gvs_mtd:,.0f} is {abs(gvs_trend):.0f}% {gvs_dir} Feb daily ({gvs_cmt}). "
    f"EDN at R{edn_mtd:,.0f} is {abs(edn_trend):.0f}% {edn_dir} Feb \u2014 {edn_cmt}. "
    f"Top mover at CEN: <strong>{top_prod}</strong> (R{top_prod_rev:,.0f}). "
    f"Watch <strong>{lowest_gp['name']}</strong> ({lowest_gp['code']}) \u2014 lowest GP in top 20 "
    f"at {lowest_gp['gp']:.1f}%. "
    f"\u26a0\ufe0f EDN stock crisis: <strong>{len(alerts['critical'])} items completely out of "
    f"stock</strong>, {len(alerts['warning'])} more dangerously low \u2014 every day is lost GP. "
    f"Blended GP: <strong>{mtd_gp:.1f}%</strong> "
    f"{'\u2713 healthy' if mtd_gp >= 35 else '\u26a0 below target'}. "
    f"This week: CEN R{wk_c:,.0f} | GVS R{wk_g:,.0f} | EDN R{wk_e:,.0f}."
)

# ── OUTPUT ────────────────────────────────────────────────────────────────────
output = {
    "generated": datetime.now().strftime("%d %B %Y %H:%M"),
    "date_range": mtd.get("date_range","Mar 2026"),
    "kpi": {
        "mtd_rev": mtd_rev, "mtd_gp": mtd_gp, "mtd_days": mtd_days,
        "avg_daily": round(avg_daily,0),
        "cen_mtd": cen_mtd, "gvs_mtd": gvs_mtd, "edn_mtd": edn_mtd,
        "cen_trend": round(cen_trend,1), "gvs_trend": round(gvs_trend,1),
        "edn_trend": round(edn_trend,1),
        "today_rev": today_rev, "today_gp": today_gp,
    },
    "narrative": narrative,
    "gaps": gaps[:30],
    "suppliers": abc_sups,
    "matrix": matrix,
    "trend": trend,
    "alerts": alerts,
    "week": {
        "cen": round(wk_c,0), "gvs": round(wk_g,0), "edn": round(wk_e,0),
        "total": round(wk_t,0),
        "daily": [{"date":d.get("document_date","")[-5:],
                   "rev":round(d.get("value_excl_after_discount",0),0)}
                  for d in week_data]
    }
}

out_path = "/Users/naadir/.openclaw/workspace/onelife-intelligence/v7_data.json"
with open(out_path, "w") as f:
    json.dump(output, f, indent=1)
print(f"\nData written to {out_path}")
print(f"  Gaps: {len(gaps[:30])}, Suppliers: {len(abc_sups)}, Trend days: {len(trend)}")
