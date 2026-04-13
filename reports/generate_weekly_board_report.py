#!/usr/bin/env python3
"""
Onelife Intelligence — Weekly Board Report Generator
Builds a premium PDF board report from the freshest local Onelife intelligence files.
"""
import glob
import json
import os
from datetime import datetime, timedelta, timezone

from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SAST = timezone(timedelta(hours=2))
WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
OUT_DIR = os.path.join(WORKSPACE, "onelife-intelligence/reports")
LOGO_PATH = os.path.join(WORKSPACE, "skills/onelife-social/onelife-logo-official.png")
OMNI_PATH = os.path.join(WORKSPACE, "memory/omni_cache.json")
TRADE_BRIEF_PATH = os.path.join(WORKSPACE, "onelife-intelligence/data/trade_brief_latest.json")
RAW_DIR = os.path.join(WORKSPACE, "vaults/onelife/raw")
LEGACY_V7_PATH = os.path.join(WORKSPACE, "onelife-intelligence/v7_data.json")

C_PRIMARY = HexColor("#1B4332")
C_ACCENT = HexColor("#2D6A4F")
C_LIGHT = HexColor("#D8F3DC")
C_TEXT = HexColor("#1B1B1B")
C_MUTED = HexColor("#6B7280")
C_GREEN = HexColor("#16A34A")
C_AMBER = HexColor("#F59E0B")
C_RED = HexColor("#DC2626")
C_WHITE = white
C_LIGHTGRAY = HexColor("#F3F4F6")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm

TARGETS = {"CEN": 1_450_000, "GVS": 330_000, "EDN": 450_000}
STORE_LABELS = {"CEN": "Centurion", "GVS": "Glen Village", "EDN": "Edenvale"}
RAW_PATTERNS = {
    "branch": "branch-intelligence-*.json",
    "inventory": "inventory-health-*.json",
    "supplier": "supplier-scorecard-*.json",
    "trade": "daily-trade-brief-*.json",
}


def load_json(path, default=None):
    if not path or not os.path.exists(path):
        return {} if default is None else default
    with open(path) as f:
        return json.load(f)


def latest_file(pattern):
    matches = sorted(glob.glob(os.path.join(RAW_DIR, pattern)))
    return matches[-1] if matches else None


def parse_date(value):
    if not value:
        return None
    text = str(value)[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except Exception:
        return None


def format_date(dt):
    if not dt:
        return "Unknown"
    return f"{dt.day} {dt.strftime('%B %Y')}"


def short_date(dt):
    if not dt:
        return "Unknown"
    return f"{dt.day} {dt.strftime('%b')}"


def shorten(text, limit=52):
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def fmt_r(val):
    val = float(val or 0)
    if abs(val) >= 1_000_000:
        return f"R{val/1_000_000:,.1f}M"
    if abs(val) >= 1_000:
        return f"R{val:,.0f}"
    return f"R{val:,.2f}"


def pace_colour(pct):
    if pct >= 90:
        return C_GREEN
    if pct >= 70:
        return C_AMBER
    return C_RED


def pace_colour_hex(pct):
    if pct >= 90:
        return "#16A34A"
    if pct >= 70:
        return "#F59E0B"
    return "#DC2626"


def pace_label(pct):
    if pct >= 90:
        return "On Track"
    if pct >= 70:
        return "Watch"
    return "Behind"


def gp_pct(gp, revenue):
    revenue = float(revenue or 0)
    return (float(gp or 0) / revenue * 100) if revenue else 0.0


def build_styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("Title1", parent=ss["Title"], fontSize=22, textColor=C_PRIMARY,
                          spaceAfter=2 * mm, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("Subtitle", parent=ss["Normal"], fontSize=11, textColor=C_MUTED,
                          spaceAfter=6 * mm))
    ss.add(ParagraphStyle("SectionHead", parent=ss["Heading2"], fontSize=14, textColor=C_ACCENT,
                          spaceBefore=5 * mm, spaceAfter=3 * mm, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=9, textColor=C_TEXT, leading=13))
    ss.add(ParagraphStyle("BodySmall", parent=ss["Normal"], fontSize=8, textColor=C_MUTED, leading=11))
    ss.add(ParagraphStyle("KPIValue", parent=ss["Normal"], fontSize=18, textColor=C_PRIMARY,
                          fontName="Helvetica-Bold", alignment=TA_CENTER))
    ss.add(ParagraphStyle("KPILabel", parent=ss["Normal"], fontSize=8, textColor=C_MUTED,
                          alignment=TA_CENTER))
    ss.add(ParagraphStyle("TableHead", parent=ss["Normal"], fontSize=9, textColor=C_WHITE,
                          fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("TableCell", parent=ss["Normal"], fontSize=8.5, textColor=C_TEXT, leading=11))
    ss.add(ParagraphStyle("TableCellR", parent=ss["Normal"], fontSize=8.5, textColor=C_TEXT,
                          alignment=TA_RIGHT, leading=11))
    ss.add(ParagraphStyle("InsightBullet", parent=ss["Normal"], fontSize=9, textColor=C_TEXT,
                          leading=13, leftIndent=8 * mm, bulletIndent=2 * mm))
    return ss


def make_kpi_card(label, value, ss):
    table = Table(
        [[Paragraph(str(value), ss["KPIValue"])], [Paragraph(label, ss["KPILabel"]) ]],
        colWidths=[38 * mm],
        rowHeights=[10 * mm, 6 * mm],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_LIGHT),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, C_ACCENT),
        ("TOPPADDING", (0, 0), (-1, 0), 3 * mm),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 2 * mm),
    ]))
    return table


