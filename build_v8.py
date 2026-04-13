#!/usr/bin/env python3
"""
Onelife Intelligence Dashboard V8 Builder
Generates the V8 dashboard as a preview by default, with optional live promotion.
"""
import argparse
import json, os, sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import calendar
import subprocess

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


def parse_doc_date(value):
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return None

def load_ga4():
    """Pull GA4 analytics data. Returns dict with channel performance, engagement, device, daily trends."""
    try:
        sa_path = os.path.join(WORKSPACE, "credentials/onelife-analytics-sa.json")
        if not os.path.exists(sa_path):
            return None
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = sa_path
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric, OrderBy

        client = BetaAnalyticsDataClient()
        PROP = "properties/525312444"

        # Channel performance
        ch_resp = client.run_report(RunReportRequest(
            property=PROP,
            date_ranges=[DateRange(start_date="28daysAgo", end_date="today")],
            dimensions=[Dimension(name="sessionDefaultChannelGroup")],
            metrics=[Metric(name="sessions"), Metric(name="totalUsers"), Metric(name="ecommercePurchases"),
                     Metric(name="purchaseRevenue"), Metric(name="bounceRate")],
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
            limit=12,
        ))
        channels = []
        for row in ch_resp.rows:
            sess = int(row.metric_values[0].value)
            users = int(row.metric_values[1].value)
            orders = int(row.metric_values[2].value)
            rev = float(row.metric_values[3].value)
            bounce = float(row.metric_values[4].value) * 100
            channels.append({
                "name": row.dimension_values[0].value,
                "sessions": sess, "users": users, "orders": orders,
                "revenue": rev, "bounce": bounce,
                "conv": (orders/sess*100) if sess > 0 else 0,
                "rps": rev/sess if sess > 0 else 0,
            })

        # Totals
        tot_sessions = sum(c["sessions"] for c in channels)
        tot_users = sum(c["users"] for c in channels)
        tot_orders = sum(c["orders"] for c in channels)
        tot_revenue = sum(c["revenue"] for c in channels)
        tot_conv = (tot_orders/tot_sessions*100) if tot_sessions > 0 else 0

        # Device breakdown
        dev_resp = client.run_report(RunReportRequest(
            property=PROP,
            date_ranges=[DateRange(start_date="28daysAgo", end_date="today")],
            dimensions=[Dimension(name="deviceCategory")],
            metrics=[Metric(name="sessions"), Metric(name="ecommercePurchases"), Metric(name="purchaseRevenue")],
            limit=5,
        ))
        devices = []
        for row in dev_resp.rows:
            devices.append({
                "device": row.dimension_values[0].value,
                "sessions": int(row.metric_values[0].value),
                "orders": int(row.metric_values[1].value),
                "revenue": float(row.metric_values[2].value),
            })

        # Engagement
        eng_resp = client.run_report(RunReportRequest(
            property=PROP,
            date_ranges=[DateRange(start_date="28daysAgo", end_date="today")],
            metrics=[Metric(name="bounceRate"), Metric(name="averageSessionDuration"),
                     Metric(name="screenPageViewsPerSession"), Metric(name="engagedSessions")],
            limit=1,
        ))
        eng = eng_resp.rows[0] if eng_resp.rows else None
        engagement = {
            "bounce": float(eng.metric_values[0].value) * 100 if eng else 0,
            "avg_duration": float(eng.metric_values[1].value) if eng else 0,
            "pages_per_session": float(eng.metric_values[2].value) if eng else 0,
            "engaged": int(eng.metric_values[3].value) if eng else 0,
        }

        # Daily trend (14 days)
        daily_resp = client.run_report(RunReportRequest(
            property=PROP,
            date_ranges=[DateRange(start_date="14daysAgo", end_date="today")],
            dimensions=[Dimension(name="date")],
            metrics=[Metric(name="sessions"), Metric(name="purchaseRevenue")],
            order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
            limit=30,
        ))
        daily_sessions = []
        daily_revenue = []
        for row in sorted(daily_resp.rows, key=lambda r: r.dimension_values[0].value):
            daily_sessions.append(int(row.metric_values[0].value))
            daily_revenue.append(float(row.metric_values[1].value))

        # Top converting pages
        page_resp = client.run_report(RunReportRequest(
            property=PROP,
            date_ranges=[DateRange(start_date="28daysAgo", end_date="today")],
            dimensions=[Dimension(name="landingPage")],
            metrics=[Metric(name="sessions"), Metric(name="purchaseRevenue"), Metric(name="ecommercePurchases")],
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="purchaseRevenue"), desc=True)],
            limit=10,
        ))
        top_pages = []
        for row in page_resp.rows:
            rev = float(row.metric_values[1].value)
            if rev > 0:
                top_pages.append({
                    "page": row.dimension_values[0].value,
                    "sessions": int(row.metric_values[0].value),
                    "revenue": rev,
                    "orders": int(row.metric_values[2].value),
                })

        # Previous period for comparison
        prev_resp = client.run_report(RunReportRequest(
            property=PROP,
            date_ranges=[DateRange(start_date="56daysAgo", end_date="29daysAgo")],
            metrics=[Metric(name="sessions"), Metric(name="ecommercePurchases"), Metric(name="purchaseRevenue")],
            limit=1,
        ))
        prev = prev_resp.rows[0] if prev_resp.rows else None
        prev_sessions = int(prev.metric_values[0].value) if prev else 0
        prev_orders = int(prev.metric_values[1].value) if prev else 0
        prev_revenue = float(prev.metric_values[2].value) if prev else 0

        sessions_chg = ((tot_sessions - prev_sessions) / prev_sessions * 100) if prev_sessions > 0 else 0
        revenue_chg = ((tot_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0
        orders_chg = ((tot_orders - prev_orders) / prev_orders * 100) if prev_orders > 0 else 0

        return {
            "channels": channels, "devices": devices, "engagement": engagement,
            "daily_sessions": daily_sessions, "daily_revenue": daily_revenue,
            "top_pages": top_pages,
            "totals": {"sessions": tot_sessions, "users": tot_users, "orders": tot_orders,
                       "revenue": tot_revenue, "conv": tot_conv},
            "changes": {"sessions": sessions_chg, "revenue": revenue_chg, "orders": orders_chg},
            "prev": {"sessions": prev_sessions, "orders": prev_orders, "revenue": prev_revenue},
        }
    except Exception as e:
        print(f"WARN: GA4 failed: {e}", file=sys.stderr)
        return None

def load_search_console():
    """Pull Search Console data via API. Returns dict with pages, queries, totals, and period comparison."""
    try:
        sa_path = os.path.join(WORKSPACE, "credentials/onelife-analytics-sa.json")
        if not os.path.exists(sa_path):
            print("WARN: No SA credentials for Search Console", file=sys.stderr)
            return None
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = sa_path
        from googleapiclient.discovery import build
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(
            sa_path, scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
        )
        service = build("searchconsole", "v1", credentials=creds)
        site = "https://onelife.co.za/"

        end = (NOW - timedelta(days=2)).strftime("%Y-%m-%d")
        start = (NOW - timedelta(days=30)).strftime("%Y-%m-%d")
        prev_end = (NOW - timedelta(days=31)).strftime("%Y-%m-%d")
        prev_start = (NOW - timedelta(days=59)).strftime("%Y-%m-%d")

        # Current period — top pages
        pages_resp = service.searchanalytics().query(siteUrl=site, body={
            "startDate": start, "endDate": end, "dimensions": ["page"], "rowLimit": 20
        }).execute()

        # Current period — top queries
        queries_resp = service.searchanalytics().query(siteUrl=site, body={
            "startDate": start, "endDate": end, "dimensions": ["query"], "rowLimit": 25
        }).execute()

        # Current period — daily totals
        daily_resp = service.searchanalytics().query(siteUrl=site, body={
            "startDate": start, "endDate": end, "dimensions": ["date"], "rowLimit": 30
        }).execute()

        # Previous period — daily totals for comparison
        prev_resp = service.searchanalytics().query(siteUrl=site, body={
            "startDate": prev_start, "endDate": prev_end, "dimensions": ["date"], "rowLimit": 30
        }).execute()

        # Compute totals
        curr_clicks = sum(r["clicks"] for r in daily_resp.get("rows", []))
        curr_impr = sum(r["impressions"] for r in daily_resp.get("rows", []))
        curr_ctr = curr_clicks / curr_impr * 100 if curr_impr > 0 else 0
        curr_pos = sum(r["position"] for r in daily_resp.get("rows", [])) / max(len(daily_resp.get("rows", [])), 1)

        prev_clicks = sum(r["clicks"] for r in prev_resp.get("rows", []))
        prev_impr = sum(r["impressions"] for r in prev_resp.get("rows", []))
        prev_ctr = prev_clicks / prev_impr * 100 if prev_impr > 0 else 0

        clicks_chg = ((curr_clicks - prev_clicks) / prev_clicks * 100) if prev_clicks > 0 else 0
        impr_chg = ((curr_impr - prev_impr) / prev_impr * 100) if prev_impr > 0 else 0

        # Categorise pages
        blogs, products, collections = [], [], []
        for row in pages_resp.get("rows", []):
            page = row["keys"][0].replace("https://onelife.co.za", "")
            entry = {"page": page, "clicks": row["clicks"], "impr": row["impressions"],
                     "ctr": row["ctr"]*100, "pos": row["position"]}
            if "/blogs/" in page: blogs.append(entry)
            elif "/products/" in page: products.append(entry)
            elif "/collections/" in page: collections.append(entry)
        blogs.sort(key=lambda x: x["clicks"], reverse=True)
        products.sort(key=lambda x: x["clicks"], reverse=True)

        # Categorise queries
        branded, non_branded = [], []
        for row in queries_resp.get("rows", []):
            q = row["keys"][0]
            entry = {"q": q, "clicks": row["clicks"], "impr": row["impressions"],
                     "ctr": row["ctr"]*100, "pos": row["position"]}
            if any(x in q.lower() for x in ["onelife", "one life", "one health"]):
                branded.append(entry)
            else:
                non_branded.append(entry)

        # Daily click trend for sparkline
        daily_clicks = []
        for row in sorted(daily_resp.get("rows", []), key=lambda r: r["keys"][0]):
            daily_clicks.append(row["clicks"])

        return {
            "period": f"{start} to {end}",
            "clicks": curr_clicks, "impressions": curr_impr,
            "ctr": curr_ctr, "position": curr_pos,
            "clicks_chg": clicks_chg, "impr_chg": impr_chg,
            "prev_ctr": prev_ctr,
            "blogs": blogs[:6], "products": products[:6], "collections": collections[:4],
            "branded": branded[:5], "non_branded": non_branded[:12],
            "daily_clicks": daily_clicks,
        }
    except Exception as e:
        print(f"WARN: Search Console failed: {e}", file=sys.stderr)
        return None

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


def wow_pct(this_vals, last_vals):
    """Week-over-week percentage change"""
    t, l = sum(this_vals), sum(last_vals)
    if l == 0: return None
    return (t - l) / l * 100

def trend_badge(pct):
    """HTML trend indicator with arrow"""
    if pct is None: return '<span style="color:#475569;font-size:11px">\u2014</span>'
    arrow = "\u2191" if pct >= 0 else "\u2193"
    col = "#22c55e" if pct >= 0 else "#ef4444"
    sign = "+" if pct >= 0 else "-"
    return f'<span style="color:{col};font-size:11px;font-weight:700">{arrow}&nbsp;{sign}{abs(pct):.1f}%</span>'

def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def load_reviews_data():
    """Load the latest Google Reviews snapshot and week-start for comparison."""
    reviews_path = os.path.join(WORKSPACE, "data/google_reviews/review_history.json")
    baseline = {
        "date": NOW.strftime("%Y-%m-%d"),
        "stores": {
            "CEN": {"rating": 4.7, "total_reviews": 294, "breakdown": {"5": 240, "4": 36, "3": 5, "2": 1, "1": 12}},
            "GVS": {"rating": 5.0, "total_reviews": 44, "breakdown": {"5": 44, "4": 0, "3": 0, "2": 0, "1": 0}},
            "EDN": {"rating": 4.9, "total_reviews": 31, "breakdown": {"5": 29, "4": 2, "3": 0, "2": 0, "1": 0}},
        }
    }
    targets = {"CEN": 5, "GVS": 3, "EDN": 3}
    try:
        with open(reviews_path) as f:
            history = json.load(f)
        snaps = history.get("snapshots", [])
        if not snaps:
            return {"latest": baseline, "week_start": baseline, "targets": targets}
        latest = snaps[-1]
        # Find Monday's snapshot
        monday = NOW - timedelta(days=NOW.weekday())
        monday_str = monday.strftime("%Y-%m-%d")
        week_start = baseline
        for s in snaps:
            if s["date"] <= monday_str:
                week_start = s
        return {"latest": latest, "week_start": week_start, "targets": targets}
    except Exception as e:
        print(f"WARN: Reviews data: {e}", file=sys.stderr)
        return {"latest": baseline, "week_start": baseline, "targets": targets}


def load_supplier_lookup():
    """Prefer the explicit supplier master exported from XLSX, then fall back to legacy memory mapping."""
    preferred = load_json("onelife-intelligence/data/suppliers_master.json")
    fallback = load_json("memory/supplier_names.json")
    merged = {}
    if isinstance(fallback, list):
        fallback = dict(fallback)
    if isinstance(fallback, dict):
        merged.update(fallback)
    if isinstance(preferred, list):
        preferred = dict(preferred)
    if isinstance(preferred, dict):
        merged.update(preferred)
    return merged


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def score_label(score):
    if score >= 80:
        return "High"
    if score >= 60:
        return "Medium"
    return "Low"


def freshness_class(days_old, ok_days=0, warn_days=2):
    if days_old <= ok_days:
        return "good", "Fresh"
    if days_old <= warn_days:
        return "warn", "Lagging"
    return "bad", "Stale"


def parse_isoish_datetime(value):
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=SAST)
        return dt.astimezone(SAST)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:len(fmt)], fmt).replace(tzinfo=SAST)
        except Exception:
            continue
    return None


