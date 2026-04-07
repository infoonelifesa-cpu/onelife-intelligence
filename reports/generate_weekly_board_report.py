#!/usr/bin/env python3
"""
Onelife Intelligence — Weekly Board Report Generator
Produces a premium 3-4 page PDF from v7_data.json.
"""
import json, os, sys, math
from datetime import datetime, timedelta, timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.widgets.markers import makeMarker

SAST = timezone(timedelta(hours=2))
WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
DATA_PATH = os.path.join(WORKSPACE, "onelife-intelligence/v7_data.json")
LOGO_PATH = os.path.join(WORKSPACE, "skills/onelife-social/onelife-logo-official.png")
OUT_DIR = os.path.join(WORKSPACE, "onelife-intelligence/reports")

# Colours
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

TARGETS = {"CEN": 1_450_000, "GVS": 330_000, "EDN": 450_000}
STORE_LABELS = {"CEN": "Centurion", "GVS": "Glen Village", "EDN": "Edenvale"}

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def load_data():
    with open(DATA_PATH) as f:
        return json.load(f)


def fmt_r(val):
    """Format Rand value."""
    if val >= 1_000_000:
        return f"R{val/1_000_000:,.1f}M"
    if val >= 1_000:
        return f"R{val:,.0f}"
    return f"R{val:,.2f}"


def pace_colour(pct):
    if pct >= 90:
        return C_GREEN
    elif pct >= 70:
        return C_AMBER
    return C_RED


def pace_label(pct):
    if pct >= 90:
        return "On Track"
    elif pct >= 70:
        return "Watch"
    return "Behind"


def build_styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("Title1", parent=ss["Title"], fontSize=22, textColor=C_PRIMARY,
                          spaceAfter=2 * mm, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("Subtitle", parent=ss["Normal"], fontSize=11, textColor=C_MUTED,
                          spaceAfter=6 * mm))
    ss.add(ParagraphStyle("SectionHead", parent=ss["Heading2"], fontSize=14, textColor=C_ACCENT,
                          spaceBefore=6 * mm, spaceAfter=3 * mm, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=9, textColor=C_TEXT, leading=13))
    ss.add(ParagraphStyle("BodySmall", parent=ss["Normal"], fontSize=8, textColor=C_MUTED, leading=11))
    ss.add(ParagraphStyle("KPIValue", parent=ss["Normal"], fontSize=18, textColor=C_PRIMARY,
                          fontName="Helvetica-Bold", alignment=TA_CENTER))
    ss.add(ParagraphStyle("KPILabel", parent=ss["Normal"], fontSize=8, textColor=C_MUTED,
                          alignment=TA_CENTER))
    ss.add(ParagraphStyle("TableHead", parent=ss["Normal"], fontSize=9, textColor=C_WHITE,
                          fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("TableCell", parent=ss["Normal"], fontSize=9, textColor=C_TEXT))
    ss.add(ParagraphStyle("TableCellR", parent=ss["Normal"], fontSize=9, textColor=C_TEXT,
                          alignment=TA_RIGHT))
    ss.add(ParagraphStyle("Footer", parent=ss["Normal"], fontSize=7, textColor=C_MUTED,
                          alignment=TA_CENTER))
    ss.add(ParagraphStyle("InsightBullet", parent=ss["Normal"], fontSize=9, textColor=C_TEXT,
                          leading=13, leftIndent=8 * mm, bulletIndent=2 * mm))
    return ss


def make_kpi_card(label, value, ss):
    """Return a small table acting as a KPI card."""
    t = Table(
        [[Paragraph(str(value), ss["KPIValue"])],
         [Paragraph(label, ss["KPILabel"])]],
        colWidths=[38 * mm], rowHeights=[10 * mm, 6 * mm]
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_LIGHT),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, C_ACCENT),
        ("TOPPADDING", (0, 0), (-1, 0), 3 * mm),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 2 * mm),
    ]))
    return t


