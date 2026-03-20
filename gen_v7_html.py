#!/usr/bin/env python3
"""V7 HTML builder - reads v7_data.json, outputs index.html"""
import json

with open("/Users/naadir/.openclaw/workspace/onelife-intelligence/v7_data.json") as f:
    D = json.load(f)

K = D["kpi"]; N = D["narrative"]; G = D["gaps"]; S = D["suppliers"]
M = D["matrix"]; T = D["trend"]; A = D["alerts"]; W = D["week"]

def fr(v):
    if v >= 1e6: return f"R{v/1e6:.1f}M"
    if v >= 1e3: return f"R{v/1e3:.1f}K"
    return f"R{v:.0f}"

def gc(p):
    if p >= 40: return "gp-green"
    if p >= 30: return "gp-yellow"
    return "gp-red"

def tbadge(p):
    if p > 3:  return f'<span class="t-up">\u25b2 {abs(p):.0f}%</span>'
    if p < -3: return f'<span class="t-dn">\u25bc {abs(p):.0f}%</span>'
    return '<span class="t-fl">\u2192 flat</span>'

def abc_badge(abc):
    c = {"A":"#22c55e","B":"#3b82f6","C":"#f59e0b"}.get(abc,"#888")
    return f'<span class="abc-badge" style="background:{c}">{abc}</span>'

def scol(l):
    return {"CEN":"#22c55e","GVS":"#3b82f6","EDN":"#f59e0b"}.get(l,"#94a3b8")

# Build sections
def sec_kpi():
    return f'''<section class="section">
<div class="s-title">\U0001f4ca KPI Strip <span class="s-badge">{D["date_range"]}</span></div>
<div class="kpi-grid">
  <div class="kpi-card"><div class="kpi-label">MTD Revenue</div>
    <div class="kpi-val c-green">{fr(K["mtd_rev"])}</div>
    <div class="kpi-sub">All 3 stores</div></div>
  <div class="kpi-card"><div class="kpi-label">CEN (Centurion)</div>
    <div class="kpi-val c-green">{fr(K["cen_mtd"])}</div>
    <div class="kpi-sub">{tbadge(K["cen_trend"])} vs Feb</div></div>
  <div class="kpi-card"><div class="kpi-label">GVS (Groenkloof)</div>
    <div class="kpi-val c-blue">{fr(K["gvs_mtd"])}</div>
    <div class="kpi-sub">{tbadge(K["gvs_trend"])} vs Feb</div></div>
  <div class="kpi-card"><div class="kpi-label">EDN (Edenvale)</div>
    <div class="kpi-val c-amber">{fr(K["edn_mtd"])}</div>
    <div class="kpi-sub">{tbadge(K["edn_trend"])} vs Feb</div></div>
  <div class="kpi-card"><div class="kpi-label">Blended GP%</div>
    <div class="kpi-val {"c-green" if K["mtd_gp"]>=35 else "c-amber"}">{K["mtd_gp"]:.1f}%</div>
    <div class="kpi-sub">Target \u2265 35%</div></div>
  <div class="kpi-card"><div class="kpi-label">Avg Daily Sales</div>
    <div class="kpi-val">{fr(K["avg_daily"])}</div>
    <div class="kpi-sub">{K["mtd_days"]} trading days</div></div>
  <div class="kpi-card"><div class="kpi-label">Today</div>
    <div class="kpi-val c-blue">{fr(K["today_rev"])}</div>
    <div class="kpi-sub">GP {K["today_gp"]:.1f}%</div></div>
</div></section>'''

def sec_narrative():
    return f'''<section class="section">
<div class="s-title">\U0001f9e0 AI Briefing <span class="s-badge">MOST IMPORTANT</span></div>
<div class="narrative-card">{N}</div>
</section>'''

def sec_gaps():
    rows = ""
    for i, g in enumerate(G, 1):
        mb = " ".join(f'<span class="miss-badge">{m}</span>' for m in g["miss"])
        rows += f'''<tr><td class="rank">{i}</td><td class="tdesc">{g["desc"]}</td>
          <td class="tnum">{fr(g["rev"])}</td><td class="tnum">{g["qty"]:,}</td>
          <td class="tnum {gc(g["gp"])}">{g["gp"]:.0f}%</td><td>{mb}</td></tr>'''
    return f'''<section class="section">
<div class="s-title">\U0001f50d Cross-Store Gap Analysis <span class="s-badge">KEY VALUE-ADD</span></div>
<p style="color:#94a3b8;font-size:12px;margin-bottom:12px">Products selling well at CEN (&gt;R5K or &gt;20 units) that are NOT stocked at GVS or EDN. Sorted by CEN revenue.</p>
<div class="table-wrap"><table>
<thead><tr><th>#</th><th>Product</th><th>CEN Rev</th><th>CEN Qty</th><th>GP%</th><th>Missing At</th></tr></thead>
<tbody>{rows}</tbody></table></div>
</section>'''

