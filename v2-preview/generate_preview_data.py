#!/usr/bin/env python3
"""Build the static data contract for the Onelife Intelligence v2 preview.

No external calls. Reads local cache/snapshot files only and emits:
- public/data/onelife-intelligence-latest.json
- public/data/onelife-intelligence-data.js (same payload assigned to window.ONELIFE_INTELLIGENCE_DATA for file:// previews)
"""

from __future__ import annotations

import calendar
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
MEMORY = WORKSPACE / "memory"
DATA = ROOT / "data"
OUT_DIR = ROOT / "v2-preview" / "public" / "data"
TZ = ZoneInfo("Africa/Johannesburg")
NOW = datetime.now(TZ)

STORE_MAP = {
    "HO": {"code": "CEN", "name": "Centurion"},
    "CEN": {"code": "CEN", "name": "Centurion"},
    "GVS": {"code": "GVS", "name": "Glen Village"},
    "EDN": {"code": "EDN", "name": "Edenvale"},
    "ONLINE": {"code": "ONLINE", "name": "Online"},
}
STORE_ORDER = ["CEN", "GVS", "EDN"]


def read_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def money(value: Any) -> float:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return 0.0
        return round(float(value), 2)
    except Exception:
        return 0.0


def pct(numerator: float, denominator: float) -> float:
    return round((numerator / denominator * 100), 1) if denominator else 0.0


def safe_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), TZ)
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    for candidate in [text, text.replace("Z", "+00:00")]:
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TZ)
            return dt.astimezone(TZ)
        except Exception:
            pass
    for fmt in ["%Y-%m-%d", "%d %B %Y %H:%M", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=TZ)
        except Exception:
            pass
    return None