def shift_year_month(year, month, delta_months):
    month_index = (year * 12 + (month - 1)) + delta_months
    new_year = month_index // 12
    new_month = month_index % 12 + 1
    return new_year, new_month

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Write V8 output to live index.html as well as v8 preview")
    args = parser.parse_args()
    # Load data
    omni = load_json("memory/omni_cache.json")
    daily_cache = load_json("memory/daily-sales-cache.json")
    sup_names = load_supplier_lookup()
    gp_data = load_json("memory/snapshots/2026-02/ana_popular_gp.json")
    ga4 = load_ga4()  # Google Analytics 4 data
    gsc = load_search_console()  # Google Search Console data
    reviews = load_reviews_data()  # Google Reviews tracker

    # MTD — compute from daily histories (more accurate than MTD combined endpoint)
    ho_history = omni.get("ho_history", omni.get("full_history", []))
    gvs_history = omni.get("gvs_history", [])
    edn_history = omni.get("edn_history", [])

    def history_dates_for_month(history, month):
        dates = []
        for entry in history:
            doc_date = parse_doc_date(entry.get("document_date", ""))
            if doc_date and doc_date.strftime("%Y-%m") == month:
                dates.append(doc_date)
        return sorted(set(dates))

    def sum_history(history, month):
        month_dates = history_dates_for_month(history, month)
        rev = sum(e.get("value_excl_after_discount", 0) for e in history if e.get("document_date", "").startswith(month))
        gp = sum(e.get("gross_profit", 0) for e in history if e.get("document_date", "").startswith(month))
        days = len(month_dates)
        last_trade_date = month_dates[-1] if month_dates else None
        return {"rev": rev, "gp": gp, "days": days, "last_trade_date": last_trade_date}

    available_months = sorted({
        parse_doc_date(e.get("document_date", "")).strftime("%Y-%m")
        for history in [ho_history, gvs_history, edn_history]
        for e in history
        if parse_doc_date(e.get("document_date", ""))
    })

    report_month = NOW.strftime("%Y-%m")
    provisional = [
        sum_history(ho_history, report_month),
        sum_history(gvs_history, report_month),
        sum_history(edn_history, report_month),
    ]
    if sum(d["rev"] for d in provisional) == 0 and available_months:
        report_month = available_months[-1]

    report_year, report_month_num = map(int, report_month.split("-"))
    report_month_label = datetime(report_year, report_month_num, 1, tzinfo=SAST).strftime("%B %Y")
    days_in_month_total = calendar.monthrange(report_year, report_month_num)[1]

    cen_mtd_data = sum_history(ho_history, report_month)
    gvs_mtd_data = sum_history(gvs_history, report_month)
    edn_mtd_data = sum_history(edn_history, report_month)

    store_mtd = {"CEN": cen_mtd_data, "GVS": gvs_mtd_data, "EDN": edn_mtd_data}

    mtd_rev = cen_mtd_data["rev"] + gvs_mtd_data["rev"] + edn_mtd_data["rev"]
    mtd_gp = cen_mtd_data["gp"] + gvs_mtd_data["gp"] + edn_mtd_data["gp"]
    mtd_gp_pct = (mtd_gp / mtd_rev * 100) if mtd_rev > 0 else 0

    # days_elapsed = latest traded day across all stores (for KPI display)
    days_elapsed = max(
        (d["last_trade_date"].day if d.get("last_trade_date") else 0)
        for d in [cen_mtd_data, gvs_mtd_data, edn_mtd_data]
    ) or NOW.day

    # Store-level run rates and projections
    store_analysis = {}
    for s in ["CEN", "GVS", "EDN"]:
        data = store_mtd[s]
        trading_days = data["days"]
        run_rate = data["rev"] / trading_days if trading_days > 0 else 0
        last_trade_date = data.get("last_trade_date")
        last_trade_day = last_trade_date.day if last_trade_date else 0

        # Important: projections must use the last traded day in Omni history,
        # not the current wall-clock date. Otherwise pre-trade mornings collapse
        # projected month-end to current MTD even when today's trade is not in yet.
        if s == "CEN":
            # CEN closed Sundays — count remaining weekdays from the day AFTER
            # the latest traded date we actually have in Omni.
            remaining_trading = 0
            for d in range(last_trade_day + 1, days_in_month_total + 1):
                future_date = datetime(report_year, report_month_num, d, tzinfo=SAST)
                if future_date.weekday() != 6:  # 6 = Sunday
                    remaining_trading += 1
        else:
            # GVS + EDN open 7 days. If latest trade is yesterday, today still counts.
            remaining_trading = max(0, days_in_month_total - last_trade_day)
        projected = data["rev"] + (run_rate * remaining_trading)
        pct_of_target = (projected / TARGETS[s] * 100) if TARGETS[s] > 0 else 0
        actual_pct_of_target = (data["rev"] / TARGETS[s] * 100) if TARGETS[s] > 0 else 0
        # Required daily to hit target
        shortfall = TARGETS[s] - data["rev"]
        required_daily = shortfall / remaining_trading if remaining_trading > 0 else 0
        store_analysis[s] = {
            "run_rate": run_rate,
            "projected": projected,
            "pct": pct_of_target,
            "actual_pct": actual_pct_of_target,
            "trading_days": trading_days,
            "remaining_trading": remaining_trading,
            "required_daily": required_daily,
            "gap": shortfall,
            "gp": data["gp"],
            "gp_pct": (data["gp"] / data["rev"] * 100) if data["rev"] > 0 else 0,
            "last_trade_date": last_trade_date,
        }

    # Combined projections
    combined_projected = sum(sa["projected"] for sa in store_analysis.values())
    total_target = sum(TARGETS.values())
    combined_daily_avg = sum(sa["run_rate"] for sa in store_analysis.values())
    days_remaining = max((sa["remaining_trading"] for sa in store_analysis.values()), default=0)

    yesterday_data = omni.get("yesterday", {})
    yesterday_rev = yesterday_data.get("combined", {}).get("revenue_excl", 0)

    # === TODAY'S / LATEST DAY SALES + GP PER STORE ===
    def latest_day(history):
        if not history:
            return {"date": "", "rev": 0, "gp": 0}
        sorted_days = sorted(
            [e for e in history if e.get("document_date")],
            key=lambda e: e["document_date"], reverse=True
        )
        if not sorted_days:
            return {"date": "", "rev": 0, "gp": 0}
        latest = sorted_days[0]
        return {
            "date": latest.get("document_date", ""),
            "rev": latest.get("value_excl_after_discount", 0),
            "gp": latest.get("gross_profit", 0),
        }

    today_cen = latest_day(ho_history)
    today_gvs = latest_day(gvs_history)
    today_edn = latest_day(edn_history)
    store_today = {"CEN": today_cen, "GVS": today_gvs, "EDN": today_edn}

    latest_date_str = today_cen.get("date", "") or today_gvs.get("date", "") or today_edn.get("date", "")
    if latest_date_str:
        try:
            ld = datetime.strptime(latest_date_str, "%Y-%m-%d").date()
            if ld == NOW.date():
                latest_day_label = "Today"
            elif ld == (NOW - timedelta(days=1)).date():
                latest_day_label = "Yesterday"
            else:
                latest_day_label = ld.strftime("%d %b")
        except:
            latest_day_label = "Latest"
    else:
        latest_day_label = "Latest"

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
    # WoW: compare last 7 trading days vs same 7 days a week prior
    # Only count days that have data in cache (non-zero total)
    def recent_trading_days(key, n=7):
        """Get n most recent days that have actual data"""
        vals = []
        i = 1
        while len(vals) < n and i < 60:
            d = (NOW - timedelta(days=i)).strftime("%Y-%m-%d")
            rev = days_data.get(d, {}).get(key, {}).get("revenue", 0)
            if rev > 0:
                vals.append((d, rev))
            i += 1
        return vals  # list of (date, revenue)

    def wow_from_trading_days(key, n=7):
        recent = recent_trading_days(key, n)
        if len(recent) < n: return None
        this_sum = sum(v for _, v in recent)
        # Get the same n days shifted back 7 calendar days
        prev_sum = 0
        count = 0
        for d, _ in recent:
            pd = (datetime.strptime(d, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
            prev_rev = days_data.get(pd, {}).get(key, {}).get("revenue", 0)
            if prev_rev > 0:
                prev_sum += prev_rev
                count += 1
        if count < 3: return None
        if prev_sum == 0: return None
        return (this_sum - prev_sum) / prev_sum * 100

    wow = {
        "CEN": wow_from_trading_days("CEN"),
        "GVS": wow_from_trading_days("GVS"),
        "EDN": wow_from_trading_days("EDN"),
    }
    overall_wow_this = sum(sum(v for _,v in recent_trading_days(k, 7)) for k in ["CEN","GVS","EDN"])
    overall_wow = None  # recalculate below as aggregate
    try:
        recent_cen = recent_trading_days("CEN", 7)
        recent_gvs = recent_trading_days("GVS", 7)
        recent_edn = recent_trading_days("EDN", 7)
        this_w = sum(v for _,v in recent_cen) + sum(v for _,v in recent_gvs) + sum(v for _,v in recent_edn)
        prev_w = 0; cnt = 0
        for key, recent in [("CEN",recent_cen),("GVS",recent_gvs),("EDN",recent_edn)]:
            for d, _ in recent:
                pd = (datetime.strptime(d, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
                pv = days_data.get(pd, {}).get(key, {}).get("revenue", 0)
                if pv > 0:
                    prev_w += pv; cnt += 1
        if cnt >= 5 and prev_w > 0:
            overall_wow = (this_w - prev_w) / prev_w * 100
    except: pass

    cen_prev = [days_data.get((NOW - timedelta(days=i+8)).strftime("%Y-%m-%d"), {}).get("CEN", {}).get("revenue", 0) for i in range(6, -1, -1)]
    gvs_prev = [days_data.get((NOW - timedelta(days=i+8)).strftime("%Y-%m-%d"), {}).get("GVS", {}).get("revenue", 0) for i in range(6, -1, -1)]
    edn_prev = [days_data.get((NOW - timedelta(days=i+8)).strftime("%Y-%m-%d"), {}).get("EDN", {}).get("revenue", 0) for i in range(6, -1, -1)]



    # Monthly totals — Omni histories for current month, daily cache for older
    monthly = {}
    for offset in range(3):
        year_i, month_i = shift_year_month(report_year, report_month_num, -offset)
        ym = f"{year_i}-{month_i:02d}"
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
                        if dd.year == year_i and dd.month == month_i:
                            for s in totals:
                                totals[s] += d_val.get(s, {}).get("revenue", 0)
                    except: pass
            # Check completeness
            month_days = calendar.monthrange(year_i, month_i)[1]
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
        # Exclude courier/postage fees — not real products
        desc_lower = desc.lower()
        if any(x in desc_lower for x in ["postgeld", "courier", "postage", "shipping fee", "delivery fee"]): continue
        pbs[desc][b]["rev"] += r.get("value_excl_after_discount", 0)
        pbs[desc][b]["gp"] += r.get("gross_profit", 0)
        pbs[desc][b]["qty"] += r.get("quantity", 0)
        pbs[desc][b]["sup"] = r.get("supplier_#", "")

    # Cross-store gaps (V8): bidirectional, using the strongest source store instead of CEN-only logic
    gaps = []
    for prod, stores in pbs.items():
        ranked_sources = []
        for store_code in ["CEN", "GVS", "EDN"]:
            sd = stores.get(store_code, {"rev": 0, "qty": 0, "gp": 0, "sup": ""})
            if sd["rev"] <= 0 and sd["qty"] <= 0:
                continue
            gp_pct = (sd["gp"] / sd["rev"] * 100) if sd["rev"] > 0 else 0
            ranked_sources.append({
                "store": store_code,
                "rev": sd["rev"],
                "qty": sd["qty"],
                "gp": sd["gp"],
                "gp_pct": gp_pct,
                "sup": sd["sup"],
            })

        if not ranked_sources:
            continue

        ranked_sources.sort(key=lambda x: (x["rev"], x["qty"], x["gp"]), reverse=True)
        best = ranked_sources[0]
        if best["rev"] < 5000 and best["qty"] < 20:
            continue

        missing = []
        for target_store in ["CEN", "GVS", "EDN"]:
            if target_store == best["store"]:
                continue
            target_data = stores.get(target_store, {"rev": 0, "qty": 0})
            if target_data.get("rev", 0) < 100:
                missing.append(target_store)

        if missing:
            per_store_uplift = best["rev"] * 0.4
            gaps.append({
                "p": prod,
                "rev": best["rev"],
                "qty": best["qty"],
                "gp": best["gp"],
                "gp_pct": best["gp_pct"],
                "sup": best["sup"],
                "m": missing,
                "source": best["store"],
                "uplift_per_store": per_store_uplift,
                "uplift_total": per_store_uplift * len(missing),
            })
    gaps.sort(key=lambda x: x["uplift_total"], reverse=True)

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
                cands.append({"p": prod, "rev": this, "sup": stores.get(store, {}).get("sup", "")})
        cands.sort(key=lambda x: x["rev"], reverse=True)
        unique[store] = cands[:5]


    # Hidden gems: high GP% + low units = visibility problem
    hidden_gems = []
    for prod, stores in pbs.items():
        for sc, sd in stores.items():
            if sd["rev"] < 800: continue
            gp_p = (sd["gp"] / sd["rev"] * 100) if sd["rev"] > 0 else 0
            if gp_p >= 40 and sd["qty"] <= 12:
                hidden_gems.append({
                    "p": prod, "store": sc, "gp_pct": gp_p,
                    "qty": sd["qty"], "rev": sd["rev"],
                    "potential": sd["rev"] * 3, "sup": sd["sup"]
                })
    hidden_gems.sort(key=lambda x: x["gp_pct"], reverse=True)

    # Low GP action card candidates
    low_gp_items = []
    for prod, stores_d in pbs.items():
        total_rev = sum(sd.get("rev",0) for sd in stores_d.values())
        total_gp_val = sum(sd.get("gp",0) for sd in stores_d.values())
        total_qty = sum(sd.get("qty",0) for sd in stores_d.values())
        if total_rev < 5000: continue
        gp_p = (total_gp_val / total_rev * 100) if total_rev > 0 else 0
        if gp_p < 20:
            uplift = total_rev * 0.35 - total_gp_val
            sup = list(stores_d.values())[0].get("sup","")
            low_gp_items.append({
                "p": prod, "rev": total_rev, "gp_pct": gp_p,
                "gp_val": total_gp_val, "qty": total_qty,
                "uplift_est": uplift, "sup": sup
            })
    low_gp_items.sort(key=lambda x: x["uplift_est"], reverse=True)

    # Supplier concentration
    top1_name = sup_name(sup_sorted[0][0], sup_names) if sup_sorted else "?"
    top1_pct = (sup_sorted[0][1]["rev"] / total_rev_all * 100) if sup_sorted and total_rev_all > 0 else 0

    # === SOURCE HEALTH + PRIORITY ACTIONS (V8) ===
    omni_updated = parse_isoish_datetime(omni.get("last_updated"))
    omni_days_old = (NOW.date() - omni_updated.date()).days if omni_updated else 99
    omni_cls, omni_status = freshness_class(omni_days_old, ok_days=0, warn_days=1)

    histories_days_old = max(0, NOW.day - days_elapsed)
    hist_cls, hist_status = freshness_class(histories_days_old, ok_days=0, warn_days=1)

    reviews_latest_date = parse_doc_date(reviews.get("latest", {}).get("date"))
    reviews_days_old = (NOW.date() - reviews_latest_date).days if reviews_latest_date else 99
    reviews_cls, reviews_status = freshness_class(reviews_days_old, ok_days=1, warn_days=3)

    source_health = [
        {
            "label": "Omni Cache",
            "status": omni_status,
            "cls": omni_cls,
            "note": omni_updated.strftime("%d %b %H:%M") if omni_updated else "No timestamp",
        },
        {
            "label": "Sales Histories",
            "status": hist_status,
            "cls": hist_cls,
            "note": f"Latest trade day: {days_elapsed}/{days_in_month_total}",
        },
        {
            "label": "GA4",
            "status": "Live" if ga4 else "Unavailable",
            "cls": "good" if ga4 else "bad",
            "note": "Last 28 days vs prior 28 days",
        },
        {
            "label": "Search Console",
            "status": "Live" if gsc else "Unavailable",
            "cls": "warn" if gsc else "bad",
            "note": "Google data naturally lags ~2 days",
        },
        {
            "label": "Google Reviews",
            "status": reviews_status,
            "cls": reviews_cls,
            "note": reviews.get("latest", {}).get("date", "No snapshot"),
        },
    ]

    action_candidates = []

    pace_priority_stores = sorted(
        [s for s in ["CEN", "GVS", "EDN"] if store_analysis[s]["pct"] < 100],
        key=lambda s: store_analysis[s]["pct"],
    )
    for store_code in pace_priority_stores[:2]:
        sa = store_analysis[store_code]
        raw_impact = max(sa["required_daily"] * min(sa["remaining_trading"], 7), 0)
        confidence = 88 if sa["pct"] < 90 else 76
        urgency = 95 if sa["pct"] < 85 else (82 if sa["pct"] < 95 else 65)
        effort = 84
        feasibility = 85
        action_candidates.append({
            "kind": "store",
            "title": f"Lift {STORE_LABELS[store_code]} pace vs target",
            "summary": f"Running at {sa['pct']:.0f}% of target. Current pace {fmt_r(sa['run_rate'])}/day vs required {fmt_r(sa['required_daily'])}/day.",
            "owner": f"{STORE_LABELS[store_code]} manager",
            "impact_value": raw_impact,
            "impact_label": f"Close ~{fmt_r(raw_impact)} of the shortfall in 7 days",
            "confidence": confidence,
            "urgency": urgency,
            "effort": effort,
            "feasibility": feasibility,
            "badge": "Store pace",
            "badge_cls": "urgent",
        })

    for g in gaps[:10]:
        confidence = 82 if g["qty"] >= 20 else 68
        urgency = 74 if g["gp_pct"] >= 35 else 62
        effort = 72
        feasibility = clamp(45 + g["qty"] * 2, 45, 90)
        action_candidates.append({
            "kind": "range",
            "title": f"Range {g['p']} from {STORE_LABELS.get(g['source'], g['source'])} into {', '.join(STORE_LABELS.get(m, m) for m in g['m'])}",
            "supplier": sup_name(g.get("sup", ""), sup_names),
            "summary": f"Best source store is {STORE_LABELS.get(g['source'], g['source'])}: {fmt_r(g['rev'])} revenue, {g['qty']} units, {g['gp_pct']:.0f}% GP.",
            "owner": "Ops / buying",
            "impact_value": g["uplift_total"],
            "impact_label": f"Potential +{fmt_r(g['uplift_total'])}/month across missing stores",
            "confidence": confidence,
            "urgency": urgency,
            "effort": effort,
            "feasibility": feasibility,
            "badge": "Range gap",
            "badge_cls": "opportunity",
        })

    for gem in hidden_gems[:8]:
        impact_value = max(gem["potential"] - gem["rev"], gem["rev"] * 1.5)
        action_candidates.append({
            "kind": "gem",
            "title": f"Move hidden gem: {gem['p']}",
            "supplier": sup_name(gem.get("sup", ""), sup_names),
            "summary": f"{STORE_LABELS.get(gem['store'], gem['store'])}: {gem['gp_pct']:.0f}% GP but only {gem['qty']} units sold.",
            "owner": f"{STORE_LABELS.get(gem['store'], gem['store'])} floor team",
            "impact_value": impact_value,
            "impact_label": f"Upside to ~{fmt_r(gem['potential'])}/month if visibility improves",
            "confidence": 66,
            "urgency": 58,
            "effort": 92,
            "feasibility": 64,
            "badge": "Hidden gem",
            "badge_cls": "margin",
        })

    for item in low_gp_items[:8]:
        action_candidates.append({
            "kind": "margin",
            "title": f"Fix low-GP drag: {item['p']}",
            "supplier": sup_name(item.get("sup", ""), sup_names),
            "summary": f"Only {item['gp_pct']:.0f}% GP on {fmt_r(item['rev'])} revenue. Buying or pricing change needed.",
            "owner": "Buying / Naadir",
            "impact_value": item["uplift_est"],
            "impact_label": f"Est. +{fmt_r(item['uplift_est'])}/month GP uplift",
            "confidence": 61,
            "urgency": 57,
            "effort": 46,
            "feasibility": 55,
            "badge": "Margin leak",
            "badge_cls": "margin",
        })

    max_impact = max((a["impact_value"] for a in action_candidates), default=1)
    for action in action_candidates:
        impact_score = clamp((action["impact_value"] / max_impact) * 100)
        action["impact_score"] = impact_score
        action["score"] = round(
            impact_score * 0.35
            + action["confidence"] * 0.25
            + action["urgency"] * 0.20
            + action["effort"] * 0.10
            + action["feasibility"] * 0.10,
            1,
        )
        action["score_label"] = score_label(action["score"])

    priority_actions = sorted(action_candidates, key=lambda a: (a["score"], a["impact_value"]), reverse=True)[:5]
    top_action = priority_actions[0] if priority_actions else None

    # === TODAY'S STORY + DAILY ACTION (V8) ===
    F = fmt_r_narrative

    pct_target = combined_projected / total_target * 100 if total_target > 0 else 0

    if days_remaining == 0:
        if pct_target >= 100:
            lead = f"{report_month_label} closed ahead of target at {F(combined_projected)} versus a {F(total_target)} target ({pct_target:.0f}%)."
        else:
            lead = f"{report_month_label} closed below target at {F(combined_projected)} versus a {F(total_target)} target ({pct_target:.0f}%), leaving a final shortfall of {F(total_target - combined_projected)}."
    else:
        if pct_target >= 100:
            lead = f"{report_month_label} is running ahead of target, projected {F(combined_projected)} against a {F(total_target)} month target ({pct_target:.0f}%)."
        elif pct_target >= 90:
            lead = f"{report_month_label} is close but not safe yet: projected {F(combined_projected)} vs {F(total_target)} target ({pct_target:.0f}%), with a {F(total_target - combined_projected)} gap still open."
        else:
            lead = f"{report_month_label} is under pressure: projected {F(combined_projected)} vs {F(total_target)} target ({pct_target:.0f}%), leaving a {F(total_target - combined_projected)} shortfall that needs action now."

    story_parts = [{"text": lead, "cls": "lead"}]
    if report_month != NOW.strftime("%Y-%m"):
        story_parts.append({"text": f"Using the latest full trade month with real sales posted: {report_month_label}. Current calendar month has not populated yet.", "cls": ""})

    if top_action:
        story_parts.append({
            "text": f"Top priority right now: {top_action['title']} ({top_action['score_label']} score, {top_action['impact_label'].lower()}). Owner: {top_action['owner']}.",
            "cls": "opp-sentence" if top_action["badge_cls"] != "urgent" else "alert-sentence",
        })

    for s in ["CEN", "GVS", "EDN"]:
        sa = store_analysis[s]
        label = STORE_LABELS[s]
        w_pct = wow.get(s)
        w_str = ""
        if w_pct is not None:
            w_str = f", {'up' if w_pct >= 0 else 'down'} {abs(w_pct):.0f}% WoW"
        if sa["remaining_trading"] == 0:
            gap_text = "ahead of target" if sa["gap"] <= 0 else f"short by {F(sa['gap'])}"
            txt = f"{label} closed at {sa['pct']:.0f}% of target, {gap_text}{w_str}."
            cls = "" if sa["gap"] <= 0 else "alert-sentence"
        elif sa["pct"] >= 100:
            txt = f"{label} is the standout at {F(store_mtd[s]['rev'])} MTD, running {F(sa['run_rate'])}/day{w_str}."
            cls = ""
        elif sa["pct"] >= 85:
            txt = f"{label} is workable at {sa['pct']:.0f}% trajectory{w_str}, but still needs {F(sa['required_daily'])}/day to close the gap."
            cls = ""
        else:
            txt = f"{label} is the concern at {sa['pct']:.0f}% trajectory{w_str}. Current pace is {F(sa['run_rate'])}/day, required pace is {F(sa['required_daily'])}/day."
            cls = "alert-sentence"
        story_parts.append({"text": txt, "cls": cls})

    if mtd_gp_pct < 33:
        story_parts.append({"text": f"Blended GP is {mtd_gp_pct:.1f}%, below the 33.8% benchmark. Margin leakage needs active intervention.", "cls": "alert-sentence"})
    else:
        story_parts.append({"text": f"Blended GP is holding at {mtd_gp_pct:.1f}%, which is healthy enough to protect while chasing revenue.", "cls": ""})

    if gaps:
        tg = gaps[0]
        story_parts.append({"text": f"Best cross-store rollout: {esc(tg['p'])} wins at {STORE_LABELS.get(tg['source'], tg['source'])} and is missing from {', '.join(STORE_LABELS.get(m, m) for m in tg['m'])}, worth about {F(tg['uplift_total'])}/month if rolled out.", "cls": "opp-sentence"})

    if top1_pct > 25:
        story_parts.append({"text": f"Supplier concentration risk remains high: {esc(top1_name)} contributes {top1_pct:.0f}% of total revenue.", "cls": "alert-sentence"})

    if top_action:
        da_text = f"{top_action['title']} — {top_action['summary']} {top_action['impact_label']}. Owner: {top_action['owner']}."
        da_type = top_action["badge_cls"]
        da_icon = "&#x1f6a8;" if da_type == "urgent" else ("&#x1f4e6;" if da_type == "opportunity" else "&#x1f4c8;")
    else:
        da_text = "No high-confidence action cards generated. Review source health and product data before acting."
        da_type = "margin"
        da_icon = "&#x1f50d;"

    narrative = lead  # keep for backward compat

    # Friendly summaries for long sections
    top_gap = gaps[0] if gaps else None
    total_gap_uplift_top10 = sum(g.get("uplift_total", 0) for g in gaps[:10])
    multi_store_gap_count = sum(1 for g in gaps if len(g.get("m", [])) > 1)
    supplier_leader_code, supplier_leader = sup_sorted[0] if sup_sorted else ("", {"rev": 0, "gp_pct": 0, "abc": "-"})
    supplier_low_gp_count = sum(1 for _, data in sup_sorted[:30] if data.get("gp_pct", 0) < 30)
    low_gp_exposure = sum(item.get("rev", 0) for item in low_gp_items[:10])

    search_quick_wins = []
    search_big_opps = []
    if gsc:
        search_quick_wins = [q for q in gsc["non_branded"] if 3 < q["pos"] <= 10 and q["impr"] > 80]
        search_big_opps = [q for q in gsc["non_branded"] if q["pos"] > 10 and q["impr"] > 200]

    review_deltas = []
    if reviews:
        rv_latest = reviews["latest"]
        rv_start = reviews["week_start"]
        for c in ["CEN", "GVS", "EDN"]:
            total_now = rv_latest["stores"].get(c, {}).get("total_reviews", 0)
            total_start = rv_start["stores"].get(c, {}).get("total_reviews", 0)
            target = reviews["targets"].get(c, 0)
            review_deltas.append({
                "store": c,
                "new": total_now - total_start,
                "target": target,
                "gap": (total_now - total_start) - target,
            })
    review_best = max(review_deltas, key=lambda x: x["new"] - x["target"]) if review_deltas else None
    review_laggard = min(review_deltas, key=lambda x: x["new"] - x["target"]) if review_deltas else None

    # === BUILD HTML ===
    lines = []
    w = lines.append

    w('<!DOCTYPE html>')
    w('<html lang="en"><head>')
    w('<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">')
    w(f'<title>Onelife Intelligence | {'V8 Live' if args.live else 'V8 Preview'}</title>')
    w('<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">')
    w('<style>')
    w("""
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:'Inter',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
.container{max-width:1400px;margin:0 auto;padding:20px}
header{text-align:center;padding:30px 0 20px}
header h1{font-size:28px;font-weight:800;color:#f8fafc}
header h1 span{color:#22c55e}
header .sub{color:#94a3b8;font-size:14px;margin-top:4px}
header .date{color:#64748b;font-size:12px;margin-top:2px}

.topnav{position:sticky;top:0;z-index:30;display:flex;flex-wrap:wrap;gap:8px;justify-content:center;padding:12px;margin:0 0 18px;background:rgba(15,23,42,.92);backdrop-filter:blur(10px);border:1px solid #334155;border-radius:14px}
.jump-btn{display:inline-flex;align-items:center;gap:6px;padding:9px 12px;border-radius:999px;background:#111827;border:1px solid #334155;color:#cbd5e1;text-decoration:none;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
.jump-btn:hover{background:#1e293b;border-color:#22c55e;color:#f8fafc}
.section-anchor{scroll-margin-top:88px}

.mini-strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:14px}
.mini-card{background:#111827;border:1px solid #334155;border-radius:10px;padding:12px}
.mini-card .k{color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-bottom:5px}
.mini-card .v{color:#f8fafc;font-size:18px;font-weight:800}
.mini-card .n{color:#64748b;font-size:11px;line-height:1.45;margin-top:3px}

.collapse{margin-top:14px;border:1px solid #334155;border-radius:10px;background:#111827;overflow:hidden}
.collapse summary{cursor:pointer;list-style:none;padding:13px 16px;font-size:12px;font-weight:700;color:#cbd5e1;background:#0f172a}
.collapse summary::-webkit-details-marker{display:none}
.collapse[open] summary{border-bottom:1px solid #334155}
.collapse .collapse-body{padding:0 0 4px}

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
.uitem{padding:7px 0;border-bottom:1px solid #334155;font-size:12px;display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.uitem-main{display:flex;flex-direction:column;gap:2px;min-width:0}
.uitem-name{color:#e2e8f0}
.uitem-supplier{color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:.04em}
.uitem .num{color:#22c55e;white-space:nowrap}
.dim{color:#475569}

.mgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;text-align:center}
.mcard{background:#0f172a;border-radius:8px;padding:14px}
.mcard .mo{color:#94a3b8;font-size:11px;font-weight:600}
.mcard .tot{font-size:20px;font-weight:800;color:#f8fafc;margin:6px 0}
.mcard .bd{font-size:11px;color:#64748b}
.mcard .incomplete{color:#f59e0b;font-size:10px;font-style:italic;margin-top:4px}

.data-warning{background:#1e293b;border:1px solid #f59e0b;border-radius:8px;padding:12px;margin-bottom:16px;font-size:12px;color:#fbbf24;display:flex;align-items:center;gap:8px}
.data-warning .icon{font-size:16px}

.source-strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:20px}
.source-card{background:#111827;border:1px solid #334155;border-radius:12px;padding:14px 16px}
.source-card.good{border-left:4px solid #22c55e}.source-card.warn{border-left:4px solid #f59e0b}.source-card.bad{border-left:4px solid #ef4444}
.source-card .label{color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}
.source-card .status{font-size:18px;font-weight:800;color:#f8fafc;margin-bottom:4px}
.source-card.good .status{color:#22c55e}.source-card.warn .status{color:#f59e0b}.source-card.bad .status{color:#ef4444}
.source-card .note{font-size:11px;color:#64748b;line-height:1.45}

/* Today's Story */
.story-card{background:linear-gradient(135deg,#142314,#0f1e10);border:1px solid #22c55e33;border-left:4px solid #22c55e;border-radius:14px;padding:18px;margin-bottom:16px}
.story-header{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.story-title{color:#22c55e;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.story-date{color:#64748b;font-size:10px;margin-left:auto}
.story-sentences{display:flex;flex-direction:column;gap:7px}
.story-sentence{color:#cbd5e1;font-size:13px;line-height:1.65;padding:6px 12px;border-left:3px solid #1e3a2e;border-radius:0 6px 6px 0}
.story-sentence.lead{color:#e2e8f0;font-size:14px;font-weight:500;border-left-color:#22c55e;background:#22c55e0a}
.story-sentence.alert-sentence{border-left-color:#ef4444;color:#fca5a5;background:#ef44440a}
.story-sentence.opp-sentence{border-left-color:#f59e0b;color:#fde68a;background:#f59e0b0a}

/* Daily Action */
.daily-action{border-radius:14px;padding:16px 18px;margin-bottom:16px;display:flex;align-items:flex-start;gap:14px}
.daily-action.urgent{background:linear-gradient(135deg,#2d1515,#1c0d0d);border:1px solid #ef444444;border-left:4px solid #ef4444}
.daily-action.opportunity{background:linear-gradient(135deg,#0e1e3a,#091525);border:1px solid #3b82f644;border-left:4px solid #3b82f6}
.daily-action.margin{background:linear-gradient(135deg,#1e1a0a,#150f05);border:1px solid #f59e0b44;border-left:4px solid #f59e0b}
.da-icon{font-size:22px;flex-shrink:0;margin-top:1px}
.da-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px}
.urgent .da-label{color:#ef4444}.opportunity .da-label{color:#3b82f6}.margin .da-label{color:#f59e0b}
.da-text{color:#f1f5f9;font-size:14px;line-height:1.65;font-weight:500}

/* Priority actions */
.priority-list{display:flex;flex-direction:column;gap:12px}
.priority-item{background:#111827;border:1px solid #334155;border-radius:12px;padding:16px}
.priority-item.urgent{border-left:4px solid #ef4444}.priority-item.opportunity{border-left:4px solid #3b82f6}.priority-item.margin{border-left:4px solid #f59e0b}
.priority-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:8px}
.priority-title{font-size:14px;font-weight:700;color:#f8fafc;line-height:1.4}
.priority-supplier{font-size:10px;color:#94a3b8;font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-top:3px}
.priority-score{font-size:11px;font-weight:800;padding:5px 8px;border-radius:999px;background:#1e293b;color:#e2e8f0;white-space:nowrap}
.priority-meta{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 10px}
.meta-pill{font-size:10px;font-weight:700;padding:4px 7px;border-radius:999px;background:#1e293b;color:#cbd5e1;text-transform:uppercase;letter-spacing:.05em}
.priority-summary{font-size:12px;color:#cbd5e1;line-height:1.6;margin-bottom:6px}
.priority-impact{font-size:12px;color:#22c55e;font-weight:700}
.priority-owner{font-size:11px;color:#94a3b8;margin-top:6px}

/* Action Cards (low GP / hidden gems) */
.action-cards{display:flex;flex-direction:column;gap:10px}
.action-card{border-radius:10px;padding:14px 16px;border:1px solid #334155;background:#1a2535}
.action-card.swap{border-left:3px solid #ef4444}
.action-card.gem{border-left:3px solid #a855f7}
.action-card.range{border-left:3px solid #3b82f6}
.ac-badge{display:inline-block;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;padding:2px 7px;border-radius:4px;margin-bottom:6px}
.ac-badge.swap{background:#ef444422;color:#ef4444}.ac-badge.gem{background:#a855f722;color:#a855f7}.ac-badge.range{background:#3b82f622;color:#3b82f6}
.ac-title{color:#f1f5f9;font-size:13px;font-weight:600;line-height:1.5;margin-bottom:4px}
.ac-supplier{color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-top:-1px;margin-bottom:6px}
.ac-meta{color:#64748b;font-size:11px}
.ac-uplift{color:#22c55e;font-weight:700;font-size:12px;margin-top:4px}

/* WoW badge in store card */
.store-wow{text-align:right;margin-top:5px;font-size:11px}

footer{text-align:center;padding:24px 0;color:#475569;font-size:11px}
footer .lo{color:#22c55e}

@media(max-width:768px){
.kpi-strip{grid-template-columns:repeat(2,1fr)}
.ugrid,.mgrid,.store-grid{grid-template-columns:1fr}
.progress-row .spark{display:none}
div[style*="grid-template-columns:1fr 1fr"]{grid-template-columns:1fr!important}
}
""")
    w('</style></head><body><div class="container">')

    # Header
    w(f'<header><h1>Onelife <span>Intelligence</span></h1>')
    if args.live:
        w(f'<div class="sub">V8 | Hybrid owner + operator cockpit | Reporting month: {report_month_label}</div>')
    else:
        w(f'<div class="sub">V8 Preview | Hybrid owner + operator cockpit | Reporting month: {report_month_label} | V7 remains live as backup</div>')
    last_updated = omni.get("last_updated", "unknown")[:16].replace("T", " ")
    w(f'<div class="date">{NOW.strftime("%d %B %Y")} | Data as at {last_updated}</div>')
    w('</header>')
    w('<div class="topnav">')
    w('<a class="jump-btn" href="#overview">Overview</a>')
    w('<a class="jump-btn" href="#stores">Stores</a>')
    w('<a class="jump-btn" href="#online">Online</a>')
    w('<a class="jump-btn" href="#opportunities">Opportunities</a>')
    w('<a class="jump-btn" href="#search">Search</a>')
    w('<a class="jump-btn" href="#reviews">Reviews</a>')
    w('<a class="jump-btn" href="#trends">Trends</a>')
    w('</div>')

    # Data health warning if Omni API is down
    fetch_status = omni.get("fetch_status", "")
    if "error" in str(fetch_status).lower() or "Version" in str(fetch_status):
        w('<div class="data-warning"><span class="icon">&#x26a0;</span> Omni API may be down. Using cached data. Numbers may not reflect today\'s full trading.</div>')

    # === SOURCE HEALTH ===
    w('<div id="overview" class="section-anchor"></div>')
    w('<div class="card"><h3>&#x1f9ec; Data Source Health</h3><div class="desc">Know what to trust before acting. Freshness is shown per source.</div>')
    w('<div class="source-strip">')
    for src in source_health:
        w(f'<div class="source-card {src["cls"]}">')
        w(f'<div class="label">{esc(src["label"])}</div>')
        w(f'<div class="status">{esc(src["status"])}</div>')
        w(f'<div class="note">{esc(src["note"])}</div>')
        w('</div>')
    w('</div></div>')

    # === TODAY'S STORY CARD ===
    w('<div class="story-card">')
    w(f'<div class="story-header"><span style="font-size:18px">&#x1f9e0;</span><span class="story-title">Today\'s Story</span><span class="story-date">{NOW.strftime("%d %B %Y")}</span></div>')
    w('<div class="story-sentences">')
    for sp in story_parts:
        cls_attr = f' {sp["cls"]}' if sp.get("cls") else ""
        w(f'<div class="story-sentence{cls_attr}">{esc(sp["text"])}</div>')
    w('</div></div>')

    # === DAILY ACTION CARD ===
    w(f'<div class="daily-action {da_type}">')
    w(f'<div class="da-icon">{da_icon}</div>')
    w('<div class="da-body">')
    w(f'<div class="da-label">&#x2605; Daily Action</div>')
    w(f'<div class="da-text">{esc(da_text)}</div>')
    w('</div></div>')

    # === TOP 5 PRIORITY ACTIONS ===
    w('<div class="card"><h3>&#x1f3af; Top 5 Priority Actions</h3><div class="desc">Weighted ranking = impact + confidence + urgency + effort + feasibility. Built for decision-making, not just reporting.</div>')
    if priority_actions:
        w('<div class="priority-list">')
        for idx, action in enumerate(priority_actions, start=1):
            w(f'<div class="priority-item {action["badge_cls"]}">')
            w('<div class="priority-head">')
            w('<div>')
            w(f'<div class="priority-title">#{idx} {esc(action["title"])}</div>')
            if action.get("supplier"):
                w(f'<div class="priority-supplier">Supplier: {esc(action["supplier"])}</div>')
            w('</div>')
            w(f'<div class="priority-score">{action["score"]:.0f}/100 · {esc(action["score_label"])}</div>')
            w('</div>')
            w('<div class="priority-meta">')
            w(f'<span class="meta-pill">{esc(action["badge"])}</span>')
            w(f'<span class="meta-pill">Confidence {action["confidence"]:.0f}</span>')
            w(f'<span class="meta-pill">Urgency {action["urgency"]:.0f}</span>')
            w(f'<span class="meta-pill">Effort {action["effort"]:.0f}</span>')
            w('</div>')
            w(f'<div class="priority-summary">{esc(action["summary"])}</div>')
            w(f'<div class="priority-impact">{esc(action["impact_label"])}</div>')
            w(f'<div class="priority-owner">Owner: {esc(action["owner"])}</div>')
            w('</div>')
        w('</div>')
    else:
        w('<div class="desc">No ranked actions generated from the current data. Check data freshness and thresholds.</div>')
    w('</div>')

    # KPI Strip
    w('<div id="stores" class="section-anchor"></div>')
    proj_class = "green" if combined_projected >= total_target * 0.95 else ("yellow" if combined_projected >= total_target * 0.80 else "red")
    w('<div class="kpi-strip">')
    w(f'<div class="kpi"><div class="label">MTD Revenue</div><div class="val">{fmt_r(mtd_rev)}</div><div class="note">Day {days_elapsed} of {days_in_month_total}</div><div class="wow">WoW: {trend_badge(overall_wow)}</div></div>')
    w(f'<div class="kpi"><div class="label">MTD Gross Profit</div><div class="val green">{fmt_r(mtd_gp)}</div><div class="note">{mtd_gp_pct:.1f}% blended GP</div></div>')
    w(f'<div class="kpi"><div class="label">Daily Run Rate</div><div class="val blue">{fmt_r(combined_daily_avg)}</div><div class="note">Yesterday: {fmt_r(yesterday_rev)}</div></div>')
    w(f'<div class="kpi"><div class="label">Projected Month</div><div class="val {proj_class}">{fmt_r(combined_projected)}</div><div class="note">Target: {fmt_r(total_target)}</div></div>')
    w('</div>')

    # === STORE DETAIL CARDS (NEW: per-store revenue, run rate, required rate, GP) ===
    w('<div class="store-grid">')
    for s in ["CEN", "GVS", "EDN"]:
        sa = store_analysis[s]
        data = store_mtd[s]
        cls = "ok" if sa["actual_pct"] >= 95 else ("warn" if sa["actual_pct"] >= 80 else "bad")
        status_cls = "highlight" if sa["pct"] >= 95 else ("alert" if sa["pct"] < 80 else "")

        w(f'<div class="store-card">')
        w(f'<div class="sname">{STORE_LABELS[s]}</div>')
        w(f'<div class="srev">{fmt_r(data["rev"])}</div>')
        w(f'<div class="bar-mini"><div class="bar-fill {cls}" style="width:{min(sa["actual_pct"],100):.0f}%"></div></div>')
        w(f'<div class="spct">{sa["actual_pct"]:.0f}% of {fmt_r(TARGETS[s])} target</div>')
        td = store_today[s]
        td_gp_pct = (td["gp"] / td["rev"] * 100) if td["rev"] > 0 else 0
        w(f'<div class="srow" style="border-bottom:1px solid #1e1e2e;padding-bottom:6px;margin-bottom:6px"><span style="color:#00ff88;font-weight:700">{latest_day_label} Sales</span><span class="sv" style="color:#00ff88;font-weight:700">{fmt_r(td["rev"])}</span></div>')
        w(f'<div class="srow"><span style="color:#00ff88">{latest_day_label} GP</span><span class="sv" style="color:#00ff88">{fmt_r(td["gp"])} ({td_gp_pct:.0f}%)</span></div>')
        w(f'<div class="srow"><span>Run Rate</span><span class="sv">{fmt_r(sa["run_rate"])}/day</span></div>')
        w(f'<div class="srow"><span>Required Rate</span><span class="sv {status_cls}">{fmt_r(sa["required_daily"])}/day</span></div>')
        w(f'<div class="srow"><span>Projected</span><span class="sv">{fmt_r(sa["projected"])}</span></div>')
        w(f'<div class="srow"><span>GP Margin</span><span class="sv">{sa["gp_pct"]:.1f}%</span></div>')
        w(f'<div class="srow"><span>Trading Days</span><span class="sv">{sa["trading_days"]} done, {sa["remaining_trading"]} left</span></div>')
        w(f'<div class="store-wow">WoW: {trend_badge(wow.get(s))}</div>')
        w(f'</div>')
    w('</div>')

    # Store Progress Bars (kept for visual overview)
    w('<div class="card"><h3>Store Tracking vs Target</h3><div class="desc">Actual month-to-date sales vs monthly target</div>')
    for s in ["CEN","GVS","EDN"]:
        sa = store_analysis[s]
        cls = "ok" if sa["actual_pct"]>=95 else ("warn" if sa["actual_pct"]>=80 else "bad")
        spark = sparkline_svg({"CEN":cen_week,"GVS":gvs_week,"EDN":edn_week}[s])
        w(f'<div class="progress-row"><div class="sn">{s}</div>')
        w(f'<div class="bar-wrap"><div class="bar {cls}" style="width:{min(sa["actual_pct"],100):.0f}%">{sa["actual_pct"]:.0f}%</div></div>')
        w(f'<div class="spark">{spark}</div>')
        w(f'<div class="tgt">{fmt_r(store_mtd[s]["rev"])} / {fmt_r(TARGETS[s])} {trend_badge(wow.get(s))}</div></div>')
    w('</div>')

    # === ONLINE PERFORMANCE (GA4) ===
    if ga4:
        w('<div id="online" class="section-anchor"></div>')
        t = ga4["totals"]
        chg = ga4["changes"]
        eng = ga4["engagement"]

        w('<div class="card"><h3>&#x1f310; Online Performance</h3>')
        w('<div class="desc">Google Analytics 4 — last 28 days vs prior 28 days | Powered by Analyzify tracking</div>')

        # Online KPIs
        sess_spark = sparkline_svg(ga4["daily_sessions"], "#3b82f6", 100, 25)
        rev_spark = sparkline_svg(ga4["daily_revenue"], "#22c55e", 100, 25)
        online_today_rev = ga4["daily_revenue"][-1] if ga4["daily_revenue"] else 0
        online_yesterday_rev = ga4["daily_revenue"][-2] if len(ga4["daily_revenue"]) >= 2 else 0

        w('<div class="kpi-strip" style="margin-bottom:14px">')
        w(f'<div class="kpi"><div class="label" style="color:#00ff88">Today Online Sales</div><div class="val" style="color:#00ff88;font-size:26px">{fmt_r(online_today_rev)}</div><div class="note">Yesterday: {fmt_r(online_yesterday_rev)}</div></div>')
        w(f'<div class="kpi"><div class="label">Sessions (28d)</div><div class="val">{t["sessions"]:,}</div><div class="note">{trend_badge(chg["sessions"])} {sess_spark}</div></div>')
        w(f'<div class="kpi"><div class="label">Revenue (28d)</div><div class="val green">{fmt_r(t["revenue"])}</div><div class="note">{trend_badge(chg["revenue"])} {rev_spark}</div></div>')
        w(f'<div class="kpi"><div class="label">Orders</div><div class="val">{t["orders"]}</div><div class="note">{trend_badge(chg["orders"])}</div></div>')
        w(f'<div class="kpi"><div class="label">Conv. Rate</div><div class="val">{t["conv"]:.2f}%</div><div class="note">Bounce: {eng["bounce"]:.0f}% | {eng["pages_per_session"]:.1f} pg/sess</div></div>')
        w('</div>')

        # Channel performance table
        w('<h4 style="color:#f1f5f9;font-size:12px;margin-bottom:6px">Channel Performance</h4>')
        w('<table style="font-size:11px"><thead><tr><th>Channel</th><th class="num">Sessions</th><th class="num">Revenue</th><th class="num">Orders</th><th class="num">Conv%</th><th class="num">Rev/Session</th><th>Verdict</th></tr></thead><tbody>')
        for ch in ga4["channels"]:
            # Verdict logic
            if ch["orders"] == 0 and ch["sessions"] > 200:
                verdict = '<span style="color:#ef4444">&#x26a0; No conversions</span>'
            elif ch["conv"] >= 0.5:
                verdict = '<span style="color:#22c55e">&#x2713; Strong</span>'
            elif ch["conv"] >= 0.15 and ch["rps"] >= 1.0:
                verdict = '<span style="color:#f59e0b">Okay</span>'
            elif ch["sessions"] > 500 and ch["conv"] < 0.15:
                verdict = '<span style="color:#ef4444">&#x26a0; High traffic, low conv</span>'
            else:
                verdict = '<span style="color:#64748b">Low volume</span>'
            conv_cls = "gph" if ch["conv"] >= 0.5 else ("gpm" if ch["conv"] >= 0.15 else "gpl")
            w(f'<tr><td>{esc(ch["name"])}</td><td class="num">{ch["sessions"]:,}</td><td class="num">{fmt_r(ch["revenue"])}</td><td class="num">{ch["orders"]}</td><td class="num {conv_cls}">{ch["conv"]:.2f}%</td><td class="num">R{ch["rps"]:.2f}</td><td>{verdict}</td></tr>')
        w('</tbody></table>')

        # Device breakdown inline
        w('<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px">')
        # Devices
        w('<div>')
        w('<h4 style="color:#f1f5f9;font-size:12px;margin-bottom:6px">&#x1f4f1; Device Split</h4>')
        w('<table style="font-size:11px"><thead><tr><th>Device</th><th class="num">Sessions</th><th class="num">Orders</th><th class="num">Revenue</th></tr></thead><tbody>')
        for d in ga4["devices"]:
            w(f'<tr><td>{d["device"].title()}</td><td class="num">{d["sessions"]:,}</td><td class="num">{d["orders"]}</td><td class="num">{fmt_r(d["revenue"])}</td></tr>')
        w('</tbody></table></div>')

        # Top revenue pages
        if ga4["top_pages"]:
            w('<div>')
            w('<h4 style="color:#f1f5f9;font-size:12px;margin-bottom:6px">&#x1f4b0; Top Revenue Pages</h4>')
            w('<table style="font-size:11px"><thead><tr><th>Page</th><th class="num">Revenue</th><th class="num">Orders</th></tr></thead><tbody>')
            for p in ga4["top_pages"][:6]:
                pg = p["page"][:45]
                if pg in ["/", "(not set)", ""]: pg = pg or "Homepage"
                w(f'<tr><td>{esc(pg)}</td><td class="num">{fmt_r(p["revenue"])}</td><td class="num">{p["orders"]}</td></tr>')
            w('</tbody></table></div>')
        w('</div>')

        # === ONLINE NARRATIVE ===
        w('<div class="story-card" style="margin-top:14px">')
        w('<div class="story-header"><span style="font-size:18px">&#x1f4ca;</span><span class="story-title">Online Intelligence &amp; Recommendations</span></div>')
        w('<div class="story-sentences">')

        # Overall trend
        if chg["revenue"] > 20:
            w(f'<div class="story-sentence lead">Online revenue up {chg["revenue"]:.0f}% — {fmt_r(t["revenue"])} from {t["orders"]} orders over 28 days. The growth trend is positive.</div>')
        elif chg["revenue"] > 0:
            w(f'<div class="story-sentence lead">Online revenue growing modestly at +{chg["revenue"]:.0f}% — {fmt_r(t["revenue"])} from {t["orders"]} orders.</div>')
        else:
            w(f'<div class="story-sentence alert-sentence">Online revenue down {abs(chg["revenue"]):.0f}% — {fmt_r(t["revenue"])} from {t["orders"]} orders. Investigate what changed.</div>')

        # Paid vs organic analysis
        paid = next((c for c in ga4["channels"] if c["name"] == "Paid Search"), None)
        organic = next((c for c in ga4["channels"] if c["name"] == "Organic Search"), None)
        if paid and organic:
            if organic["rps"] > paid["rps"]:
                ratio = organic["rps"] / paid["rps"] if paid["rps"] > 0 else 0
                w(f'<div class="story-sentence opp-sentence">Organic search converts {ratio:.1f}x better than paid search (R{organic["rps"]:.2f} vs R{paid["rps"]:.2f} per session). Every R1 invested in SEO/content works harder than R1 on Google Ads. Ask Digiwiz for ROAS breakdown.</div>')
            if paid["sessions"] > 10000 and paid["conv"] < 0.2:
                w(f'<div class="story-sentence alert-sentence">Paid Search is {paid["sessions"]:,} sessions but only {paid["conv"]:.2f}% converts. {paid["sessions"]-paid["orders"]:,} visitors leave without buying. Landing page or keyword targeting needs review.</div>')

        # Email performance
        email = next((c for c in ga4["channels"] if c["name"] == "Email"), None)
        if email and email["conv"] > 0.5:
            w(f'<div class="story-sentence">Email (Klaviyo) converts at {email["conv"]:.1f}% — your highest-quality channel at R{email["rps"]:.2f}/session. Grow the subscriber list; every new subscriber is worth ~R{email["rps"]:.0f} per visit.</div>')
        elif email:
            w(f'<div class="story-sentence">Email drives {email["sessions"]} sessions with {email["conv"]:.2f}% conversion. Room to grow — weekly sends, abandoned cart flows, and a bigger list would compound this.</div>')

        # Paid Social
        paid_social = next((c for c in ga4["channels"] if c["name"] == "Paid Social"), None)
        if paid_social and paid_social["sessions"] > 100 and paid_social["orders"] == 0:
            w(f'<div class="story-sentence alert-sentence">Paid Social (Meta/TikTok ads): {paid_social["sessions"]:,} sessions, ZERO conversions. This ad spend is producing awareness but no sales. Review targeting or pause until conversion tracking is fixed.</div>')

        # Cross-network
        cross = next((c for c in ga4["channels"] if c["name"] == "Cross-network"), None)
        if cross and cross["sessions"] > 200 and cross["orders"] == 0:
            w(f'<div class="story-sentence alert-sentence">Cross-network (Performance Max/display): {cross["sessions"]:,} sessions, zero sales. This traffic isn\'t buying. Consider reallocating budget to organic content or email.</div>')

        # Conversion rate benchmark
        if t["conv"] < 0.5:
            w(f'<div class="story-sentence">Overall conversion rate is {t["conv"]:.2f}% — below the 1-2% e-commerce benchmark. Priority: improve product pages, add reviews/social proof, simplify checkout. Every 0.1% improvement = ~{int(t["sessions"]*0.001/28*30)} extra orders/month.</div>')

        # Device insight
        mobile_d = next((d for d in ga4["devices"] if d["device"] == "mobile"), None)
        desktop_d = next((d for d in ga4["devices"] if d["device"] == "desktop"), None)
        if mobile_d and desktop_d and mobile_d["sessions"] > desktop_d["sessions"]:
            m_conv = (mobile_d["orders"]/mobile_d["sessions"]*100) if mobile_d["sessions"] > 0 else 0
            d_conv = (desktop_d["orders"]/desktop_d["sessions"]*100) if desktop_d["sessions"] > 0 else 0
            w(f'<div class="story-sentence">{mobile_d["sessions"]:,} mobile vs {desktop_d["sessions"]:,} desktop sessions. Mobile conversion: {m_conv:.2f}%, Desktop: {d_conv:.2f}%. {"Mobile experience needs work — most traffic but lower conversion." if m_conv < d_conv else "Mobile converting well."}</div>')

        w('</div></div>')
        w('</div>')

    # === HIDDEN GEMS SECTION ===
    w('<div id="opportunities" class="section-anchor"></div>')
    if hidden_gems:
        w('<div class="card"><h3>&#x1f48e; Hidden Gems</h3>')
        w('<div class="desc">High GP% products with low unit sales — shelf visibility problem. Move them and watch revenue climb.</div>')
        w('<div class="action-cards">')
        for gem in hidden_gems[:6]:
            w(f'<div class="action-card gem">')
            w(f'<span class="ac-badge gem">Hidden Gem</span>')
            w(f'<div class="ac-title">{esc(gem["p"])} @ {STORE_LABELS.get(gem["store"], gem["store"])}</div>')
            w(f'<div class="ac-supplier">Supplier: {esc(sup_name(gem.get("sup", ""), sup_names))}</div>')
            w(f'<div class="ac-meta">{gem["gp_pct"]:.0f}% GP &middot; only {gem["qty"]} units sold &middot; {fmt_r(gem["rev"])} revenue &middot; Supplier: {sup_name(gem.get("sup",""), sup_names)}</div>')
            w(f'<div class="ac-uplift">&#x27a4; Move to eye level or endcap. 3x sales potential = {fmt_r(gem["potential"])}/month</div>')
            w('</div>')
        w('</div></div>')

    # === LOW GP ACTION CARDS ===
    if low_gp_items:
        w('<div class="card"><h3>&#x26a0;&#xfe0f; Low GP Action Cards</h3>')
        w('<div class="desc">Products dragging your margin. Each card shows the swap opportunity and estimated monthly GP uplift.</div>')
        w('<div class="action-cards">')
        for item in low_gp_items[:5]:
            w(f'<div class="action-card swap">')
            w(f'<span class="ac-badge swap">Swap / Reprice</span>')
            w(f'<div class="ac-title">{esc(item["p"])}</div>')
            w(f'<div class="ac-supplier">Supplier: {esc(sup_name(item.get("sup", ""), sup_names))}</div>')
            w(f'<div class="ac-meta">{item["gp_pct"]:.0f}% GP &middot; {fmt_r(item["rev"])} revenue &middot; {item["qty"]} units &middot; Supplier: {sup_name(item["sup"], sup_names)}</div>')
            w(f'<div class="ac-uplift">&#x27a4; Replace with 35%+ GP equivalent &rarr; est. +{fmt_r(item["uplift_est"])}/month GP uplift</div>')
            w('</div>')
        w('</div></div>')

    # === CROSS-STORE RANGE ACTION CARDS ===
    w('<div class="card"><h3>&#x1f4e6; Cross-Store Range Opportunities</h3>')
    w(f'<div class="desc">Bidirectional range gaps. Products can now originate from any strong store, not just Centurion. {len(gaps)} opportunities — top 5 shown as action cards, full list below.</div>')
    w('<div class="mini-strip">')
    w(f'<div class="mini-card"><div class="k">Range gaps found</div><div class="v">{len(gaps)}</div><div class="n">{multi_store_gap_count} products are missing in 2 stores, not just 1.</div></div>')
    if top_gap:
        w(f'<div class="mini-card"><div class="k">Best rollout right now</div><div class="v">{fmt_r(top_gap["uplift_total"])} </div><div class="n">{esc(top_gap["p"])} from {STORE_LABELS.get(top_gap["source"], top_gap["source"])} into {", ".join(STORE_LABELS.get(m, m) for m in top_gap["m"])}.</div></div>')
    w(f'<div class="mini-card"><div class="k">Top 10 uplift pool</div><div class="v">{fmt_r(total_gap_uplift_top10)}</div><div class="n">Combined estimated monthly upside from the strongest 10 rollout ideas.</div></div>')
    w('</div>')
    w('<div class="action-cards" style="margin-bottom:16px">')
    for g in gaps[:5]:
        w(f'<div class="action-card range">')
        w(f'<span class="ac-badge range">Range It</span>')
        w(f'<div class="ac-title">{esc(g["p"])}</div>')
        w(f'<div class="ac-supplier">Supplier: {esc(sup_name(g.get("sup", ""), sup_names))}</div>')
        w(f'<div class="ac-meta">Source: {STORE_LABELS.get(g["source"], g["source"])} &middot; {g["gp_pct"]:.0f}% GP &middot; {fmt_r(g["rev"])} revenue &middot; {g["qty"]} units &middot; Supplier: {sup_name(g.get("sup",""), sup_names)} &middot; Missing: {", ".join(STORE_LABELS.get(m, m) for m in g["m"])}</div>')
        w(f'<div class="ac-uplift">&#x27a4; Stock at {", ".join(STORE_LABELS.get(m, m) for m in g["m"])} &rarr; potential {fmt_r(g["uplift_total"])} / month total uplift</div>')
        w('</div>')
    w('</div>')
    w('<details class="collapse"><summary>View detailed rollout table (top 25 products)</summary><div class="collapse-body">')
    w('<table><thead><tr><th>Product</th><th>Supplier</th><th>Source Store</th><th class="num">Source Revenue</th><th class="num">Source Units</th><th class="num">GP%</th><th>Missing At</th><th class="num">Est. Uplift</th></tr></thead><tbody>')
    for g in gaps[:25]:
        gpc = "gph" if g["gp_pct"]>=40 else ("gpm" if g["gp_pct"]>=30 else "gpl")
        w(f'<tr><td>{esc(g["p"])}</td><td>{esc(sup_name(g["sup"], sup_names))}</td><td>{STORE_LABELS.get(g["source"], g["source"])}</td><td class="num">{fmt_r(g["rev"])}</td><td class="num">{g["qty"]}</td><td class="num {gpc}">{g["gp_pct"]:.0f}%</td><td class="miss">{", ".join(STORE_LABELS.get(m, m) for m in g["m"])}</td><td class="num">{fmt_r(g["uplift_total"])}</td></tr>')
    w('</tbody></table></div></details></div>')

    # Supplier ABC Scorecard
    w('<div class="card"><h3>Supplier ABC Scorecard</h3>')
    w(f'<div class="desc">Top 30 suppliers by revenue. A = top 80% cumulative, B = next 15%, C = bottom 5%.</div>')
    w('<div class="mini-strip">')
    w(f'<div class="mini-card"><div class="k">Top supplier</div><div class="v">{esc(sup_name(supplier_leader_code, sup_names))}</div><div class="n">{fmt_r(supplier_leader.get("rev", 0))} revenue at {supplier_leader.get("gp_pct", 0):.1f}% GP.</div></div>')
    w(f'<div class="mini-card"><div class="k">Low-GP suppliers</div><div class="v">{supplier_low_gp_count}</div><div class="n">Suppliers in the top 30 currently below 30% GP.</div></div>')
    w(f'<div class="mini-card"><div class="k">Low-GP product exposure</div><div class="v">{fmt_r(low_gp_exposure)}</div><div class="n">Revenue flowing through the biggest low-margin product problems.</div></div>')
    w('</div>')
    w('<table><thead><tr><th>Class</th><th>Supplier</th><th class="num">Revenue</th><th class="num">GP%</th><th class="num">Units</th><th class="num">Products</th></tr></thead><tbody>')
    for code, data in sup_sorted[:10]:
        gpc = "gph" if data["gp_pct"]>=40 else ("gpm" if data["gp_pct"]>=30 else "gpl")
        ac = f'abc-{data["abc"].lower()}'
        w(f'<tr><td><span class="{ac}">{data["abc"]}</span></td><td>{sup_name(code, sup_names)}</td><td class="num">{fmt_r(data["rev"])}</td><td class="num {gpc}">{data["gp_pct"]:.1f}%</td><td class="num">{data["qty"]:,}</td><td class="num">{data["prods"]}</td></tr>')
    w('</tbody></table>')
    w('<details class="collapse"><summary>View full supplier table (top 30)</summary><div class="collapse-body"><table><thead><tr><th>Class</th><th>Supplier</th><th class="num">Revenue</th><th class="num">GP%</th><th class="num">Units</th><th class="num">Products</th></tr></thead><tbody>')
    for code, data in sup_sorted[:30]:
        gpc = "gph" if data["gp_pct"]>=40 else ("gpm" if data["gp_pct"]>=30 else "gpl")
        ac = f'abc-{data["abc"].lower()}'
        w(f'<tr><td><span class="{ac}">{data["abc"]}</span></td><td>{sup_name(code, sup_names)}</td><td class="num">{fmt_r(data["rev"])}</td><td class="num {gpc}">{data["gp_pct"]:.1f}%</td><td class="num">{data["qty"]:,}</td><td class="num">{data["prods"]}</td></tr>')
    w('</tbody></table></div></details></div>')

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
                w(f'<div class="uitem"><div class="uitem-main"><div class="uitem-name">{esc(it["p"])}</div><div class="uitem-supplier">Supplier: {esc(sup_name(it.get("sup", ""), sup_names))}</div></div><span class="num">{fmt_r(it["rev"])}</span></div>')
        else:
            w('<div class="uitem dim">No standout unique sellers</div>')
        w('</div>')
    w('</div></div>')

    # === SEARCH PERFORMANCE (Google Search Console) ===
    if gsc:
        w('<div id="search" class="section-anchor"></div>')
        w('<div class="card"><h3>&#x1f50d; Search Performance</h3>')
        w(f'<div class="desc">Google organic search data — {gsc["period"]} vs prior 28 days</div>')
        w('<div class="mini-strip">')
        w(f'<div class="mini-card"><div class="k">Quick wins</div><div class="v">{len(search_quick_wins)}</div><div class="n">Queries already ranking 4-10 with enough volume to push into the top 3.</div></div>')
        w(f'<div class="mini-card"><div class="k">Bigger content gaps</div><div class="v">{len(search_big_opps)}</div><div class="n">High-impression queries still sitting off page 1.</div></div>')
        if gsc["blogs"]:
            top_blog = gsc["blogs"][0]
            top_blog_title = top_blog["page"].split("/")[-1].replace("-", " ").title()[:26]
            w(f'<div class="mini-card"><div class="k">Top blog right now</div><div class="v">{esc(top_blog_title)}</div><div class="n">{top_blog["clicks"]:.0f} clicks at position {top_blog["pos"]:.1f}.</div></div>')
        w('</div>')

        # KPI row for search
        click_cls = "green" if gsc["clicks_chg"] >= 0 else "red"
        impr_cls = "green" if gsc["impr_chg"] >= 0 else "red"
        spark_html = sparkline_svg(gsc["daily_clicks"], "#3b82f6", 140, 35)
        w('<div class="kpi-strip" style="margin-bottom:16px">')
        w(f'<div class="kpi"><div class="label">Clicks (28d)</div><div class="val">{gsc["clicks"]:,}</div><div class="note">{trend_badge(gsc["clicks_chg"])} vs prior</div></div>')
        w(f'<div class="kpi"><div class="label">Impressions</div><div class="val">{gsc["impressions"]:,}</div><div class="note">{trend_badge(gsc["impr_chg"])} vs prior</div></div>')
        w(f'<div class="kpi"><div class="label">Avg CTR</div><div class="val">{gsc["ctr"]:.1f}%</div><div class="note">Was {gsc["prev_ctr"]:.1f}%</div></div>')
        w(f'<div class="kpi"><div class="label">Avg Position</div><div class="val">{gsc["position"]:.1f}</div><div class="note">{spark_html}</div></div>')
        w('</div>')

        # Blog and product performance tables side by side
        w('<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">')

        # Blog posts
        if gsc["blogs"]:
            w('<div>')
            w('<h4 style="color:#22c55e;font-size:12px;margin-bottom:6px">&#x1f4dd; Top Blog Posts</h4>')
            w('<table style="font-size:11px"><thead><tr><th>Post</th><th class="num">Clicks</th><th class="num">Impr</th><th class="num">Pos</th></tr></thead><tbody>')
            for b in gsc["blogs"]:
                title = b["page"].split("/")[-1].replace("-", " ").title()[:40]
                pos_cls = "gph" if b["pos"] <= 5 else ("gpm" if b["pos"] <= 10 else "gpl")
                w(f'<tr><td title="{esc(b["page"])}">{esc(title)}</td><td class="num">{b["clicks"]:.0f}</td><td class="num">{b["impr"]:.0f}</td><td class="num {pos_cls}">{b["pos"]:.1f}</td></tr>')
            w('</tbody></table></div>')

        # Product pages
        if gsc["products"]:
            w('<div>')
            w('<h4 style="color:#3b82f6;font-size:12px;margin-bottom:6px">&#x1f6cd; Top Product Pages</h4>')
            w('<table style="font-size:11px"><thead><tr><th>Product</th><th class="num">Clicks</th><th class="num">CTR</th><th class="num">Pos</th></tr></thead><tbody>')
            for p in gsc["products"]:
                title = p["page"].split("/")[-1].replace("-", " ").title()[:40]
                # Flag barcode URLs
                slug = p["page"].split("/")[-1]
                is_barcode = slug.replace("-","").isdigit()
                flag = ' <span style="color:#f59e0b;font-size:9px">&#x26a0;barcode URL</span>' if is_barcode else ""
                w(f'<tr><td title="{esc(p["page"])}">{esc(title)}{flag}</td><td class="num">{p["clicks"]:.0f}</td><td class="num">{p["ctr"]:.1f}%</td><td class="num">{p["pos"]:.1f}</td></tr>')
            w('</tbody></table></div>')
        w('</div>')

        # Search queries — non-branded opportunities
        if gsc["non_branded"]:
            w('<h4 style="color:#f59e0b;font-size:12px;margin:12px 0 6px">&#x1f4a1; Non-Branded Search Opportunities</h4>')
            w('<div class="desc" style="margin-bottom:6px">These queries bring people who don\'t know you yet — the highest-value traffic.</div>')
            w('<table style="font-size:11px"><thead><tr><th>Query</th><th class="num">Clicks</th><th class="num">Impr</th><th class="num">Pos</th><th>Opportunity</th></tr></thead><tbody>')
            for q in gsc["non_branded"][:6]:
                if q["pos"] <= 3:
                    opp = '<span style="color:#22c55e">&#x2713; Ranking well</span>'
                elif q["pos"] <= 10 and q["impr"] > 100:
                    opp = '<span style="color:#f59e0b">&#x2191; Push to top 3</span>'
                elif q["impr"] > 200:
                    opp = '<span style="color:#3b82f6">&#x2197; High volume — write content</span>'
                else:
                    opp = '<span style="color:#64748b">Monitor</span>'
                w(f'<tr><td>{esc(q["q"])}</td><td class="num">{q["clicks"]:.0f}</td><td class="num">{q["impr"]:.0f}</td><td class="num">{q["pos"]:.1f}</td><td>{opp}</td></tr>')
            w('</tbody></table>')
            w('<details class="collapse"><summary>View full non-branded query table</summary><div class="collapse-body"><table style="font-size:11px"><thead><tr><th>Query</th><th class="num">Clicks</th><th class="num">Impr</th><th class="num">Pos</th><th>Opportunity</th></tr></thead><tbody>')
            for q in gsc["non_branded"]:
                if q["pos"] <= 3:
                    opp = '<span style="color:#22c55e">&#x2713; Ranking well</span>'
                elif q["pos"] <= 10 and q["impr"] > 100:
                    opp = '<span style="color:#f59e0b">&#x2191; Push to top 3</span>'
                elif q["impr"] > 200:
                    opp = '<span style="color:#3b82f6">&#x2197; High volume — write content</span>'
                else:
                    opp = '<span style="color:#64748b">Monitor</span>'
                w(f'<tr><td>{esc(q["q"])}</td><td class="num">{q["clicks"]:.0f}</td><td class="num">{q["impr"]:.0f}</td><td class="num">{q["pos"]:.1f}</td><td>{opp}</td></tr>')
            w('</tbody></table></div></details>')

        # === SEARCH NARRATIVE ===
        w('<div class="story-card" style="margin-top:14px">')
        w('<div class="story-header"><span style="font-size:18px">&#x1f50e;</span><span class="story-title">Search Insights &amp; Recommendations</span></div>')
        w('<div class="story-sentences">')

        # Growth narrative
        if gsc["clicks_chg"] > 50:
            w(f'<div class="story-sentence lead">Organic search is exploding — clicks up {gsc["clicks_chg"]:.0f}% and impressions up {gsc["impr_chg"]:.0f}% vs the prior period. The SEO work is compounding.</div>')
        elif gsc["clicks_chg"] > 0:
            w(f'<div class="story-sentence lead">Organic search growing steadily — clicks up {gsc["clicks_chg"]:.0f}% vs prior period.</div>')
        else:
            w(f'<div class="story-sentence alert-sentence">Organic search is declining — clicks down {abs(gsc["clicks_chg"]):.0f}%. Investigate lost rankings.</div>')

        # Blog narrative
        if gsc["blogs"]:
            top_blog = gsc["blogs"][0]
            blog_title = top_blog["page"].split("/")[-1].replace("-", " ").title()[:50]
            total_blog_clicks = sum(b["clicks"] for b in gsc["blogs"])
            w(f'<div class="story-sentence">Blog content drives {total_blog_clicks} clicks — top performer: "{blog_title}" at position {top_blog["pos"]:.1f}. Every blog post that ranks is free advertising.</div>')

        # Barcode URL warning
        barcode_products = [p for p in gsc["products"] if p["page"].split("/")[-1].replace("-","").isdigit()]
        if barcode_products:
            named_products = [p for p in gsc["products"] if not p["page"].split("/")[-1].replace("-","").isdigit()]
            bc_ctr = sum(p["ctr"] for p in barcode_products) / len(barcode_products) if barcode_products else 0
            nm_ctr = sum(p["ctr"] for p in named_products) / len(named_products) if named_products else 0
            if nm_ctr > bc_ctr:
                w(f'<div class="story-sentence alert-sentence">Products with barcode URLs ({len(barcode_products)} in top results) average {bc_ctr:.1f}% CTR vs {nm_ctr:.1f}% for named URLs. Fixing these slugs would boost clicks significantly.</div>')

        # Quick win queries
        quick_wins = [q for q in gsc["non_branded"] if 3 < q["pos"] <= 10 and q["impr"] > 80]
        if quick_wins:
            qw_names = ", ".join(f'"{q["q"]}"' for q in quick_wins[:3])
            w(f'<div class="story-sentence opp-sentence">Quick wins: {qw_names} rank positions 4-10 with decent volume. Optimise these product/collection pages to push into top 3 — each position gained = ~30% more clicks.</div>')

        # High-volume low-ranking
        big_opps = [q for q in gsc["non_branded"] if q["pos"] > 10 and q["impr"] > 200]
        if big_opps:
            opp_names = ", ".join(f'"{q["q"]}"' for q in big_opps[:3])
            w(f'<div class="story-sentence opp-sentence">Untapped search demand: {opp_names} have high impressions but you\'re off page 1. Create dedicated content or optimise existing pages to capture this traffic.</div>')

        # CTR narrative
        if gsc["ctr"] < 2.0:
            w(f'<div class="story-sentence">Overall CTR is {gsc["ctr"]:.1f}% — below the 2-3% e-commerce benchmark. Improving meta titles and descriptions can boost this without changing rankings.</div>')

        w('</div></div>')
        w('</div>')

    # === GOOGLE REVIEWS ===
    if reviews:
        w('<div id="reviews" class="section-anchor"></div>')
        rv_latest = reviews["latest"]
        rv_start = reviews["week_start"]
        rv_targets = reviews["targets"]
        rv_date = rv_latest.get("date", "")
        rv_stores_info = {"CEN": ("Centurion", "🏆"), "GVS": ("Glen Village", "🌿"), "EDN": ("Edenvale", "💚")}

        total_reviews_all = sum(rv_latest["stores"].get(c, {}).get("total_reviews", 0) for c in ["CEN","GVS","EDN"])
        total_new_week = sum(
            rv_latest["stores"].get(c, {}).get("total_reviews", 0) - rv_start["stores"].get(c, {}).get("total_reviews", 0)
            for c in ["CEN","GVS","EDN"]
        )
        total_target_week = sum(rv_targets.values())

        w('<div class="card"><h3>⭐ Google Reviews</h3>')
        w(f'<div class="desc">Review tracking across all 3 stores | Data as at {rv_date} | Weekly target: {total_target_week} new reviews</div>')
        w('<div class="mini-strip">')
        if review_best:
            w(f'<div class="mini-card"><div class="k">Best pace this week</div><div class="v">{STORE_LABELS.get(review_best["store"], review_best["store"])}</div><div class="n">+{review_best["new"]} reviews against a target of {review_best["target"]}.</div></div>')
        if review_laggard:
            w(f'<div class="mini-card"><div class="k">Needs attention</div><div class="v">{STORE_LABELS.get(review_laggard["store"], review_laggard["store"])}</div><div class="n">+{review_laggard["new"]} so far against a target of {review_laggard["target"]}.</div></div>')
        w(f'<div class="mini-card"><div class="k">Network pace</div><div class="v">+{total_new_week}</div><div class="n">Running against a combined weekly target of {total_target_week} reviews.</div></div>')
        w('</div>')

        # KPI strip for reviews
        w('<div class="kpi-strip" style="margin-bottom:14px">')
        w(f'<div class="kpi"><div class="label">Total Reviews</div><div class="val">{total_reviews_all}</div><div class="note">Across all stores</div></div>')
        w(f'<div class="kpi"><div class="label">New This Week</div><div class="val {"green" if total_new_week >= total_target_week else ("yellow" if total_new_week >= total_target_week * 0.5 else "red")}">{total_new_week}</div><div class="note">Target: {total_target_week}</div></div>')
        for c in ["CEN","GVS","EDN"]:
            sd = rv_latest["stores"].get(c, {})
            rating = sd.get("rating", 0)
            total = sd.get("total_reviews", 0)
            star_start = rv_start["stores"].get(c, {}).get("total_reviews", 0)
            new_w = total - star_start
            tgt = rv_targets.get(c, 0)
            name, emoji = rv_stores_info[c]
            status = "green" if new_w >= tgt else ("yellow" if new_w >= tgt * 0.5 else "red")
            w(f'<div class="kpi"><div class="label">{emoji} {name}</div><div class="val">{rating}⭐</div><div class="note">{total} reviews | <span class="{status}">+{new_w}/{tgt} this week</span></div></div>')
        w('</div>')

        # Per-store breakdown bars
        w('<div class="store-grid">')
        for c in ["CEN","GVS","EDN"]:
            sd = rv_latest["stores"].get(c, {})
            bd = sd.get("breakdown", {})
            rating = sd.get("rating", 0)
            total = sd.get("total_reviews", 0)
            name, emoji = rv_stores_info[c]
            star_start = rv_start["stores"].get(c, {}).get("total_reviews", 0)
            new_w = total - star_start
            tgt = rv_targets.get(c, 0)
            pct_tgt = min(100, (new_w / tgt * 100)) if tgt > 0 else 0
            bar_cls = "ok" if pct_tgt >= 80 else ("warn" if pct_tgt >= 40 else "bad")

            max_bd = max(int(bd.get("5", 0)), int(bd.get("4", 0)), int(bd.get("3", 0)), int(bd.get("2", 0)), int(bd.get("1", 0)), 1)
            bars_html = ""
            star_colors = {"5": "#22c55e", "4": "#a3e635", "3": "#fbbf24", "2": "#fb923c", "1": "#ef4444"}
            for star in ["5","4","3","2","1"]:
                count = int(bd.get(star, 0))
                h = int(count / max_bd * 40) if max_bd > 0 else 0
                bars_html += f'<div style="text-align:center;flex:1"><div style="background:#0f172a;border-radius:3px;height:40px;display:flex;flex-direction:column-reverse;overflow:hidden"><div style="height:{h}px;background:{star_colors[star]};border-radius:0 0 3px 3px"></div></div><div style="font-size:9px;color:#64748b;margin-top:2px">{star}★ ({count})</div></div>'

            w(f'<div class="store-card">')
            w(f'<div class="sname">{emoji} {name}</div>')
            w(f'<div class="srev">{rating} ⭐</div>')
            w(f'<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">{total} total reviews</div>')
            w(f'<div class="bar-mini"><div class="bar-fill {bar_cls}" style="width:{pct_tgt:.0f}%"></div></div>')
            w(f'<div class="spct">Weekly: +{new_w} / {tgt} target</div>')
            w(f'<div style="display:flex;gap:4px;margin-top:10px">{bars_html}</div>')
            w(f'</div>')
        w('</div>')

        w('</div>')

    # Monthly Trends
    w('<div id="trends" class="section-anchor"></div>')
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
    preview_dir = os.path.join(OUT_DIR, "v8")
    os.makedirs(preview_dir, exist_ok=True)
    preview_path = os.path.join(preview_dir, "index.html")
    with open(preview_path, "w") as f:
        f.write(html)
    print(f"Dashboard written: {len(html):,} bytes -> {preview_path}")

    if args.live:
        backup_dir = os.path.join(OUT_DIR, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        live_path = os.path.join(OUT_DIR, "index.html")
        if os.path.exists(live_path):
            backup_path = os.path.join(backup_dir, f"index-pre-v8-live-{NOW.strftime('%Y-%m-%d-%H%M')}.html")
            with open(live_path) as src, open(backup_path, 'w') as dst:
                dst.write(src.read())
            print(f"Backed up previous live dashboard -> {backup_path}")
        with open(live_path, 'w') as f:
            f.write(html)
        print(f"Promoted V8 live -> {live_path}")
    ga4_status = f"GA4 Online ({'✅' if ga4 else '❌'})"
    gsc_status = f"Search Console ({'✅' if gsc else '❌'})"
    print(f"Sections: Source Health, Story, Daily Action, Top 5 Priority Actions, KPIs, Store Detail Cards, Store Progress, {ga4_status}, Hidden Gems, Low GP, Cross-Store Gaps ({len(gaps)}), Supplier ABC ({len(sup_sorted[:30])}), Store Comparison, {gsc_status}, Monthly Trends")

if __name__ == "__main__":
    main()
