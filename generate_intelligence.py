#!/usr/bin/env python3
"""
Onelife Intelligence Dashboard Generator
Pulls live Omni data and generates a rich HTML dashboard.
"""

import json, urllib.request, urllib.parse, urllib.error
from collections import defaultdict
from datetime import datetime, date, timezone, timedelta
import os, subprocess

SAST_OFFSET = timezone(timedelta(hours=2))
def SAST(): return datetime.now(SAST_OFFSET)
BASE = "http://102.22.82.27:59029"
AUTH = "UserName=analytic&Password=An%40lyt1c&CompanyName=Onelife"
OUT = "/Users/naadir/.openclaw/workspace/onelife-intelligence/index.html"

BRANCHES = {"HO": "Daily Turnover One Life", "GVS": "Daily Turnover GVS", "EDN": "Daily Turnover EDEN"}
BRANCH_LABELS = {"HO": "Centurion", "GVS": "Glen Village", "EDN": "Edenvale"}
TARGETS = {"HO": 1450000, "GVS": 330000, "EDN": 450000}
TRADING_DAYS = {"HO": 26, "GVS": 31, "EDN": 31}
BAKERY_SUPPLIER = "LOVE"

# Supplier code -> name lookup (from Naadir's Suppliers.xlsx — authoritative source)
def _load_suppliers():
    """Load supplier names from the xlsx file, fall back to cached JSON."""
    try:
        import openpyxl
        for p in [
            os.path.expanduser("~/.openclaw/media/inbound/Suppliers---52e19b0a-554e-438c-a34d-6544ac78687f.xlsx"),
            os.path.expanduser("~/.openclaw/workspace/memory/suppliers.xlsx"),
        ]:
            if os.path.exists(p):
                wb = openpyxl.load_workbook(p, read_only=True)
                ws = wb["Suppliers"]
                d = {}
                for row in ws.iter_rows(min_row=2, values_only=True):
                    code, name = row[0], row[1]
                    if code and name and "Category" not in str(name):
                        d[str(code).strip()] = str(name).strip()
                wb.close()
                return d
    except Exception:
        pass
    # Fallback: cached JSON
    try:
        with open(os.path.expanduser("~/.openclaw/workspace/memory/supplier_names.json")) as f:
            return json.load(f)
    except Exception:
        return {}

SUPPLIER_NAMES = _load_suppliers()

def sup_name(code):
    return SUPPLIER_NAMES.get(code, code)

def omni(path, timeout=120):
    url = f"{BASE}{path}?{AUTH}"
    try:
        r = urllib.request.urlopen(url, timeout=timeout)
        return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def fmt_r(n):
    if n >= 1000000: return f"R{n/1000000:.1f}M"
    if n >= 1000: return f"R{n/1000:.0f}k"
    return f"R{n:.0f}"

def fmt_pct(n): return f"{n:.1f}%"

def pace_color(pct):
    if pct >= 85: return "#22c55e"
    if pct >= 65: return "#f59e0b"
    return "#ef4444"

def gp_color(pct):
    if pct >= 35: return "#22c55e"
    if pct >= 28: return "#f59e0b"
    return "#ef4444"