def sec_suppliers():
    rows = ""
    for s in S:
        rows += f'''<tr><td>{abc_badge(s["abc"])}</td><td class="tdesc">{s["name"]}</td>
          <td class="sup-code">{s["code"]}</td><td class="tnum">{fr(s["rev"])}</td>
          <td class="tnum {gc(s["gp"])}">{s["gp"]:.1f}%</td>
          <td class="tnum">{s["qty"]:,}</td></tr>'''
    return f'''<section class="section">
<div class="s-title">\U0001f3af Supplier ABC Scorecard <span class="s-badge">TOP 30</span></div>
<p style="color:#94a3b8;font-size:12px;margin-bottom:12px">A = top 80% cumulative revenue, B = next 15%, C = bottom 5%. GP color: <span class="gp-green">green &gt;40%</span>, <span class="gp-yellow">yellow 30-40%</span>, <span class="gp-red">red &lt;30%</span></p>
<div class="table-wrap"><table>
<thead><tr><th>ABC</th><th>Supplier</th><th>Code</th><th>Revenue</th><th>GP%</th><th>Units</th></tr></thead>
<tbody>{rows}</tbody></table></div>
</section>'''

def sec_matrix():
    cards = ""
    for lbl in ["CEN","GVS","EDN"]:
        m = M[lbl]; col = scol(lbl)
        uniq = ""
        for item in m["top"]:
            uniq += f'<li><span class="pn">{item["desc"][:36]}</span><span class="pr">{fr(item["rev"])}</span></li>'
        if not uniq:
            uniq = '<li style="opacity:.4">No data</li>'
        cards += f'''<div class="store-card">
          <h3 style="color:{col}">{lbl}</h3>
          <div class="store-stat"><span class="label">MTD Revenue</span><span class="val" style="color:{col}">{fr(m["rev"])}</span></div>
          <div class="store-stat"><span class="label">GP %</span><span class="val {gc(m["gp"])}">{m["gp"]:.1f}%</span></div>
          <div class="store-stat"><span class="label">Transactions</span><span class="val">{m["txn"]:,}</span></div>
          <div class="store-stat"><span class="label">Avg Basket</span><span class="val">{fr(m["basket"])}</span></div>
          <div style="font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;margin:10px 0 6px">Top Unique Sellers</div>
          <ul class="uniq-list">{uniq}</ul></div>'''
    return f'''<section class="section">
<div class="s-title">\U0001f3ea Store Comparison Matrix</div>
<div class="store-grid">{cards}</div>
</section>'''

def sec_alerts():
    def cards(items, color, icon, label):
        out = ""
        for a in items:
            out += f'''<div class="alert-card" style="border-left-color:{color}">
              <div class="alert-head"><span>{icon} <strong>{a["desc"]}</strong></span>
              <span class="alert-lbl" style="color:{color}">{label}</span></div>
              <div class="alert-meta">Stock: <b>{a.get("stock",0)}</b> &middot;
              R{a.get("price",0):,.2f} &middot; GP {a.get("gp_pct",0):.1f}% &middot;
              {a.get("supplier","?")} &middot;
              <span style="color:{color}">~R{a.get("daily_gp_lost",0):.0f}/day lost</span>
              </div></div>'''
        return out

    crit = cards(A["critical"][:15], "#ef4444", "\U0001f534", "ZERO STOCK")
    warn = cards(A["warning"][:15], "#f59e0b", "\U0001f7e1", "LOW STOCK")
    info = cards(A["info"][:9], "#3b82f6", "\U0001f535", "WATCH")

    return f'''<section class="section">
<div class="s-title">\u26a0\ufe0f Stock-Out Risk Alerts <span class="s-badge" style="background:#ef4444">{len(A["critical"])} CRITICAL</span></div>
<p style="color:#94a3b8;font-size:12px;margin-bottom:12px">EDN A-items with dangerously low stock. Every day of delay = lost GP.</p>
<div style="margin-bottom:16px"><h4 style="color:#ef4444;font-size:13px;margin-bottom:8px">\U0001f534 Zero Stock ({len(A["critical"])} items)</h4>{crit}</div>
<div style="margin-bottom:16px"><h4 style="color:#f59e0b;font-size:13px;margin-bottom:8px">\U0001f7e1 Low Stock \u22643 ({len(A["warning"])} items)</h4>{warn}</div>
<div><h4 style="color:#3b82f6;font-size:13px;margin-bottom:8px">\U0001f535 Watch List \u22645 ({len(A["info"])} items)</h4>{info}</div>
</section>'''