def build_report_data():
    omni = load_json(OMNI_PATH)
    trade_brief = load_json(TRADE_BRIEF_PATH) or load_json(latest_file(RAW_PATTERNS["trade"]))
    branch = load_json(latest_file(RAW_PATTERNS["branch"]))
    inventory = load_json(latest_file(RAW_PATTERNS["inventory"]))
    supplier = load_json(latest_file(RAW_PATTERNS["supplier"]))
    legacy = load_json(LEGACY_V7_PATH)

    if not omni:
        raise RuntimeError("Missing memory/omni_cache.json, cannot build weekly report.")

    branch_summary = branch.get("summary", {})
    branch_watch = {item.get("store_code"): item for item in trade_brief.get("sections", {}).get("branch_watch", [])}

    histories = {
        "CEN": omni.get("ho_history", []),
        "GVS": omni.get("gvs_history", []),
        "EDN": omni.get("edn_history", []),
    }

    mtd = omni.get("mtd", {})
    combined = mtd.get("combined", {})
    projections = mtd.get("projections", {})
    full_history = omni.get("full_history", [])

    latest_trade_date = parse_date(branch.get("source_dates", {}).get("today"))
    if not latest_trade_date:
        latest_trade_date = parse_date(omni.get("today", {}).get("date"))
    if not latest_trade_date and full_history:
        latest_trade_date = max(parse_date(row.get("document_date")) for row in full_history if row.get("document_date"))

    week_end = latest_trade_date
    week_start = week_end - timedelta(days=6) if week_end else None

    branch_rows = []
    for code in ["CEN", "GVS", "EDN"]:
        summary = branch_summary.get(code, {})
        history = histories.get(code, [])
        latest_entry = max(history, key=lambda r: r.get("document_date", "")) if history else {}
        latest_store_date = parse_date(latest_entry.get("document_date"))
        latest_revenue = float(latest_entry.get("value_excl_after_discount", 0) or 0)
        latest_gp_value = float(latest_entry.get("gross_profit", 0) or 0)

        if code == "CEN":
            mtd_store = mtd.get("HO", {})
        else:
            mtd_store = mtd.get(code, {})

        mtd_revenue = float(summary.get("mtd_revenue", mtd_store.get("revenue_excl", 0)) or 0)
        mtd_gp_value = float(summary.get("mtd_gp", mtd_store.get("gross_profit", 0)) or 0)
        target = float(summary.get("mtd_target", mtd_store.get("target", TARGETS[code])) or TARGETS[code])
        projected = float(summary.get("projected_eom", mtd_store.get("projected_eom", 0)) or 0)
        trading_days_done = int(summary.get("trading_days_done", len(history)) or len(history) or 0)
        trading_days_total = int(summary.get("trading_days_total", 0) or 0)
        mom_trend = summary.get("mom_trend_revenue")
        active_alerts = branch_watch.get(code, {}).get("active_alerts", [])

        branch_rows.append({
            "code": code,
            "name": STORE_LABELS[code],
            "mtd_revenue": mtd_revenue,
            "mtd_gp_value": mtd_gp_value,
            "gp_pct": gp_pct(mtd_gp_value, mtd_revenue),
            "target": target,
            "projected_eom": projected,
            "projected_pct": (projected / target * 100) if target else 0,
            "latest_trade_date": latest_store_date,
            "latest_revenue": latest_revenue,
            "latest_gp_pct": gp_pct(latest_gp_value, latest_revenue),
            "trading_days_done": trading_days_done,
            "trading_days_total": trading_days_total,
            "mom_trend_revenue": mom_trend,
            "active_alerts": active_alerts,
        })

    trend_map = {}
    for code, history in histories.items():
        for row in history:
            doc_date = parse_date(row.get("document_date"))
            if not doc_date:
                continue
            trend_map.setdefault(doc_date, {"cen": 0, "gvs": 0, "edn": 0})
            key = "cen" if code == "CEN" else code.lower()
            trend_map[doc_date][key] = round(float(row.get("value_excl_after_discount", 0) or 0), 0)

    trend_dates = sorted(trend_map.keys())[-30:]
    trend = []
    for dt in trend_dates:
        row = trend_map[dt]
        trend.append({
            "date": short_date(dt),
            "raw_date": dt,
            "cen": row.get("cen", 0),
            "gvs": row.get("gvs", 0),
            "edn": row.get("edn", 0),
            "total": row.get("cen", 0) + row.get("gvs", 0) + row.get("edn", 0),
        })

    stock_risk = list(trade_brief.get("sections", {}).get("winning_items_stock_risk", []) or [])
    safe_to_push = list(trade_brief.get("sections", {}).get("safe_to_push_products", []) or [])

    product_priorities = []
    for item in stock_risk[:4]:
        pressure_stores = item.get("stockout_stores", []) + item.get("reorder_stores", [])
        pressure_text = ", ".join(pressure_stores) if pressure_stores else "Monitor"
        cover_days = item.get("stock_cover_days")
        cover_text = f"Cover {cover_days:.0f}d" if isinstance(cover_days, (int, float)) else "Cover unknown"
        product_priorities.append({
            "type": "Protect",
            "type_hex": "#DC2626",
            "title": item.get("title", "Unknown item"),
            "revenue": float(item.get("revenue_90", 0) or 0),
            "gp_pct": None,
            "detail": f"{cover_text} | {pressure_text}",
        })
    for item in safe_to_push[:4]:
        cover_days = item.get("stock_cover_days")
        cover_text = f"Cover {cover_days:.0f}d" if isinstance(cover_days, (int, float)) else "Cover unknown"
        product_priorities.append({
            "type": "Push",
            "type_hex": "#16A34A",
            "title": item.get("title", "Unknown item"),
            "revenue": float(item.get("revenue_90", 0) or 0),
            "gp_pct": float(item.get("gross_profit_pct", 0) or 0),
            "detail": cover_text,
        })

    supplier_rows = supplier.get("summary", {}).get("top_suppliers_by_revenue") or supplier.get("suppliers", [])[:10]
    stock_pressure = inventory.get("branch_summary", [])

    week_daily = omni.get("week", []) or []
    best_day = max(week_daily, key=lambda d: d.get("value_excl_after_discount", 0)) if week_daily else None
    worst_day = min(week_daily, key=lambda d: d.get("value_excl_after_discount", 0)) if week_daily else None

    top_stock_store = max(stock_pressure, key=lambda d: d.get("stockouts", 0)) if stock_pressure else None
    top_stock_risk = stock_risk[0] if stock_risk else None
    top_push = safe_to_push[0] if safe_to_push else None
    focus_store_code = trade_brief.get("executive", {}).get("focus_store")
    focus_store_name = STORE_LABELS.get(focus_store_code, focus_store_code or "")
    focus_store_pct = trade_brief.get("executive", {}).get("focus_store_target_pct")
    competitor_risks = trade_brief.get("sections", {}).get("competitor_watch", {}).get("price_match_risks", [])
    top_city = trade_brief.get("executive", {}).get("top_city", {})

    total_target = float(projections.get("total_target", sum(TARGETS.values())) or sum(TARGETS.values()))
    total_projected = float(projections.get("TOTAL", 0) or 0)
    total_target_pct = float(projections.get("total_target_pct", (total_projected / total_target * 100) if total_target else 0) or 0)

    actions = list(trade_brief.get("actions", []) or [])
    if not actions:
        if top_stock_risk:
            actions.append(f"Protect {top_stock_risk.get('title')} first and replenish the pressured stores immediately.")
        if focus_store_name and focus_store_pct is not None:
            actions.append(f"Treat {focus_store_name} as the same-week pace priority at {focus_store_pct:.1f}% of target.")
        if competitor_risks:
            risk = competitor_risks[0]
            actions.append(risk.get("recommendation", "Review competitor price gaps and adjust where needed."))
        if top_stock_store:
            actions.append(f"Reduce stockout pressure in {top_stock_store.get('store')} where stockouts are currently highest.")

    focus = []
    if focus_store_name and focus_store_pct is not None:
        focus.append(f"Recover {focus_store_name} pace versus target, currently at {focus_store_pct:.1f}% of MTD target.")
    if top_stock_risk:
        focus.append(f"Protect {top_stock_risk.get('title')} and clear the reorder pressure this week.")
    if top_stock_store:
        focus.append(f"Cut stockout pressure in {top_stock_store.get('store')} where stockouts are highest.")
    if competitor_risks:
        focus.append(f"Review pricing on {competitor_risks[0].get('product')} against the latest competitor signal.")
    if top_push:
        focus.append(f"Support {top_push.get('title')} with visibility while stock cover remains healthy.")
    focus = focus[:4]

    data_note = (
        "Page 2 product priorities use the current daily trade brief SKU lists because the latest branch intelligence feed "
        "did not include populated per-branch top-product tables on this run."
    )

    if not branch_rows and legacy:
        raise RuntimeError("Current local intelligence sources are missing branch rows and the legacy v7 file is too stale to use safely.")

    return {
        "generated_at": trade_brief.get("generated_at") or branch.get("generated_at") or datetime.now(SAST).isoformat(),
        "week_start": week_start,
        "week_end": week_end,
        "mtd_range": branch.get("source_dates", {}).get("mtd_range") or mtd.get("date_range") or "Unknown",
        "kpi": {
            "mtd_rev": float(combined.get("revenue_excl", 0) or 0),
            "mtd_gp": float(combined.get("gp_pct", 0) or 0),
            "mtd_days": len(full_history) or max((row["trading_days_done"] for row in branch_rows), default=0),
            "avg_daily": round(float(combined.get("revenue_excl", 0) or 0) / max(len(full_history), 1), 0),
            "cen_mtd": branch_rows[0]["mtd_revenue"],
            "gvs_mtd": branch_rows[1]["mtd_revenue"],
            "edn_mtd": branch_rows[2]["mtd_revenue"],
        },
        "branch_rows": branch_rows,
        "combined_projected": total_projected,
        "combined_target": total_target,
        "combined_target_pct": total_target_pct,
        "trend": trend,
        "trend_label": (
            f"{format_date(trend_dates[0])} to {format_date(trend_dates[-1])}" if trend_dates else "Current trade window"
        ),
        "product_priorities": product_priorities,
        "stock_pressure": stock_pressure,
        "supplier_rows": supplier_rows[:10],
        "best_day": best_day,
        "worst_day": worst_day,
        "top_stock_store": top_stock_store,
        "top_stock_risk": top_stock_risk,
        "top_push": top_push,
        "focus_store_name": focus_store_name,
        "focus_store_pct": focus_store_pct,
        "actions": actions[:4],
        "focus": focus,
        "top_city": top_city,
        "competitor_risks": competitor_risks,
        "data_note": data_note,
    }