def main():
    now = SAST()
    today_str = now.strftime("%Y-%m-%d")
    month_prefix = now.strftime("%Y-%m")
    trading_day_num = now.day  # approximate

    # --- Fetch data ---
    print("Fetching daily turnover...")
    daily_data = {}
    for branch, rpt in BRANCHES.items():
        data = omni(f"/Report/{urllib.parse.quote(rpt)}")
        key = next((k for k, v in data.items() if isinstance(v, list)), None)
        records = data[key] if key else []
        daily_data[branch] = [r for r in records if str(r.get("document_date","")).startswith(month_prefix)]

    print("Fetching product GP...")
    gp_data = omni(f"/Report/{urllib.parse.quote('ANA_Most Popular Products GP')}")
    gp_key = next((k for k, v in gp_data.items() if isinstance(v, list)), None)
    all_products = gp_data[gp_key] if gp_key else []

    # --- Process per branch ---
    branch_stats = {}
    for branch in ["HO", "GVS", "EDN"]:
        label = BRANCH_LABELS[branch]
        target = TARGETS[branch]
        trade_days = TRADING_DAYS[branch]
        records = daily_data.get(branch, [])

        mtd_rev = sum(r.get("value_excl_after_discount", 0) for r in records)
        mtd_gp = sum(r.get("gross_profit", 0) for r in records)
        mtd_gp_pct = (mtd_gp / mtd_rev * 100) if mtd_rev else 0
        days_traded = len(records)

        today_rec = next((r for r in records if today_str in str(r.get("document_date",""))), None)
        today_rev = today_rec["value_excl_after_discount"] if today_rec else 0
        today_gp = today_rec["gross_profit"] if today_rec else 0

        # Run rate
        avg_daily = mtd_rev / days_traded if days_traded else 0
        projected = avg_daily * trade_days
        pace_pct = (projected / target * 100) if target else 0
        gap_daily = ((target - projected) / (trade_days - days_traded)) if (trade_days - days_traded) > 0 else 0

        # Products for this branch
        branch_prods = [p for p in all_products if p.get("company_branch_code") == branch]

        # Top sellers by revenue
        top_sellers = sorted(branch_prods, key=lambda x: x.get("value_excl_after_discount", 0), reverse=True)[:15]

        # Low GP items (excl bakery, rev > R2000 annual so meaningful)
        low_gp = []
        for p in branch_prods:
            rev = p.get("value_excl_after_discount", 0)
            gp_val = p.get("gross_profit", 0)
            sup = p.get("supplier_#", "")
            if rev > 2000 and sup != BAKERY_SUPPLIER:
                gp_pct = (gp_val / rev * 100) if rev else 0
                if gp_pct < 25:
                    low_gp.append({**p, "gp_pct": gp_pct})
        low_gp = sorted(low_gp, key=lambda x: x["gp_pct"])[:15]

        # Non-movers (qty = 0 or 1 but we have them listed)
        non_movers = [p for p in branch_prods if p.get("quantity", 0) <= 1 and p.get("value_excl_after_discount", 0) < 500]
        non_movers = sorted(non_movers, key=lambda x: x.get("value_excl_after_discount", 0))[:15]

        # Daily trend for sparkline
        trend = [(r.get("document_date","")[-2:], r.get("value_excl_after_discount", 0)) for r in sorted(records, key=lambda x: x.get("document_date",""))]

        branch_stats[branch] = {
            "label": label, "target": target, "trade_days": trade_days,
            "mtd_rev": mtd_rev, "mtd_gp": mtd_gp, "mtd_gp_pct": mtd_gp_pct,
            "days_traded": days_traded, "today_rev": today_rev, "today_gp": today_gp,
            "avg_daily": avg_daily, "projected": projected, "pace_pct": pace_pct,
            "gap_daily": gap_daily, "top_sellers": top_sellers, "low_gp": low_gp,
            "non_movers": non_movers, "trend": trend,
        }

    # --- Supplier summary ---
    sup_totals = defaultdict(lambda: {"rev": 0, "gp": 0, "qty": 0})
    for p in all_products:
        if p.get("company_branch_code") == "HO":
            s = p.get("supplier_#", "UNKNOWN")
            sup_totals[s]["rev"] += p.get("value_excl_after_discount", 0)
            sup_totals[s]["gp"] += p.get("gross_profit", 0)
            sup_totals[s]["qty"] += p.get("quantity", 0)
    top_suppliers = sorted(sup_totals.items(), key=lambda x: x[1]["rev"], reverse=True)[:20]

    # --- Build HTML ---
    def trend_bars(trend_data):
        if not trend_data: return ""
        max_val = max(v for _, v in trend_data) or 1
        bars = ""
        for day, val in trend_data:
            h = max(4, int((val / max_val) * 48))
            bars += f'<div title="Day {day}: {fmt_r(val)}" style="width:10px;height:{h}px;background:#22c55e;border-radius:2px;display:inline-block;vertical-align:bottom;margin:0 1px"></div>'
        return bars

    def product_rows(products, show_gp_pct=True):
        rows = ""
        for p in products:
            desc = p.get("line_item_description","?")[:50]
            rev = p.get("value_excl_after_discount", 0)
            gp_val = p.get("gross_profit", 0)
            qty = p.get("quantity", 0)
            sup = p.get("supplier_#", "?")
            gp_pct = (gp_val / rev * 100) if rev else 0
            gp_col = gp_color(gp_pct)
            rows += f"""<tr>
                <td style="padding:8px 12px;border-bottom:1px solid #2d2d3d;font-size:13px;max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{desc}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #2d2d3d;font-size:13px;color:#94a3b8;font-size:12px">{sup_name(sup)} ({sup})</td>
                <td style="padding:8px 12px;border-bottom:1px solid #2d2d3d;font-size:13px;text-align:right">{fmt_r(rev)}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #2d2d3d;font-size:13px;text-align:right;color:{gp_col}">{fmt_pct(gp_pct)}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #2d2d3d;font-size:13px;text-align:right;color:#94a3b8">{int(qty):,}</td>
            </tr>"""
        return rows

    def top_seller_rows(sellers):
        rows = ""
        for p in sellers[:10]:
            desc = p.get("line_item_description", "?")
            rev = p.get("value_excl_after_discount", 0)
            gp_v = p.get("gross_profit", 0)
            gp_p = (gp_v / rev * 100) if rev else 0
            col = gp_color(gp_p)
            rows += f"<tr><td style='padding:5px 8px;border-bottom:1px solid #2d2d3d;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:150px'>{desc[:30]}</td><td style='padding:5px 8px;border-bottom:1px solid #2d2d3d;font-size:12px;text-align:right'>{fmt_r(rev)}</td><td style='padding:5px 8px;border-bottom:1px solid #2d2d3d;font-size:12px;text-align:right;color:{col}'>{fmt_pct(gp_p)}</td></tr>"
        return rows

    def low_gp_rows(items):
        rows = ""
        for p in items[:10]:
            desc = p.get("line_item_description", "?")
            gp_p = p.get("gp_pct", 0)
            sup = p.get("supplier_#", "?")
            rows += f"<tr><td style='padding:5px 8px;border-bottom:1px solid #2d2d3d;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:140px'>{desc[:28]}</td><td style='padding:5px 8px;border-bottom:1px solid #2d2d3d;font-size:12px;text-align:right;color:#ef4444'>{fmt_pct(gp_p)}</td><td style='padding:5px 8px;border-bottom:1px solid #2d2d3d;font-size:11px;text-align:right;color:#94a3b8'>{sup}</td></tr>"
        return rows

    def non_mover_rows(items):
        rows = ""
        for p in items[:10]:
            desc = p.get("line_item_description", "?")
            sup = p.get("supplier_#", "?")
            rows += f"<tr><td style='padding:5px 8px;border-bottom:1px solid #2d2d3d;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px'>{desc[:32]}</td><td style='padding:5px 8px;border-bottom:1px solid #2d2d3d;font-size:11px;text-align:right;color:#94a3b8'>{sup}</td></tr>"
        return rows

    def branch_card(b):
        s = branch_stats[b]
        pc = s["pace_pct"]
        gpc = s["mtd_gp_pct"]
        status = "On Track" if pc >= 85 else "Lagging" if pc >= 65 else "Behind"
        status_col = pace_color(pc)
        remaining_days = s["trade_days"] - s["days_traded"]
        need_msg = f"Need {fmt_r(s['gap_daily'])}/day to hit target" if s["gap_daily"] > 0 else "Projecting to hit target"
        ts_rows = top_seller_rows(s["top_sellers"])
        lg_rows = low_gp_rows(s["low_gp"])
        nm_rows = non_mover_rows(s["non_movers"])

        return f"""
        <div style="background:#1a1a2e;border:1px solid #2d2d3d;border-radius:12px;padding:24px;margin-bottom:20px">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px">
                <div>
                    <h2 style="margin:0;font-size:22px;color:#f1f5f9">{s["label"]}</h2>
                    <span style="font-size:12px;color:{status_col};font-weight:600;letter-spacing:1px">{status}</span>
                </div>
                <div style="text-align:right">
                    <div style="font-size:11px;color:#64748b;margin-bottom:2px">TARGET</div>
                    <div style="font-size:18px;font-weight:700;color:#64748b">{fmt_r(s["target"])}</div>
                </div>
            </div>

            <!-- KPI Grid -->
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px">
                <div style="background:#0f0f1a;border-radius:8px;padding:14px;text-align:center">
                    <div style="font-size:11px;color:#64748b;margin-bottom:4px;letter-spacing:1px">TODAY REV</div>
                    <div style="font-size:22px;font-weight:700;color:#f1f5f9">{fmt_r(s["today_rev"])}</div>
                    <div style="font-size:11px;color:#22c55e">GP {fmt_r(s["today_gp"])}</div>
                </div>
                <div style="background:#0f0f1a;border-radius:8px;padding:14px;text-align:center">
                    <div style="font-size:11px;color:#64748b;margin-bottom:4px;letter-spacing:1px">MTD REV</div>
                    <div style="font-size:22px;font-weight:700;color:#f1f5f9">{fmt_r(s["mtd_rev"])}</div>
                    <div style="font-size:11px;color:#22c55e">GP {fmt_r(s["mtd_gp"])}</div>
                </div>
                <div style="background:#0f0f1a;border-radius:8px;padding:14px;text-align:center">
                    <div style="font-size:11px;color:#64748b;margin-bottom:4px;letter-spacing:1px">GP%</div>
                    <div style="font-size:22px;font-weight:700;color:{gp_color(gpc)}">{fmt_pct(gpc)}</div>
                    <div style="font-size:11px;color:#64748b">{s["days_traded"]} trading days</div>
                </div>
                <div style="background:#0f0f1a;border-radius:8px;padding:14px;text-align:center">
                    <div style="font-size:11px;color:#64748b;margin-bottom:4px;letter-spacing:1px">PROJECTED</div>
                    <div style="font-size:22px;font-weight:700;color:{status_col}">{fmt_r(s["projected"])}</div>
                    <div style="font-size:11px;color:#64748b">{fmt_pct(pc)} of target</div>
                </div>
            </div>

            <!-- Progress bar -->
            <div style="margin-bottom:8px">
                <div style="display:flex;justify-content:space-between;font-size:11px;color:#64748b;margin-bottom:4px">
                    <span>MTD Progress: {fmt_pct(s["mtd_rev"]/s["target"]*100 if s["target"] else 0)}</span>
                    <span>{need_msg}</span>
                </div>
                <div style="background:#2d2d3d;border-radius:4px;height:8px;overflow:hidden">
                    <div style="background:{status_col};height:100%;width:{min(100, s['mtd_rev']/s['target']*100 if s['target'] else 0):.1f}%;border-radius:4px;transition:width 0.3s"></div>
                </div>
            </div>

            <!-- Daily trend sparkline -->
            <div style="margin-bottom:20px;padding:12px;background:#0f0f1a;border-radius:8px">
                <div style="font-size:11px;color:#64748b;margin-bottom:8px;letter-spacing:1px">DAILY TREND (MTD)</div>
                <div style="display:flex;align-items:flex-end;height:52px;gap:1px">
                    {trend_bars(s["trend"])}
                </div>
            </div>

            <!-- Tables in 3 columns -->
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px">
                <!-- Top Sellers -->
                <div>
                    <div style="font-size:12px;color:#94a3b8;font-weight:600;letter-spacing:1px;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #2d2d3d">TOP SELLERS (ANNUAL)</div>
                    <table style="width:100%;border-collapse:collapse">
                        <tr><th style="font-size:11px;color:#64748b;text-align:left;padding:4px 8px">Product</th><th style="font-size:11px;color:#64748b;text-align:right;padding:4px 8px">Rev</th><th style="font-size:11px;color:#64748b;text-align:right;padding:4px 8px">GP%</th></tr>
                        {ts_rows}
                    </table>
                </div>
                <!-- Low GP Items -->
                <div>
                    <div style="font-size:12px;color:#ef4444;font-weight:600;letter-spacing:1px;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #2d2d3d">LOW GP ITEMS (EXCL BAKERY)</div>
                    <table style="width:100%;border-collapse:collapse">
                        <tr><th style="font-size:11px;color:#64748b;text-align:left;padding:4px 8px">Product</th><th style="font-size:11px;color:#64748b;text-align:right;padding:4px 8px">GP%</th><th style="font-size:11px;color:#64748b;text-align:right;padding:4px 8px">Supplier</th></tr>
                        {lg_rows}
                    </table>
                </div>
                <!-- Non-Movers -->
                <div>
                    <div style="font-size:12px;color:#f59e0b;font-weight:600;letter-spacing:1px;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #2d2d3d">NON-MOVERS (≤1 UNIT)</div>
                    <table style="width:100%;border-collapse:collapse">
                        <tr><th style="font-size:11px;color:#64748b;text-align:left;padding:4px 8px">Product</th><th style="font-size:11px;color:#64748b;text-align:right;padding:4px 8px">Supplier</th></tr>
                        {nm_rows}
                    </table>
                </div>
            </div>
        </div>"""

    # Supplier table
    sup_rows = ""
    for code, t in top_suppliers:
        gp_pct = (t["gp"] / t["rev"] * 100) if t["rev"] else 0
        sup_rows += f"""<tr>
            <td style="padding:8px 16px;border-bottom:1px solid #2d2d3d;font-size:13px">{sup_name(code)}</td>
            <td style="padding:8px 16px;border-bottom:1px solid #2d2d3d;font-size:12px;color:#64748b">{code}</td>
            <td style="padding:8px 16px;border-bottom:1px solid #2d2d3d;font-size:13px;text-align:right">{fmt_r(t["rev"])}</td>
            <td style="padding:8px 16px;border-bottom:1px solid #2d2d3d;font-size:13px;text-align:right;color:{gp_color(gp_pct)}">{fmt_pct(gp_pct)}</td>
            <td style="padding:8px 16px;border-bottom:1px solid #2d2d3d;font-size:13px;text-align:right;color:#94a3b8">{int(t["qty"]):,}</td>
        </tr>"""

    total_mtd = sum(branch_stats[b]["mtd_rev"] for b in branch_stats)
    total_gp = sum(branch_stats[b]["mtd_gp"] for b in branch_stats)
    total_gp_pct = (total_gp / total_mtd * 100) if total_mtd else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="1800">