def sec_trends():
    TL = json.dumps([d["date"] for d in T])
    TC = json.dumps([d["cen"]  for d in T])
    TG = json.dumps([d["gvs"]  for d in T])
    TE = json.dumps([d["edn"]  for d in T])
    TT = json.dumps([d["total"] for d in T])
    WL = json.dumps([d["date"] for d in W["daily"]])
    WV = json.dumps([d["rev"]  for d in W["daily"]])
    SN = json.dumps([s["name"] for s in S[:12]])
    SR = json.dumps([s["rev"]  for s in S[:12]])
    SC = json.dumps(["#22c55e" if s["gp"]>=40 else "#f59e0b" if s["gp"]>=30 else "#ef4444" for s in S[:12]])

    return f'''<section class="section">
<div class="s-title">\U0001f4c8 Revenue Trends</div>
<div class="charts-row">
  <div class="chart-card">
    <h3>30-Day Revenue by Store</h3>
    <div class="chart-wrap"><canvas id="trendChart"></canvas></div>
  </div>
  <div class="chart-card">
    <h3>This Week (Combined)</h3>
    <div class="chart-wrap"><canvas id="weekChart"></canvas></div>
  </div>
</div>
<div class="charts-row">
  <div class="chart-card">
    <h3>Top 12 Suppliers by Revenue</h3>
    <div class="chart-wrap"><canvas id="supChart"></canvas></div>
  </div>
  <div class="chart-card">
    <h3>Store Revenue Split (MTD)</h3>
    <div class="chart-wrap"><canvas id="pieChart"></canvas></div>
  </div>
</div>
</section>
<script>
const chartOpts = {{responsive:true,maintainAspectRatio:false,
  plugins:{{legend:{{labels:{{color:'#94a3b8',font:{{size:10}}}}}}}},
  scales:{{x:{{ticks:{{color:'#64748b',font:{{size:9}}}},grid:{{color:'#1e2d3d'}}}},
           y:{{ticks:{{color:'#64748b',font:{{size:9}},callback:v=>v>=1000?(v/1000)+'K':v}},grid:{{color:'#1e2d3d'}}}}}}}};

new Chart(document.getElementById('trendChart'),{{type:'line',
  data:{{labels:{TL},datasets:[
    {{label:'CEN',data:{TC},borderColor:'#22c55e',backgroundColor:'#22c55e20',borderWidth:2,fill:true,tension:.3,pointRadius:0}},
    {{label:'GVS',data:{TG},borderColor:'#3b82f6',backgroundColor:'#3b82f620',borderWidth:2,fill:true,tension:.3,pointRadius:0}},
    {{label:'EDN',data:{TE},borderColor:'#f59e0b',backgroundColor:'#f59e0b20',borderWidth:2,fill:true,tension:.3,pointRadius:0}}
  ]}},options:chartOpts}});

new Chart(document.getElementById('weekChart'),{{type:'bar',
  data:{{labels:{WL},datasets:[
    {{label:'Revenue',data:{WV},backgroundColor:'#3b82f6',borderRadius:4}}
  ]}},options:{{...chartOpts,plugins:{{legend:{{display:false}}}}}}}});

new Chart(document.getElementById('supChart'),{{type:'bar',
  data:{{labels:{SN},datasets:[
    {{label:'Revenue',data:{SR},backgroundColor:{SC},borderRadius:3}}
  ]}},options:{{...chartOpts,indexAxis:'y',plugins:{{legend:{{display:false}}}}}}}});

new Chart(document.getElementById('pieChart'),{{type:'doughnut',
  data:{{labels:['CEN','GVS','EDN'],datasets:[
    {{data:[{K["cen_mtd"]},{K["gvs_mtd"]},{K["edn_mtd"]}],backgroundColor:['#22c55e','#3b82f6','#f59e0b'],borderWidth:0}}
  ]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:'#94a3b8',font:{{size:11}}}}}}}}}}}});
</script>'''