def make_branch_table(data, ss):
    """Branch performance table with traffic lights."""
    kpi = data["kpi"]
    days = kpi["mtd_days"]
    # Assume ~22 trading days in April
    trading_days_in_month = 22

    rows = []
    header = [
        Paragraph("Store", ss["TableHead"]),
        Paragraph("MTD Revenue", ss["TableHead"]),
        Paragraph("Target", ss["TableHead"]),
        Paragraph("Pace to Target", ss["TableHead"]),
        Paragraph("Status", ss["TableHead"]),
        Paragraph("GP%", ss["TableHead"]),
    ]
    rows.append(header)

    stores = [
        ("CEN", "Centurion", kpi["cen_mtd"]),
        ("GVS", "Glen Village", kpi["gvs_mtd"]),
        ("EDN", "Edenvale", kpi["edn_mtd"]),
    ]

    total_mtd = 0
    total_target = 0
    for code, name, mtd in stores:
        target = TARGETS[code]
        projected = (mtd / days * trading_days_in_month) if days > 0 else 0
        pace_pct = (projected / target * 100) if target > 0 else 0
        gp = data["matrix"].get(code, {}).get("gp", 0)
        colour = pace_colour(pace_pct)
        status = pace_label(pace_pct)
        total_mtd += mtd
        total_target += target

        rows.append([
            Paragraph(name, ss["TableCell"]),
            Paragraph(fmt_r(mtd), ss["TableCellR"]),
            Paragraph(fmt_r(target), ss["TableCellR"]),
            Paragraph(f"{pace_pct:.0f}%", ss["TableCellR"]),
            Paragraph(f'<font color="#{colour.hexval()[2:]}">\u25cf</font> {status}', ss["TableCell"]),
            Paragraph(f"{gp:.1f}%", ss["TableCellR"]),
        ])

    # Total row
    total_projected = (total_mtd / days * trading_days_in_month) if days > 0 else 0
    total_pace = (total_projected / total_target * 100) if total_target > 0 else 0
    total_colour = pace_colour(total_pace)
    rows.append([
        Paragraph("<b>Combined</b>", ss["TableCell"]),
        Paragraph(f"<b>{fmt_r(total_mtd)}</b>", ss["TableCellR"]),
        Paragraph(f"<b>{fmt_r(total_target)}</b>", ss["TableCellR"]),
        Paragraph(f"<b>{total_pace:.0f}%</b>", ss["TableCellR"]),
        Paragraph(f'<font color="#{total_colour.hexval()[2:]}">\u25cf</font> {pace_label(total_pace)}', ss["TableCell"]),
        Paragraph(f"<b>{kpi['mtd_gp']:.1f}%</b>", ss["TableCellR"]),
    ])

    col_widths = [30 * mm, 28 * mm, 28 * mm, 28 * mm, 24 * mm, 18 * mm]
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
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
    return t


def make_trend_chart(trend_data):
    """Create a line chart of daily revenue trends."""
    drawing = Drawing(160 * mm, 55 * mm)

    chart = HorizontalLineChart()
    chart.x = 12 * mm
    chart.y = 8 * mm
    chart.width = 140 * mm
    chart.height = 40 * mm

    dates = [t["date"] for t in trend_data]
    cen_vals = [t.get("cen", 0) for t in trend_data]
    gvs_vals = [t.get("gvs", 0) for t in trend_data]
    edn_vals = [t.get("edn", 0) for t in trend_data]

    chart.data = [cen_vals, gvs_vals, edn_vals]

    chart.categoryAxis.categoryNames = dates
    chart.categoryAxis.labels.fontSize = 6
    chart.categoryAxis.labels.angle = 45
    chart.categoryAxis.labels.dy = -2 * mm
    chart.categoryAxis.visibleTicks = 0

    max_val = max(max(cen_vals, default=0), max(gvs_vals, default=0), max(edn_vals, default=0))
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = int(max_val * 1.15) if max_val > 0 else 100000
    chart.valueAxis.valueStep = int(chart.valueAxis.valueMax / 5) or 10000
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labelTextFormat = lambda v: f"R{v/1000:.0f}k"

    colours = [C_PRIMARY, C_ACCENT, HexColor("#059669")]
    names = ["Centurion", "Glen Village", "Edenvale"]
    for i, (c, n) in enumerate(zip(colours, names)):
        chart.lines[i].strokeColor = c
        chart.lines[i].strokeWidth = 1.5
        chart.lines[i].symbol = makeMarker("Circle")
        chart.lines[i].symbol.size = 2

    # Legend
    for i, (c, n) in enumerate(zip(colours, names)):
        x_pos = 12 * mm + i * 40 * mm
        drawing.add(Rect(x_pos, 52 * mm, 3 * mm, 3 * mm, fillColor=c, strokeColor=c))
        drawing.add(String(x_pos + 4 * mm, 52 * mm, n, fontSize=7, fillColor=C_TEXT))

    drawing.add(chart)
    return drawing


def make_top_products_table(data, ss):
    """Top products per branch."""
    rows = []
    header = [
        Paragraph("Branch", ss["TableHead"]),
        Paragraph("#", ss["TableHead"]),
        Paragraph("Product", ss["TableHead"]),
        Paragraph("Revenue", ss["TableHead"]),
    ]
    rows.append(header)

    for code in ["CEN", "GVS", "EDN"]:
        matrix = data["matrix"].get(code, {})
        top = matrix.get("top", [])[:5]
        for i, item in enumerate(top):
            rows.append([
                Paragraph(STORE_LABELS[code] if i == 0 else "", ss["TableCell"]),
                Paragraph(str(i + 1), ss["TableCell"]),
                Paragraph(item["desc"][:40], ss["TableCell"]),
                Paragraph(fmt_r(item["rev"]), ss["TableCellR"]),
            ])

    col_widths = [28 * mm, 8 * mm, 80 * mm, 28 * mm]
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHTGRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    return t