def make_branch_table(data, ss):
    rows = [[
        Paragraph("Store", ss["TableHead"]),
        Paragraph("MTD Revenue", ss["TableHead"]),
        Paragraph("Target", ss["TableHead"]),
        Paragraph("Projected EOM", ss["TableHead"]),
        Paragraph("Pace", ss["TableHead"]),
        Paragraph("Status", ss["TableHead"]),
        Paragraph("GP%", ss["TableHead"]),
    ]]

    total_mtd = 0
    for row in data["branch_rows"]:
        total_mtd += row["mtd_revenue"]
        status_hex = pace_colour_hex(row["projected_pct"])
        rows.append([
            Paragraph(row["name"], ss["TableCell"]),
            Paragraph(fmt_r(row["mtd_revenue"]), ss["TableCellR"]),
            Paragraph(fmt_r(row["target"]), ss["TableCellR"]),
            Paragraph(fmt_r(row["projected_eom"]), ss["TableCellR"]),
            Paragraph(f"{row['projected_pct']:.0f}%", ss["TableCellR"]),
            Paragraph(f'<font color="{status_hex}">●</font> {pace_label(row["projected_pct"])}', ss["TableCell"]),
            Paragraph(f"{row['gp_pct']:.1f}%", ss["TableCellR"]),
        ])

    total_status_hex = pace_colour_hex(data["combined_target_pct"])
    rows.append([
        Paragraph("<b>Combined</b>", ss["TableCell"]),
        Paragraph(f"<b>{fmt_r(total_mtd)}</b>", ss["TableCellR"]),
        Paragraph(f"<b>{fmt_r(data['combined_target'])}</b>", ss["TableCellR"]),
        Paragraph(f"<b>{fmt_r(data['combined_projected'])}</b>", ss["TableCellR"]),
        Paragraph(f"<b>{data['combined_target_pct']:.0f}%</b>", ss["TableCellR"]),
        Paragraph(f'<font color="{total_status_hex}">●</font> {pace_label(data["combined_target_pct"])}', ss["TableCell"]),
        Paragraph(f"<b>{data['kpi']['mtd_gp']:.1f}%</b>", ss["TableCellR"]),
    ])

    table = Table(rows, colWidths=[28 * mm, 24 * mm, 24 * mm, 28 * mm, 18 * mm, 24 * mm, 18 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [C_WHITE, C_LIGHTGRAY]),
        ("BACKGROUND", (0, -1), (-1, -1), C_LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#D1D5DB")),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    return table


def make_trend_chart(trend_data):
    drawing = Drawing(160 * mm, 55 * mm)
    chart = HorizontalLineChart()
    chart.x = 12 * mm
    chart.y = 8 * mm
    chart.width = 140 * mm
    chart.height = 40 * mm

    chart.data = [
        [row.get("cen", 0) for row in trend_data],
        [row.get("gvs", 0) for row in trend_data],
        [row.get("edn", 0) for row in trend_data],
    ]
    chart.categoryAxis.categoryNames = [row["date"] for row in trend_data]
    chart.categoryAxis.labels.fontSize = 6
    chart.categoryAxis.labels.angle = 45
    chart.categoryAxis.labels.dy = -2 * mm
    chart.categoryAxis.visibleTicks = 0

    max_val = max((max(series) for series in chart.data if series), default=0)
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = int(max_val * 1.15) if max_val > 0 else 100_000
    chart.valueAxis.valueStep = max(int(chart.valueAxis.valueMax / 5), 10_000)
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.labelTextFormat = lambda v: f"R{v/1000:.0f}k"

    colours = [C_PRIMARY, C_ACCENT, HexColor("#059669")]
    names = ["Centurion", "Glen Village", "Edenvale"]
    for idx, (colour, name) in enumerate(zip(colours, names)):
        chart.lines[idx].strokeColor = colour
        chart.lines[idx].strokeWidth = 1.5
        chart.lines[idx].symbol = makeMarker("Circle")
        chart.lines[idx].symbol.size = 2
        x_pos = 12 * mm + idx * 40 * mm
        drawing.add(Rect(x_pos, 52 * mm, 3 * mm, 3 * mm, fillColor=colour, strokeColor=colour))
        drawing.add(String(x_pos + 4 * mm, 52 * mm, name, fontSize=7, fillColor=C_TEXT))

    drawing.add(chart)
    return drawing


def make_branch_watch_table(data, ss):
    rows = [[
        Paragraph("Store", ss["TableHead"]),
        Paragraph("Latest Trade", ss["TableHead"]),
        Paragraph("Latest Revenue", ss["TableHead"]),
        Paragraph("Latest GP%", ss["TableHead"]),
        Paragraph("MoM Trend", ss["TableHead"]),
        Paragraph("Key Watch", ss["TableHead"]),
    ]]

    for row in data["branch_rows"]:
        mom = row.get("mom_trend_revenue")
        mom_text = "n/a" if mom is None else f"{mom:+.1f}%"
        alerts = row.get("active_alerts", [])
        watch_text = shorten(", ".join(alerts[:2]) if alerts else "No active alerts surfaced in the latest brief", 60)
        rows.append([
            Paragraph(row["name"], ss["TableCell"]),
            Paragraph(short_date(row.get("latest_trade_date")), ss["TableCell"]),
            Paragraph(fmt_r(row.get("latest_revenue", 0)), ss["TableCellR"]),
            Paragraph(f"{row.get('latest_gp_pct', 0):.1f}%", ss["TableCellR"]),
            Paragraph(mom_text, ss["TableCellR"]),
            Paragraph(watch_text, ss["TableCell"]),
        ])

    table = Table(rows, colWidths=[24 * mm, 20 * mm, 24 * mm, 18 * mm, 18 * mm, 60 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHTGRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    return table


def make_product_priority_table(data, ss):
    rows = [[
        Paragraph("Type", ss["TableHead"]),
        Paragraph("Product", ss["TableHead"]),
        Paragraph("90d Revenue", ss["TableHead"]),
        Paragraph("GP%", ss["TableHead"]),
        Paragraph("Stock / Action", ss["TableHead"]),
    ]]

    for item in data["product_priorities"][:8]:
        gp_text = "n/a" if item["gp_pct"] is None else f"{item['gp_pct']:.1f}%"
        rows.append([
            Paragraph(f'<font color="{item["type_hex"]}"><b>{item["type"]}</b></font>', ss["TableCell"]),
            Paragraph(shorten(item["title"], 54), ss["TableCell"]),
            Paragraph(fmt_r(item["revenue"]), ss["TableCellR"]),
            Paragraph(gp_text, ss["TableCellR"]),
            Paragraph(shorten(item["detail"], 32), ss["TableCell"]),
        ])

    table = Table(rows, colWidths=[18 * mm, 76 * mm, 24 * mm, 16 * mm, 30 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHTGRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    return table


def make_stock_pressure_table(data, ss):
    rows = [[
        Paragraph("Store", ss["TableHead"]),
        Paragraph("SKUs", ss["TableHead"]),
        Paragraph("Units", ss["TableHead"]),
        Paragraph("Stockouts", ss["TableHead"]),
        Paragraph("Reorders", ss["TableHead"]),
        Paragraph("Overstock", ss["TableHead"]),
    ]]

    for row in data["stock_pressure"]:
        rows.append([
            Paragraph(row.get("store", "Unknown"), ss["TableCell"]),
            Paragraph(f"{int(row.get('products', 0)):,}", ss["TableCellR"]),
            Paragraph(f"{int(row.get('units', 0)):,}", ss["TableCellR"]),
            Paragraph(f"<font color='#DC2626'>{int(row.get('stockouts', 0)):,}</font>", ss["TableCellR"]),
            Paragraph(f"{int(row.get('reorder_triggers', 0)):,}", ss["TableCellR"]),
            Paragraph(f"{int(row.get('overstock', 0)):,}", ss["TableCellR"]),
        ])

    table = Table(rows, colWidths=[34 * mm, 18 * mm, 18 * mm, 26 * mm, 24 * mm, 22 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHTGRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    return table


def make_supplier_table(data, ss):
    rows = [[
        Paragraph("Supplier", ss["TableHead"]),
        Paragraph("Revenue", ss["TableHead"]),
        Paragraph("GP%", ss["TableHead"]),
        Paragraph("Products", ss["TableHead"]),
        Paragraph("Declining Lines", ss["TableHead"]),
    ]]

    for row in data["supplier_rows"]:
        name = row.get("supplier") or row.get("name") or "Unknown"
        revenue = float(row.get("total_revenue", row.get("rev", 0)) or 0)
        margin = float(row.get("avg_margin_pct", row.get("gp", 0)) or 0)
        products = int(row.get("product_count", row.get("prods", 0)) or 0)
        declining = int(row.get("declining_count", 0) or 0)
        rows.append([
            Paragraph(shorten(name, 28), ss["TableCell"]),
            Paragraph(fmt_r(revenue), ss["TableCellR"]),
            Paragraph(f"{margin:.1f}%", ss["TableCellR"]),
            Paragraph(f"{products:,}", ss["TableCellR"]),
            Paragraph(f"{declining:,}", ss["TableCellR"]),
        ])

    table = Table(rows, colWidths=[58 * mm, 24 * mm, 18 * mm, 20 * mm, 26 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHTGRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    return table


def generate_insights(data):
    insights = []
    shortfall = max(data["combined_target"] - data["combined_projected"], 0)
    if data["combined_target_pct"] >= 100:
        insights.append(
            f"Combined April projection is {fmt_r(data['combined_projected'])}, ahead of the {fmt_r(data['combined_target'])} target."
        )
    else:
        insights.append(
            f"Combined April projection is {fmt_r(data['combined_projected'])}, or {data['combined_target_pct']:.1f}% of target, leaving roughly {fmt_r(shortfall)} to recover."
        )

    if data.get("focus_store_name") and data.get("focus_store_pct") is not None:
        insights.append(
            f"{data['focus_store_name']} is the current pace risk at {data['focus_store_pct']:.1f}% of MTD target attainment."
        )

    if data.get("best_day") and data.get("worst_day"):
        best = data["best_day"]
        worst = data["worst_day"]
        insights.append(
            f"Best day in the current weekly window was {best.get('document_date')} at {fmt_r(best.get('value_excl_after_discount', 0))}; slowest was {worst.get('document_date')} at {fmt_r(worst.get('value_excl_after_discount', 0))}."
        )

    if data.get("top_stock_store"):
        store = data["top_stock_store"]
        insights.append(
            f"{store.get('store')} carries the heaviest stock pressure with {int(store.get('stockouts', 0)):,} stockouts and {int(store.get('reorder_triggers', 0)):,} reorder triggers."
        )

    if data.get("top_stock_risk"):
        item = data["top_stock_risk"]
        pressured = item.get("stockout_stores", []) + item.get("reorder_stores", [])
        pressure_text = ", ".join(pressured) if pressured else "the current stock list"
        insights.append(
            f"{shorten(item.get('title', 'Unknown item'), 70)} is the lead SKU to protect, with {fmt_r(item.get('revenue_90', 0))} over 90 days and pressure visible in {pressure_text}."
        )

    if data.get("top_push"):
        item = data["top_push"]
        insights.append(
            f"{shorten(item.get('title', 'Unknown item'), 70)} is safe to push at {float(item.get('gross_profit_pct', 0) or 0):.1f}% GP with about {float(item.get('stock_cover_days', 0) or 0):.0f} days of stock cover."
        )

    if data.get("top_city", {}).get("city"):
        city = data["top_city"]
        insights.append(
            f"Top online demand remains concentrated in {city.get('city')} with {fmt_r(city.get('revenue', 0))} over the 90 day customer view."
        )

    return insights[:6]


def generate_actions(data):
    return data.get("actions", [])[:4]


def add_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(C_MUTED)
    now = datetime.now(SAST).strftime("%d %B %Y %H:%M")
    canvas.drawCentredString(PAGE_W / 2, 10 * mm, f"Onelife Intelligence — Generated {now} — Confidential")
    canvas.drawRightString(PAGE_W - MARGIN, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf(data):
    now = datetime.now(SAST)
    date_str = now.strftime("%Y-%m-%d")
    out_path = os.path.join(OUT_DIR, f"onelife-weekly-report-{date_str}.pdf")
    ss = build_styles()

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=20 * mm,
    )

    story = []

    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=40 * mm, height=14 * mm)
        logo.hAlign = "LEFT"
        story.append(logo)
        story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("Onelife Intelligence — Weekly Report", ss["Title1"]))
    story.append(
        Paragraph(
            f"Week ending {format_date(data['week_end'])}  |  MTD data: {data['mtd_range']}",
            ss["Subtitle"],
        )
    )

    kpi = data["kpi"]
    kpi_cards = Table(
        [[
            make_kpi_card("MTD Revenue", fmt_r(kpi["mtd_rev"]), ss),
            make_kpi_card("Gross Profit", f"{kpi['mtd_gp']:.1f}%", ss),
            make_kpi_card("Avg Daily Rev", fmt_r(kpi["avg_daily"]), ss),
            make_kpi_card("Days Traded", str(kpi["mtd_days"]), ss),
        ]],
        colWidths=[42 * mm] * 4,
    )
    kpi_cards.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(kpi_cards)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Branch Performance", ss["SectionHead"]))
    story.append(make_branch_table(data, ss))

    story.append(PageBreak())

    story.append(Paragraph(f"Revenue Trend — {data['trend_label']}", ss["SectionHead"]))
    story.append(Paragraph("Recent Omni trade window by branch, using the latest available posted sales history.", ss["BodySmall"]))
    story.append(Spacer(1, 2 * mm))
    story.append(make_trend_chart(data["trend"]))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Branch Watchlist", ss["SectionHead"]))
    story.append(make_branch_watch_table(data, ss))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Current Product Priorities", ss["SectionHead"]))
    story.append(Paragraph("Protect the winning SKUs under pressure, and push the high-margin items with healthy cover.", ss["BodySmall"]))
    story.append(Spacer(1, 2 * mm))
    story.append(make_product_priority_table(data, ss))

    story.append(PageBreak())

    story.append(Paragraph("Branch Stock Pressure", ss["SectionHead"]))
    story.append(Paragraph("Current inventory pressure by store from the latest inventory health feed.", ss["BodySmall"]))
    story.append(Spacer(1, 2 * mm))
    story.append(make_stock_pressure_table(data, ss))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Supplier Concentration — Current Revenue Leaders", ss["SectionHead"]))
    story.append(Paragraph("Top suppliers by current scorecard revenue, including average margin and declining line count.", ss["BodySmall"]))
    story.append(Spacer(1, 2 * mm))
    story.append(make_supplier_table(data, ss))

    story.append(PageBreak())

    story.append(Paragraph("Key Observations", ss["SectionHead"]))
    for item in generate_insights(data):
        story.append(Paragraph(f"• {item}", ss["InsightBullet"]))
        story.append(Spacer(1, 1.4 * mm))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Recommended Actions", ss["SectionHead"]))
    for idx, action in enumerate(generate_actions(data), start=1):
        story.append(Paragraph(f"{idx}. {action}", ss["InsightBullet"]))
        story.append(Spacer(1, 1.4 * mm))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Week Ahead Focus", ss["SectionHead"]))
    for item in data.get("focus", []):
        story.append(Paragraph(f"→ {item}", ss["InsightBullet"]))
        story.append(Spacer(1, 1.4 * mm))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Data Note", ss["SectionHead"]))
    story.append(Paragraph(data["data_note"], ss["BodySmall"]))

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    return out_path


if __name__ == "__main__":
    report_data = build_report_data()
    path = build_pdf(report_data)
    print(f"Report generated: {path}")