def health_status(dt: datetime | None, *, fresh_days: int = 2, warn_days: int = 14) -> tuple[str, int | None]:
    if not dt:
        return "unknown", None
    age_days = max(0, int((NOW - dt).total_seconds() // 86400))
    if age_days <= fresh_days:
        return "fresh", age_days
    if age_days <= warn_days:
        return "watch", age_days
    return "stale", age_days


def source_health_item(source_id: str, label: str, path: Path, date_value: Any, note: str = "", fresh_days: int = 2, warn_days: int = 14) -> dict[str, Any]:
    dt = safe_dt(date_value)
    status, age = health_status(dt, fresh_days=fresh_days, warn_days=warn_days)
    return {
        "id": source_id,
        "label": label,
        "path": str(path.relative_to(WORKSPACE)) if path.exists() else str(path),
        "exists": path.exists(),
        "generated_at": dt.isoformat() if dt else None,
        "age_days": age,
        "status": status,
        "note": note,
    }


def store_code(raw: str | None) -> str:
    return STORE_MAP.get(str(raw or "").upper(), {"code": str(raw or "UNKNOWN").upper(), "name": str(raw or "Unknown")})["code"]


def store_name(code: str) -> str:
    for item in STORE_MAP.values():
        if item["code"] == code:
            return item["name"]
    return code


def row_date(row: dict[str, Any]) -> str | None:
    return row.get("document_date") or row.get("date")


def build_trend_series(omni: dict[str, Any]) -> list[dict[str, Any]]:
    series_specs = [
        ("ALL", "All stores", omni.get("full_history", [])),
        ("CEN", "Centurion", omni.get("ho_history", [])),
        ("GVS", "Glen Village", omni.get("gvs_history", [])),
        ("EDN", "Edenvale", omni.get("edn_history", [])),
    ]
    all_dates = sorted({row_date(r) for _, _, rows in series_specs for r in rows if row_date(r)})
    output = []
    for code, label, rows in series_specs:
        by_date = {row_date(r): r for r in rows if row_date(r)}
        points = []
        for d in all_dates:
            r = by_date.get(d, {})
            revenue = money(r.get("value_excl_after_discount"))
            gp = money(r.get("gross_profit"))
            points.append({"date": d, "revenue": revenue, "gross_profit": gp, "gp_pct": pct(gp, revenue)})
        output.append({"code": code, "label": label, "points": points})
    return output


def build_stores(omni: dict[str, Any], trade: dict[str, Any]) -> list[dict[str, Any]]:
    mtd = omni.get("mtd", {}) or {}
    today = omni.get("today", {}) or {}
    branch_watch = {b.get("store_code"): b for b in (trade.get("sections", {}) or {}).get("branch_watch", [])}
    stores = []
    for raw in ["HO", "GVS", "EDN"]:
        code = store_code(raw)
        m = mtd.get(raw, {}) or {}
        t = today.get(raw if raw != "HO" else "CEN", today.get(raw, {})) or {}
        bw = branch_watch.get(code, {})
        revenue = money(m.get("revenue_excl") or bw.get("mtd_revenue"))
        gp = money(m.get("gross_profit"))
        gp_pct = pct(gp, revenue) if gp else money(t.get("gp_pct") or bw.get("physical_gp_pct_today"))
        target = money(m.get("target"))
        projected = money(m.get("projected_eom") or bw.get("projected_eom"))
        done = int(m.get("trading_days_done") or 0)
        total = int(m.get("trading_days_total") or 0)
        remaining = max(total - done, 0)
        daily_run = revenue / done if done else 0.0
        daily_needed = max(target - revenue, 0.0) / remaining if remaining else 0.0
        gap = projected - target if target else money(bw.get("pace_gap_amount"))
        status = "on-track" if projected >= target else ("watch" if projected >= target * 0.92 else "behind")
        alerts = list(bw.get("active_alerts", []))
        if target and projected < target:
            alerts.insert(0, f"Projected R{abs(gap):,.0f} below target")
        stores.append({
            "code": code,
            "source_code": raw,
            "name": store_name(code),
            "today_revenue": money(t.get("revenue_excl") or bw.get("physical_revenue_today")),
            "today_gp_pct": money(t.get("gp_pct") or bw.get("physical_gp_pct_today")),
            "mtd_revenue": revenue,
            "gross_profit": gp,
            "gp_pct": gp_pct,
            "target": target,
            "target_pct": pct(revenue, target) if target else money(bw.get("mtd_target_pct")),
            "trading_days_done": done,
            "trading_days_total": total,
            "days_remaining": remaining,
            "projected_eom": projected,
            "projected_target_pct": pct(projected, target) if target else 0.0,
            "pace_gap_amount": round(gap, 2),
            "daily_run_rate": round(daily_run, 2),
            "daily_needed": round(daily_needed, 2),
            "status": status,
            "alerts": alerts[:5],
        })
    return stores


def build_margin_leaks(snapshot: dict[str, Any], suppliers: dict[str, str]) -> dict[str, Any]:
    rows = snapshot.get("rows", []) if isinstance(snapshot, dict) else []
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    supplier_totals: dict[str, dict[str, Any]] = defaultdict(lambda: {"revenue": 0.0, "gross_profit": 0.0, "quantity": 0, "sku_count": set(), "name": ""})

    for r in rows:
        revenue = money(r.get("value_excl_after_discount"))
        gp = money(r.get("gross_profit"))
        qty = int(r.get("quantity") or 0)
        if revenue <= 0:
            continue
        raw_branch = str(r.get("company_branch_code") or "").upper()
        code = store_code(raw_branch)
        sku = str(r.get("stock_code") or "UNKNOWN")
        key = (sku, code)
        supplier_code = str(r.get("supplier_#") or "UNKNOWN").strip() or "UNKNOWN"
        item = grouped.setdefault(key, {
            "sku": sku,
            "store_code": code,
            "store": store_name(code),
            "title": str(r.get("line_item_description") or "Unknown product").strip(),
            "supplier_code": supplier_code,
            "supplier": suppliers.get(supplier_code, supplier_code),
            "revenue": 0.0,
            "gross_profit": 0.0,
            "quantity": 0,
        })
        item["revenue"] += revenue
        item["gross_profit"] += gp
        item["quantity"] += qty

        st = supplier_totals[supplier_code]
        st["revenue"] += revenue
        st["gross_profit"] += gp
        st["quantity"] += qty
        st["sku_count"].add(sku)
        st["name"] = suppliers.get(supplier_code, supplier_code)

    items = []
    for item in grouped.values():
        revenue = item["revenue"]
        gp = item["gross_profit"]
        gp_pct = pct(gp, revenue)
        recoverable_35 = max(0.0, revenue * 0.35 - gp)
        recoverable_40 = max(0.0, revenue * 0.40 - gp)
        if revenue < 1000 or recoverable_35 <= 50:
            continue
        item.update({
            "revenue": round(revenue, 2),
            "gross_profit": round(gp, 2),
            "gp_pct": gp_pct,
            "recoverable_to_35": round(recoverable_35, 2),
            "recoverable_to_40": round(recoverable_40, 2),
            "severity": "high" if gp_pct < 25 and recoverable_35 > 1500 else "medium",
        })
        items.append(item)

    items.sort(key=lambda x: (x["recoverable_to_35"], x["revenue"]), reverse=True)

    supplier_rows = []
    total_revenue = sum(v["revenue"] for v in supplier_totals.values())
    for code, v in supplier_totals.items():
        revenue = v["revenue"]
        gp = v["gross_profit"]
        supplier_rows.append({
            "supplier_code": code,
            "supplier": v["name"] or code,
            "revenue": round(revenue, 2),
            "gross_profit": round(gp, 2),
            "gp_pct": pct(gp, revenue),
            "quantity": int(v["quantity"]),
            "sku_count": len(v["sku_count"]),
            "share_pct": pct(revenue, total_revenue),
        })
    supplier_rows.sort(key=lambda x: x["revenue"], reverse=True)
    top5_share = round(sum(r["share_pct"] for r in supplier_rows[:5]), 1)

    return {
        "source_pulled": snapshot.get("pulled") if isinstance(snapshot, dict) else None,
        "items": items[:40],
        "summary": {
            "candidate_count": len(items),
            "total_recoverable_to_35": round(sum(i["recoverable_to_35"] for i in items), 2),
            "stale_warning": "Product margin data is from the February ANA snapshot. Use this for triage, not final decisions.",
        },
        "suppliers": {
            "rows": supplier_rows[:25],
            "concentration": {
                "supplier_count": len(supplier_rows),
                "top5_revenue_share_pct": top5_share,
                "total_revenue": round(total_revenue, 2),
            },
        },
    }


def build_range_stock(trade: dict[str, Any], v7: dict[str, Any]) -> dict[str, Any]:
    sections = trade.get("sections", {}) or {}
    risks = []
    for r in sections.get("winning_items_stock_risk", []) or []:
        cover = money(r.get("stock_cover_days"))
        inv = int(r.get("inventory_quantity") or 0)
        severity = "high" if inv <= 0 or cover <= 15 else ("medium" if cover <= 45 else "watch")
        risks.append({
            "sku": r.get("sku"),
            "title": r.get("title"),
            "category": r.get("category"),
            "revenue_30": money(r.get("revenue_30")),
            "revenue_90": money(r.get("revenue_90")),
            "units_30": int(r.get("units_30") or 0),
            "inventory_quantity": inv,
            "stock_cover_days": cover,
            "reorder_stores": r.get("reorder_stores", []),
            "severity": severity,
            "action": "Replenish or transfer" if severity == "high" else "Watch and confirm branch cover",
        })
    risks.sort(key=lambda x: ({"high": 0, "medium": 1, "watch": 2}.get(x["severity"], 3), -x["revenue_90"]))

    gaps = []
    for g in (v7.get("gaps", []) or [])[:20]:
        miss = g.get("miss") or []
        if not miss:
            continue
        gaps.append({
            "title": g.get("desc"),
            "revenue": money(g.get("rev")),
            "quantity": int(g.get("qty") or 0),
            "gp_pct": money(g.get("gp")),
            "missing_stores": miss,
            "action": "Validate range gap before supplier/order move",
        })

    return {
        "stock_risks": risks,
        "safe_to_push": sections.get("safe_to_push_products", []) or [],
        "content_to_commerce": sections.get("content_to_commerce", []) or [],
        "range_gaps": gaps,
    }


def build_reviews_and_search(review_history: dict[str, Any], trade: dict[str, Any]) -> dict[str, Any]:
    snapshots = review_history.get("snapshots", []) if isinstance(review_history, dict) else []
    latest = snapshots[-1] if snapshots else {"date": None, "stores": {}}
    reviews = []
    for code in STORE_ORDER:
        r = (latest.get("stores", {}) or {}).get(code, {})
        breakdown = r.get("breakdown", {}) or {}
        reviews.append({
            "store_code": code,
            "store": store_name(code),
            "rating": money(r.get("rating")),
            "total_reviews": int(r.get("total_reviews") or 0),
            "five_star": int(breakdown.get("5") or 0),
            "one_two_star": int(breakdown.get("1") or 0) + int(breakdown.get("2") or 0),
        })
    opps = []
    for item in ((trade.get("sections", {}) or {}).get("content_to_commerce", []) or []):
        lane = str(item.get("lane") or "")
        if "seo" in lane or "search" in lane:
            opps.append({
                "lane": lane,
                "theme": item.get("theme"),
                "products_to_push": item.get("products_to_push", []),
                "why_now": item.get("why_now"),
            })
    return {
        "reviews_date": latest.get("date"),
        "reviews": reviews,
        "seo_opportunities": opps,
    }


def build_online(trade: dict[str, Any]) -> dict[str, Any]:
    executive = trade.get("executive", {}) or {}
    customer_geo = (trade.get("sections", {}) or {}).get("customer_geo", {}) or {}
    orders = int(executive.get("shopify_orders") or 0)
    revenue = money(executive.get("shopify_revenue"))
    has_trade = orders > 0 or revenue > 0
    return {
        "status": "available" if has_trade else "limited",
        "metrics": {
            "revenue": revenue,
            "orders": orders,
            "aov": money(executive.get("shopify_aov")),
            "gp_pct": money(executive.get("shopify_gp_pct")),
            "new_orders": int(executive.get("new_orders") or 0),
            "returning_orders": int(executive.get("returning_orders") or 0),
            "repeat_purchase_rate_90d": money(customer_geo.get("repeat_purchase_rate_90d")),
            "due_for_repeat_31_60d": int(customer_geo.get("due_for_repeat_31_60d") or 0),
        },
        "funnel": [
            {"stage": "Sessions", "value": None, "note": "GA4 detail not present in local preview contract"},
            {"stage": "Product views", "value": None, "note": "GA4 detail not present in local preview contract"},
            {"stage": "Add to cart", "value": None, "note": "GA4 detail not present in local preview contract"},
            {"stage": "Orders", "value": orders, "note": "Shopify feed"},
            {"stage": "Revenue", "value": revenue, "note": "Shopify feed"},
        ],
        "top_cities_90d": customer_geo.get("top_cities_90d", [])[:8],
        "warning": "Shopify feed is fresh but currently reports R0 / 0 orders. Channel and device funnel metrics were not available in the local files used for this preview." if not has_trade else "",
    }


def build_actions(stores: list[dict[str, Any]], range_stock: dict[str, Any], margin: dict[str, Any], trade: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    behind = sorted([s for s in stores if s.get("target") and s.get("projected_eom", 0) < s.get("target", 0)], key=lambda s: s.get("pace_gap_amount", 0))
    if behind:
        s = behind[0]
        actions.append({
            "priority": "High",
            "lane": "Store pace",
            "title": f"Recover {s['name']} month-end pace",
            "owner": "Store lead / Naadir",
            "store_code": s["code"],
            "reason": f"Projected EOM is R{abs(s['pace_gap_amount']):,.0f} below target at {s['projected_target_pct']:.1f}% projected target cover.",
            "expected_move": f"Needs roughly R{s['daily_needed']:,.0f}/trading day for the remaining {s['days_remaining']} trading days.",
            "evidence": s.get("alerts", [])[:3],
        })
    if range_stock.get("stock_risks"):
        r = range_stock["stock_risks"][0]
        actions.append({
            "priority": "High" if r["severity"] == "high" else "Medium",
            "lane": "Stock protection",
            "title": f"Protect {r['title']}",
            "owner": "Buying / Store ops",
            "store_code": (r.get("reorder_stores") or ["ALL"])[0],
            "reason": f"R{r['revenue_90']:,.0f} 90d demand with {r['inventory_quantity']} units and {r['stock_cover_days']:.0f} days cover.",
            "expected_move": "Transfer, reorder, or supplier follow-up before demand outruns cover.",
            "evidence": [f"Reorder stores: {', '.join(r.get('reorder_stores') or [])}", f"30d units: {r['units_30']}"],
        })
    if margin.get("items"):
        m = margin["items"][0]
        actions.append({
            "priority": "Medium",
            "lane": "Margin leak",
            "title": f"Validate GP leak on {m['title']}",
            "owner": "Buying / Finance",
            "store_code": m["store_code"],
            "reason": f"{m['gp_pct']:.1f}% GP on R{m['revenue']:,.0f} revenue in stale ANA snapshot.",
            "expected_move": f"If still current, lifting to 35% GP recovers about R{m['recoverable_to_35']:,.0f}.",
            "evidence": [f"Supplier: {m.get('supplier')}", "Validate against current Omni before acting"],
        })
    for item in trade.get("approval_gated_actions", []) or []:
        if len(actions) >= 5:
            break
        actions.append({
            "priority": str(item.get("priority") or "Medium").title(),
            "lane": item.get("lane") or "Approval gated",
            "title": item.get("title"),
            "owner": "Manual approval",
            "store_code": "ALL",
            "reason": item.get("reason"),
            "expected_move": item.get("recommended_decision"),
            "evidence": item.get("evidence", []),
        })
    return actions[:5]


def build_foresight(stores: list[dict[str, Any]], omni: dict[str, Any]) -> dict[str, Any]:
    projections = ((omni.get("mtd", {}) or {}).get("projections", {}) or {})
    total_target = money(projections.get("total_target") or sum(s.get("target", 0) for s in stores))
    base_projection = money(projections.get("TOTAL") or sum(s.get("projected_eom", 0) for s in stores))
    downside = round(sum(s.get("mtd_revenue", 0) + max(s.get("days_remaining", 0), 0) * s.get("daily_run_rate", 0) * 0.9 for s in stores), 2)
    upside = round(sum(s.get("mtd_revenue", 0) + max(s.get("days_remaining", 0), 0) * max(s.get("daily_needed", 0), s.get("daily_run_rate", 0) * 1.08) for s in stores), 2)
    return {
        "target": total_target,
        "base_projection": base_projection,
        "base_gap": round(base_projection - total_target, 2),
        "target_cover_pct": pct(base_projection, total_target),
        "scenarios": [
            {"name": "Soft landing", "value": downside, "gap": round(downside - total_target, 2), "note": "Run-rate fades 10% from current pace."},
            {"name": "Current pace", "value": base_projection, "gap": round(base_projection - total_target, 2), "note": "Omni projection using current MTD pace."},
            {"name": "Recovery push", "value": upside, "gap": round(upside - total_target, 2), "note": "Stores hit needed run-rate or 8% above current pace where needed."},
        ],
        "limitations": [
            "Forecast is physical-store-led. Online orders are showing zero in the current Shopify feed.",
            "Centurion/Glen Village use 19 trading days in Omni while Edenvale uses 23, so total pace is directional rather than accounting-grade.",
        ],
    }


def main() -> None:
    omni_path = MEMORY / "omni_cache.json"
    daily_path = MEMORY / "daily-sales-cache.json"
    ana_path = MEMORY / "snapshots" / "2026-02" / "ana_popular_gp.json"
    suppliers_path = DATA / "suppliers_master.json"
    trade_path = DATA / "trade_brief_latest.json"
    reviews_path = DATA / "google_reviews" / "review_history.json"
    v7_path = ROOT / "v7_data.json"

    omni = read_json(omni_path, {})
    daily = read_json(daily_path, {})
    ana = read_json(ana_path, {})
    suppliers = read_json(suppliers_path, {})
    trade = read_json(trade_path, {})
    reviews = read_json(reviews_path, {})
    v7 = read_json(v7_path, {})

    stores = build_stores(omni, trade)
    trends = build_trend_series(omni)
    margin = build_margin_leaks(ana, suppliers if isinstance(suppliers, dict) else {})
    range_stock = build_range_stock(trade, v7)
    search_reviews = build_reviews_and_search(reviews, trade)
    online = build_online(trade)
    actions = build_actions(stores, range_stock, margin, trade)
    foresight = build_foresight(stores, omni)

    mtd = omni.get("mtd", {}) or {}
    combined = mtd.get("combined", {}) or {}
    today_combined = (omni.get("today", {}) or {}).get("combined", {}) or {}
    projections = mtd.get("projections", {}) or {}

    payload = {
        "schema_version": "onelife-intelligence-preview/v2.0",
        "generated_at": NOW.isoformat(timespec="seconds"),
        "as_of": (omni.get("today", {}) or {}).get("date") or trade.get("run_date"),
        "date_range": mtd.get("date_range"),
        "source_health": [
            source_health_item("omni", "Omni dashboard cache", omni_path, omni.get("last_updated"), omni.get("fetch_status", ""), fresh_days=1, warn_days=3),
            source_health_item("trade_brief", "Trade brief", trade_path, trade.get("generated_at"), "Commerce/action brief used for stock, online and content cards.", fresh_days=2, warn_days=7),
            source_health_item("ana_gp", "ANA popular GP snapshot", ana_path, ana.get("pulled"), "Used only for margin leak triage; stale by design until refreshed.", fresh_days=7, warn_days=30),
            source_health_item("daily_sales", "Daily sales cache", daily_path, daily.get("last_updated"), "Legacy history cache retained for warning only; Omni cache drives the preview.", fresh_days=2, warn_days=14),
            source_health_item("reviews", "Google review history", reviews_path, (reviews.get("snapshots", [{}]) or [{}])[-1].get("date"), "Only one snapshot available, so review trend is not yet chartable.", fresh_days=7, warn_days=21),
        ],
        "executive": {
            "mtd_revenue": money(combined.get("revenue_excl")),
            "mtd_gross_profit": money(combined.get("gross_profit")),
            "mtd_gp_pct": money(combined.get("gp_pct")) or pct(money(combined.get("gross_profit")), money(combined.get("revenue_excl"))),
            "today_revenue": money(today_combined.get("revenue_excl")),
            "today_gross_profit": money(today_combined.get("gross_profit")),
            "today_gp_pct": money(today_combined.get("gp_pct")),
            "target": money(projections.get("total_target")),
            "projected_eom": money(projections.get("TOTAL")),
            "target_pct_current": pct(money(combined.get("revenue_excl")), money(projections.get("total_target"))),
            "target_pct_projected": money(projections.get("total_target_pct")) or pct(money(projections.get("TOTAL")), money(projections.get("total_target"))),
            "projected_gap": round(money(projections.get("TOTAL")) - money(projections.get("total_target")), 2),
        },
        "stores": stores,
        "trends": trends,
        "actions": actions,
        "margin_leaks": {"summary": margin["summary"], "items": margin["items"]},
        "range_stock": range_stock,
        "supplier": margin["suppliers"],
        "online_funnel": online,
        "search_reviews": search_reviews,
        "foresight": foresight,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "onelife-intelligence-latest.json"
    js_path = OUT_DIR / "onelife-intelligence-data.js"
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    json_path.write_text(json_text + "\n", encoding="utf-8")
    js_path.write_text("window.ONELIFE_INTELLIGENCE_DATA = " + json_text + ";\n", encoding="utf-8")
    print(f"Wrote {json_path.relative_to(ROOT)}")
    print(f"Wrote {js_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