<title>Onelife Intelligence | {now.strftime('%d %b %Y')}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0a14;color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:20px}}
table{{border-collapse:collapse;width:100%}}
.badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600}}
@media(max-width:768px){{.grid-3{{grid-template-columns:1fr!important}}}}
</style>
</head>
<body>

<!-- Header -->
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;padding-bottom:20px;border-bottom:1px solid #2d2d3d">
    <div>
        <h1 style="font-size:28px;font-weight:800;color:#f1f5f9;letter-spacing:-0.5px">Onelife Intelligence</h1>
        <div style="font-size:13px;color:#64748b;margin-top:4px">Real-time store performance · All figures excl VAT · Updated {now.strftime('%d %b %Y %H:%M SAST')}</div>
    </div>
    <div style="text-align:right">
        <div style="font-size:11px;color:#64748b;margin-bottom:2px">COMBINED MTD</div>
        <div style="font-size:32px;font-weight:800;color:#22c55e">{fmt_r(total_mtd)}</div>
        <div style="font-size:13px;color:#64748b">GP {fmt_r(total_gp)} ({fmt_pct(total_gp_pct)})</div>
    </div>
</div>

<!-- Store Dashboards -->
{branch_card("HO")}
{branch_card("GVS")}
{branch_card("EDN")}