# ── CSS ──────────────────────────────────────────────────────────────────────
CSS = """
:root{--bg:#0f172a;--card:#1e293b;--border:#334155;--green:#22c55e;--blue:#3b82f6;--red:#ef4444;--amber:#f59e0b;--text:#e2e8f0;--muted:#94a3b8;--dim:#475569}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,sans-serif;font-size:13px;line-height:1.5}
.header{background:linear-gradient(135deg,#1e293b,#0f172a);border-bottom:1px solid var(--border);padding:14px 24px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100}
.header h1{font-size:20px;font-weight:800;background:linear-gradient(90deg,#22c55e,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.header-meta{color:var(--muted);font-size:11px;text-align:right;line-height:1.6}
.container{max-width:1400px;margin:0 auto;padding:20px}
.section{margin-bottom:32px}
.s-title{font-size:15px;font-weight:700;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px}
.s-badge{font-size:10px;font-weight:600;padding:2px 7px;border-radius:4px;background:var(--blue);color:white}
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px}
.kpi-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.kpi-label{font-size:10px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}
.kpi-val{font-size:20px;font-weight:800}
.kpi-sub{font-size:11px;color:var(--muted);margin-top:3px}
.c-green{color:var(--green)}.c-blue{color:var(--blue)}.c-amber{color:var(--amber)}.c-red{color:var(--red)}
.narrative-card{background:linear-gradient(135deg,#1e293b,#162032);border:1px solid #3b82f640;border-left:4px solid var(--blue);border-radius:10px;padding:20px 24px;font-size:14px;line-height:1.8;color:#cbd5e1}
.narrative-card strong{color:var(--text)}
.table-wrap{overflow-x:auto;border-radius:10px;border:1px solid var(--border)}
table{width:100%;border-collapse:collapse;background:var(--card)}
th{background:#162032;color:var(--muted);font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;padding:10px 12px;text-align:left;border-bottom:1px solid var(--border)}
td{padding:9px 12px;border-bottom:1px solid #1e2d3d;font-size:12px}
tr:last-child td{border-bottom:none}
tr:hover td{background:#1a2a3a}
.rank{color:var(--dim);font-size:11px;width:30px;text-align:center}
.tdesc{max-width:230px;font-weight:500}
.tnum{text-align:right;font-variant-numeric:tabular-nums;font-weight:500}
.sup-code{font-size:10px;color:var(--muted);font-family:monospace}
.gp-green{color:var(--green)!important;font-weight:600}
.gp-yellow{color:var(--amber)!important;font-weight:600}
.gp-red{color:var(--red)!important;font-weight:600}
.abc-badge{display:inline-block;width:22px;height:22px;border-radius:4px;text-align:center;line-height:22px;font-size:11px;font-weight:700;color:white}
.miss-badge{display:inline-block;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:600;background:#ef44442a;color:var(--red);margin:1px}
.t-up{font-size:11px;font-weight:600;padding:2px 5px;border-radius:3px;background:#22c55e20;color:var(--green)}
.t-dn{font-size:11px;font-weight:600;padding:2px 5px;border-radius:3px;background:#ef444420;color:var(--red)}
.t-fl{font-size:11px;font-weight:600;padding:2px 5px;border-radius:3px;background:#3b82f620;color:var(--blue)}
.store-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
@media(max-width:800px){.store-grid{grid-template-columns:1fr}}
.store-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px}
.store-card h3{font-size:16px;font-weight:700;margin-bottom:14px}
.store-stat{display:flex;justify-content:space-between;margin-bottom:8px;font-size:12px}
.store-stat .label{color:var(--muted)}.store-stat .val{font-weight:600}
.uniq-list{list-style:none;margin-top:6px;border-top:1px solid var(--border);padding-top:8px}
.uniq-list li{display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid #1e2d3d;font-size:11px}
.uniq-list li:last-child{border-bottom:none}
.pn{color:var(--text);max-width:165px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pr{color:var(--green);font-weight:600;font-size:10px;white-space:nowrap;margin-left:6px}
.alert-card{background:var(--card);border:1px solid var(--border);border-left:4px solid var(--red);border-radius:8px;padding:10px 14px;margin-bottom:8px}
.alert-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;font-size:12px}
.alert-lbl{font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;background:#ef444420}
.alert-meta{font-size:11px;color:var(--muted)}.alert-meta b{color:var(--text)}
.chart-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px}
.chart-card h3{font-size:11px;font-weight:600;color:var(--muted);margin-bottom:12px;text-transform:uppercase;letter-spacing:.5px}
.chart-wrap{position:relative;height:230px}
.charts-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
@media(max-width:900px){.charts-row{grid-template-columns:1fr}}
.footer{text-align:center;color:var(--dim);font-size:11px;padding:24px;border-top:1px solid var(--border);margin-top:32px}
"""

# ── ASSEMBLE ─────────────────────────────────────────────────────────────────
html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Onelife Intelligence | V7</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>{CSS}</style>
</head><body>
<header class="header">
  <h1>\u26a1 Onelife Intelligence | V7</h1>
  <div class="header-meta">
    <div>Generated {D["generated"]}</div>
    <div>Feb 2026 snapshot &middot; Mar MTD live &middot; 3 stores + online</div>
  </div>
</header>
<div class="container">
{sec_kpi()}
{sec_narrative()}
{sec_gaps()}
{sec_suppliers()}
{sec_matrix()}
{sec_alerts()}
{sec_trends()}
</div>
<footer class="footer">
  Onelife Intelligence &middot; {D["generated"]} &middot; 3 stores + online &middot; Powered by Jarvis \U0001f99e
</footer>
</body></html>'''

OUT = "/Users/naadir/.openclaw/workspace/onelife-intelligence/index.html"
with open(OUT, "w") as f:
    f.write(html)
print(f"Dashboard written to {OUT}")
print(f"  Size: {len(html):,} bytes")