def make_branch_kpi_table(data, ss):
    """Branch-level KPIs: transactions, basket size, GP%."""
    rows = []
    header = [
        Paragraph("Branch", ss["TableHead"]),
        Paragraph("Revenue", ss["TableHead"]),
        Paragraph("Transactions", ss["TableHead"]),
        Paragraph("Avg Basket", ss["TableHead"]),
        Paragraph("GP%", ss["TableHead"]),
    ]
    rows.append(header)

    for code in ["CEN", "GVS", "EDN"]:
        m = data["matrix"].get(code, {})
        rows.append([
            Paragraph(STORE_LABELS[code], ss["TableCell"]),
            Paragraph(fmt_r(m.get("rev", 0)), ss["TableCellR"]),
            Paragraph(f"{m.get('txn', 0):,}", ss["TableCellR"]),
            Paragraph(fmt_r(m.get("basket", 0)), ss["TableCellR"]),
            Paragraph(f"{m.get('gp', 0):.1f}%", ss["TableCellR"]),
        ])

    col_widths = [30 * mm, 30 * mm, 28 * mm, 28 * mm, 20 * mm]
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHTGRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    return t


def make_gaps_table(data, ss):
    """Cross-store gap analysis."""
    rows = []
    header = [
        Paragraph("Product", ss["TableHead"]),
        Paragraph("Revenue (where stocked)", ss["TableHead"]),
        Paragraph("Qty Sold", ss["TableHead"]),
        Paragraph("GP%", ss["TableHead"]),
        Paragraph("Missing From", ss["TableHead"]),
    ]
    rows.append(header)

    for gap in data["gaps"][:10]:
        rows.append([
            Paragraph(gap["desc"][:35], ss["TableCell"]),
            Paragraph(fmt_r(gap["rev"]), ss["TableCellR"]),
            Paragraph(str(gap["qty"]), ss["TableCellR"]),
            Paragraph(f"{gap['gp']:.1f}%", ss["TableCellR"]),
            Paragraph(", ".join(gap.get("miss", [])), ss["TableCell"]),
        ])

    col_widths = [45 * mm, 32 * mm, 18 * mm, 16 * mm, 28 * mm]
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHTGRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    return t


def make_supplier_table(data, ss):
    """Top suppliers by revenue."""
    rows = []
    header = [
        Paragraph("Supplier", ss["TableHead"]),
        Paragraph("Revenue", ss["TableHead"]),
        Paragraph("GP%", ss["TableHead"]),
        Paragraph("Units", ss["TableHead"]),
        Paragraph("ABC", ss["TableHead"]),
    ]
    rows.append(header)

    for s in data["suppliers"][:10]:
        rows.append([
            Paragraph(s["name"][:30], ss["TableCell"]),
            Paragraph(fmt_r(s["rev"]), ss["TableCellR"]),
            Paragraph(f"{s['gp']:.1f}%", ss["TableCellR"]),
            Paragraph(f"{s['qty']:,}", ss["TableCellR"]),
            Paragraph(s.get("abc", ""), ss["TableCell"]),
        ])

    col_widths = [45 * mm, 30 * mm, 18 * mm, 22 * mm, 14 * mm]
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHTGRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    return t


def generate_insights(data):
    """Auto-generate observations from data patterns."""
    insights = []
    kpi = data["kpi"]
    alerts = data["alerts"]

    # GP observation
    if kpi["mtd_gp"] >= 34:
        insights.append(f"Blended GP is solid at {kpi['mtd_gp']:.1f}%, above the 33% floor.")
    else:
        insights.append(f"⚠ Blended GP at {kpi['mtd_gp']:.1f}% is below the 34% target. Review low-margin lines.")

    # Critical stock alerts
    n_crit = len(alerts.get("critical", []))
    if n_crit > 0:
        insights.append(f"⚠ {n_crit} products are critically out of stock, representing lost GP daily.")
        top_crit = alerts["critical"][:3]
        descs = ", ".join(c["desc"] for c in top_crit)
        insights.append(f"Top stock-outs: {descs}.")

    # Warning alerts
    n_warn = len(alerts.get("warning", []))
    if n_warn > 0:
        insights.append(f"{n_warn} products have dangerously low stock levels.")

    # Gap opportunities
    top_gap = data["gaps"][0] if data["gaps"] else None
    if top_gap:
        insights.append(
            f"Biggest cross-store gap: {top_gap['desc']} ({fmt_r(top_gap['rev'])} revenue) "
            f"missing from {', '.join(top_gap['miss'])}."
        )

    # Week trading pattern
    week = data.get("week", {})
    daily = week.get("daily", [])
    if daily:
        best = max(daily, key=lambda d: d["rev"])
        worst = min(daily, key=lambda d: d["rev"])
        insights.append(f"Best day this week: {best['date']} ({fmt_r(best['rev'])}). "
                        f"Slowest: {worst['date']} ({fmt_r(worst['rev'])}).")

    return insights