<!-- Top Suppliers (Centurion annual) -->
<div style="background:#1a1a2e;border:1px solid #2d2d3d;border-radius:12px;padding:24px;margin-bottom:20px">
    <h3 style="font-size:16px;font-weight:700;margin-bottom:16px;color:#f1f5f9">Top Suppliers by Revenue — Centurion (Annual)</h3>
    <table>
        <thead><tr>
            <th style="font-size:11px;color:#64748b;text-align:left;padding:8px 16px;letter-spacing:1px">SUPPLIER</th>
            <th style="font-size:11px;color:#64748b;text-align:left;padding:8px 16px;letter-spacing:1px">CODE</th>
            <th style="font-size:11px;color:#64748b;text-align:right;padding:8px 16px;letter-spacing:1px">ANNUAL REV</th>
            <th style="font-size:11px;color:#64748b;text-align:right;padding:8px 16px;letter-spacing:1px">GP%</th>
            <th style="font-size:11px;color:#64748b;text-align:right;padding:8px 16px;letter-spacing:1px">UNITS SOLD</th>
        </tr></thead>
        <tbody>{sup_rows}</tbody>
    </table>
</div>

<!-- Footer -->
<div style="text-align:center;padding:20px;font-size:12px;color:#64748b">
    Onelife Intelligence · {now.strftime('%d %B %Y')} · 3 stores + online · Auto-refreshes every 30 min
</div>

</body>
</html>"""

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(html)
    print(f"Dashboard written: {len(html):,} chars → {OUT}")

if __name__ == "__main__":
    main()