def generate_actions(data):
    """Auto-generate recommended actions."""
    actions = []
    alerts = data["alerts"]

    if alerts.get("critical"):
        actions.append("URGENT: Restock critical out-of-stock items, prioritising highest daily GP loss.")

    gaps = data["gaps"][:3]
    if gaps:
        miss_stores = set()
        for g in gaps:
            miss_stores.update(g.get("miss", []))
        actions.append(f"Cross-stock top gap products into {', '.join(sorted(miss_stores))}.")

    kpi = data["kpi"]
    if kpi["mtd_gp"] < 34:
        actions.append("Review pricing on low-GP lines. Target blended GP of 34%+.")

    actions.append("Continue weekly cadence: Monday report, Thursday email, Friday ad review.")

    return actions


def add_footer(canvas, doc):
    """Page footer."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(C_MUTED)
    now = datetime.now(SAST).strftime("%d %B %Y %H:%M")
    canvas.drawCentredString(PAGE_W / 2, 10 * mm,
                             f"Onelife Intelligence — Generated {now} — Confidential")
    canvas.drawRightString(PAGE_W - MARGIN, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf(data):
    now = datetime.now(SAST)
    date_str = now.strftime("%Y-%m-%d")
    out_path = os.path.join(OUT_DIR, f"onelife-weekly-report-{date_str}.pdf")

    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=20 * mm,
    )

    ss = build_styles()
    story = []

    # --- PAGE 1: Executive Summary ---
    # Logo
    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=40 * mm, height=14 * mm)
        logo.hAlign = "LEFT"
        story.append(logo)
        story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("Onelife Intelligence — Weekly Report", ss["Title1"]))
    story.append(Paragraph(f"Week ending 5 April 2026  |  Data: {data['date_range']}", ss["Subtitle"]))

    # KPI Cards
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

    # Branch Performance
    story.append(Paragraph("Branch Performance", ss["SectionHead"]))
    story.append(make_branch_table(data, ss))

    story.append(PageBreak())

    # --- PAGE 2: Branch Deep Dive ---
    story.append(Paragraph("Revenue Trend — Last 30 Days", ss["SectionHead"]))
    story.append(make_trend_chart(data["trend"]))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Branch KPIs", ss["SectionHead"]))
    story.append(make_branch_kpi_table(data, ss))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Top Products by Branch", ss["SectionHead"]))
    story.append(make_top_products_table(data, ss))

    story.append(PageBreak())

    # --- PAGE 3: Stock & Gaps ---
    story.append(Paragraph("Cross-Store Gap Opportunities", ss["SectionHead"]))
    story.append(Paragraph(
        "Products generating significant revenue at one branch but not stocked at another.",
        ss["BodySmall"]
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(make_gaps_table(data, ss))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Supplier Concentration — Top 10", ss["SectionHead"]))
    story.append(make_supplier_table(data, ss))

    story.append(PageBreak())

    # --- PAGE 4: Insights & Actions ---
    story.append(Paragraph("Key Observations", ss["SectionHead"]))
    insights = generate_insights(data)
    for ins in insights:
        story.append(Paragraph(f"• {ins}", ss["InsightBullet"]))
        story.append(Spacer(1, 1.5 * mm))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Recommended Actions", ss["SectionHead"]))
    actions = generate_actions(data)
    for i, act in enumerate(actions, 1):
        story.append(Paragraph(f"{i}. {act}", ss["InsightBullet"]))
        story.append(Spacer(1, 1.5 * mm))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Week Ahead Focus", ss["SectionHead"]))
    focus = [
        "Monitor restock progress on critical out-of-stock items.",
        "Review cross-store gap list with branch managers.",
        "Prep Thursday Klaviyo email campaign.",
        "Track daily revenue pace against monthly targets.",
    ]
    for f in focus:
        story.append(Paragraph(f"→ {f}", ss["InsightBullet"]))
        story.append(Spacer(1, 1.5 * mm))

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    return out_path


if __name__ == "__main__":
    data = load_data()
    path = build_pdf(data)
    print(f"Report generated: {path}")
