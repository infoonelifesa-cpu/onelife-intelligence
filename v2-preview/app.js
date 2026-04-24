(() => {
  "use strict";

  const data = window.ONELIFE_INTELLIGENCE_DATA;
  const state = { store: "ALL", theme: "dark" };
  const storeNames = { ALL: "All stores", CEN: "Centurion", GVS: "Glen Village", EDN: "Edenvale", ONLINE: "Online" };
  let colours = {
    green: "#6ef0a4",
    green2: "#2fc775",
    amber: "#ffca69",
    red: "#ff7d7d",
    blue: "#7cc6ff",
    purple: "#bfa4ff",
    muted: "#9db5aa",
    line: "rgba(192, 233, 213, 0.14)",
    soft: "#cce1d7",
    canvasA: "rgba(255,255,255,0.035)",
    canvasB: "rgba(255,255,255,0.005)",
  };

  if (!data) {
    document.body.innerHTML = '<main class="shell"><section class="card"><h1>Preview data missing</h1><p class="notice">Run <code>python3 v2-preview/generate_preview_data.py</code> from the repo root, then reload this page.</p></section></main>';
    return;
  }

  const $ = (id) => document.getElementById(id);
  const fmt = new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 0 });
  const fmt1 = new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 1 });
  const money = (value) => `R${fmt.format(Number(value || 0))}`;
  const moneyExact = (value) => `R${new Intl.NumberFormat("en-ZA", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(value || 0))}`;
  const pct = (value) => `${fmt1.format(Number(value || 0))}%`;
  const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[ch]));
  const priorityClass = (p) => String(p || "").toLowerCase();
  const statusClass = (status) => status === "on-track" ? "good" : status === "behind" ? "bad" : "watch";

  function cssVar(name, fallback) {
    return getComputedStyle(document.body).getPropertyValue(name).trim() || fallback;
  }

  function refreshColours() {
    colours = {
      green: cssVar("--green", colours.green),
      green2: cssVar("--green-2", colours.green2),
      amber: cssVar("--amber", colours.amber),
      red: cssVar("--red", colours.red),
      blue: cssVar("--blue", colours.blue),
      purple: cssVar("--purple", colours.purple),
      muted: cssVar("--muted", colours.muted),
      line: cssVar("--line", colours.line),
      soft: cssVar("--soft", colours.soft),
      canvasA: cssVar("--canvas-bg-a", colours.canvasA),
      canvasB: cssVar("--canvas-bg-b", colours.canvasB),
    };
  }

  function withAlpha(colour, alpha) {
    const value = String(colour || "").trim();
    if (value.startsWith("#")) {
      const hex = value.length === 4 ? value.replace(/^#(.)(.)(.)$/, "#$1$1$2$2$3$3") : value;
      const int = parseInt(hex.slice(1), 16);
      const r = (int >> 16) & 255;
      const g = (int >> 8) & 255;
      const b = int & 255;
      return `rgba(${r},${g},${b},${alpha})`;
    }
    return value;
  }

  function resizeCanvas(canvas) {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const fallbackHeight = Number(canvas.getAttribute("height")) || 240;
    const width = Math.max(320, rect.width || canvas.parentElement.clientWidth || 700);
    const height = Math.max(180, rect.height || fallbackHeight);
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, width, height };
  }

  function clear(ctx, width, height) {
    ctx.clearRect(0, 0, width, height);
    const gradient = ctx.createLinearGradient(0, 0, width, height);
    gradient.addColorStop(0, colours.canvasA);
    gradient.addColorStop(1, colours.canvasB);
    ctx.fillStyle = gradient;
    roundRect(ctx, 0, 0, width, height, 16);
    ctx.fill();
  }

  function roundRect(ctx, x, y, width, height, radius) {
    const r = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + width, y, x + width, y + height, r);
    ctx.arcTo(x + width, y + height, x, y + height, r);
    ctx.arcTo(x, y + height, x, y, r);
    ctx.arcTo(x, y, x + width, y, r);
    ctx.closePath();
  }

  function drawEmpty(canvas, message) {
    const { ctx, width, height } = resizeCanvas(canvas);
    clear(ctx, width, height);
    ctx.fillStyle = colours.muted;
    ctx.font = "14px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(message, width / 2, height / 2);
  }

  function drawLineChart(canvas, series) {
    const points = (series?.points || []).filter((p) => Number(p.revenue) > 0);
    if (!points.length) return drawEmpty(canvas, "No trend points available");
    const { ctx, width, height } = resizeCanvas(canvas);
    clear(ctx, width, height);
    const pad = { l: 54, r: 18, t: 20, b: 42 };
    const chartW = width - pad.l - pad.r;
    const chartH = height - pad.t - pad.b;
    const max = Math.max(...points.map((p) => p.revenue)) * 1.12;
    const min = 0;
    const x = (i) => pad.l + (points.length === 1 ? chartW / 2 : (i / (points.length - 1)) * chartW);
    const y = (v) => pad.t + chartH - ((v - min) / (max - min || 1)) * chartH;

    ctx.strokeStyle = colours.line;
    ctx.lineWidth = 1;
    ctx.fillStyle = colours.muted;
    ctx.font = "11px Inter, sans-serif";
    ctx.textAlign = "right";
    for (let i = 0; i <= 4; i++) {
      const val = (max / 4) * i;
      const yy = y(val);
      ctx.beginPath();
      ctx.moveTo(pad.l, yy);
      ctx.lineTo(width - pad.r, yy);
      ctx.stroke();
      ctx.fillText(money(val).replace("R", "R "), pad.l - 8, yy + 4);
    }

    const area = ctx.createLinearGradient(0, pad.t, 0, height - pad.b);
    area.addColorStop(0, withAlpha(colours.green, 0.26));
    area.addColorStop(1, withAlpha(colours.green, 0.00));
    ctx.beginPath();
    points.forEach((p, i) => {
      const xx = x(i), yy = y(p.revenue);
      if (i === 0) ctx.moveTo(xx, yy); else ctx.lineTo(xx, yy);
    });
    ctx.lineTo(x(points.length - 1), height - pad.b);
    ctx.lineTo(x(0), height - pad.b);
    ctx.closePath();
    ctx.fillStyle = area;
    ctx.fill();

    ctx.beginPath();
    points.forEach((p, i) => {
      const xx = x(i), yy = y(p.revenue);
      if (i === 0) ctx.moveTo(xx, yy); else ctx.lineTo(xx, yy);
    });
    ctx.strokeStyle = colours.green;
    ctx.lineWidth = 3;
    ctx.stroke();

    points.forEach((p, i) => {
      if (i % Math.ceil(points.length / 7) === 0 || i === points.length - 1) {
        ctx.fillStyle = colours.muted;
        ctx.textAlign = "center";
        ctx.font = "11px Inter, sans-serif";
        ctx.fillText(p.date.slice(5), x(i), height - 16);
      }
    });
  }

  function drawPaceChart(canvas, stores) {
    if (!stores.length) return drawEmpty(canvas, "No store pace data available");
    const { ctx, width, height } = resizeCanvas(canvas);
    clear(ctx, width, height);
    const pad = { l: 56, r: 20, t: 28, b: 54 };
    const chartW = width - pad.l - pad.r;
    const chartH = height - pad.t - pad.b;
    const max = Math.max(...stores.flatMap((s) => [s.target, s.projected_eom])) * 1.12;
    const groupW = chartW / stores.length;
    const barW = Math.min(46, groupW / 4);
    const y = (v) => pad.t + chartH - (v / (max || 1)) * chartH;

    ctx.strokeStyle = colours.line;
    ctx.fillStyle = colours.muted;
    ctx.font = "11px Inter, sans-serif";
    ctx.textAlign = "right";
    for (let i = 0; i <= 4; i++) {
      const val = (max / 4) * i;
      const yy = y(val);
      ctx.beginPath(); ctx.moveTo(pad.l, yy); ctx.lineTo(width - pad.r, yy); ctx.stroke();
      ctx.fillText(money(val), pad.l - 8, yy + 4);
    }

    stores.forEach((s, i) => {
      const center = pad.l + groupW * i + groupW / 2;
      const targetH = chartH - (y(s.target) - pad.t);
      const projH = chartH - (y(s.projected_eom) - pad.t);
      ctx.fillStyle = "rgba(255,255,255,0.14)";
      roundRect(ctx, center - barW - 4, y(s.target), barW, targetH, 8); ctx.fill();
      ctx.fillStyle = s.projected_eom >= s.target ? colours.green : colours.amber;
      roundRect(ctx, center + 4, y(s.projected_eom), barW, projH, 8); ctx.fill();
      ctx.fillStyle = colours.soft;
      ctx.font = "12px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(s.code, center, height - 24);
      ctx.fillStyle = s.projected_eom >= s.target ? colours.green : colours.red;
      ctx.fillText(pct(s.projected_target_pct), center, y(Math.max(s.target, s.projected_eom)) - 8);
    });

    ctx.fillStyle = colours.muted;
    ctx.textAlign = "left";
    ctx.font = "12px Inter, sans-serif";
    ctx.fillText("Target", width - 138, 18);
    ctx.fillStyle = "rgba(255,255,255,0.14)"; ctx.fillRect(width - 180, 9, 34, 9);
    ctx.fillStyle = colours.green; ctx.fillRect(width - 86, 9, 34, 9);
    ctx.fillStyle = colours.muted; ctx.fillText("Projected", width - 46, 18);
  }

  function drawBarChart(canvas, items, options = {}) {
    if (!items.length) return drawEmpty(canvas, options.empty || "No chart data available");
    const { ctx, width, height } = resizeCanvas(canvas);
    clear(ctx, width, height);
    const pad = { l: 170, r: 26, t: 18, b: 28 };
    const chartW = width - pad.l - pad.r;
    const rowH = Math.min(34, (height - pad.t - pad.b) / items.length);
    const max = Math.max(...items.map((x) => Number(x.value || 0))) * 1.08;
    ctx.font = "12px Inter, sans-serif";
    items.forEach((item, i) => {
      const y = pad.t + i * rowH + 5;
      const w = (Number(item.value || 0) / (max || 1)) * chartW;
      ctx.fillStyle = colours.muted;
      ctx.textAlign = "right";
      ctx.fillText(truncate(item.label, 23), pad.l - 10, y + 16);
      ctx.fillStyle = item.colour || colours.green;
      roundRect(ctx, pad.l, y, Math.max(3, w), rowH - 10, 8);
      ctx.fill();
      ctx.fillStyle = colours.soft;
      ctx.textAlign = "left";
      ctx.fillText(item.display || money(item.value), pad.l + w + 8, y + 16);
    });
  }

  function drawScenarioChart(canvas, foresight) {
    const items = (foresight.scenarios || []).map((s) => ({ label: s.name, value: s.value, gap: s.gap }));
    if (!items.length) return drawEmpty(canvas, "No scenario data available");
    const { ctx, width, height } = resizeCanvas(canvas);
    clear(ctx, width, height);
    const pad = { l: 48, r: 18, t: 26, b: 42 };
    const chartW = width - pad.l - pad.r;
    const chartH = height - pad.t - pad.b;
    const max = Math.max(foresight.target || 0, ...items.map((i) => i.value)) * 1.12;
    const barW = Math.min(78, chartW / (items.length * 2));
    const groupW = chartW / items.length;
    const y = (v) => pad.t + chartH - (v / (max || 1)) * chartH;
    const targetY = y(foresight.target || 0);
    ctx.strokeStyle = "rgba(255,202,105,0.74)";
    ctx.setLineDash([6, 6]);
    ctx.beginPath(); ctx.moveTo(pad.l, targetY); ctx.lineTo(width - pad.r, targetY); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = colours.amber;
    ctx.font = "12px Inter, sans-serif";
    ctx.fillText("Target", pad.l + 4, targetY - 7);

    items.forEach((item, i) => {
      const center = pad.l + groupW * i + groupW / 2;
      const h = chartH - (y(item.value) - pad.t);
      ctx.fillStyle = item.gap >= 0 ? colours.green : (item.label === "Soft landing" ? colours.red : colours.amber);
      roundRect(ctx, center - barW / 2, y(item.value), barW, h, 10);
      ctx.fill();
      ctx.textAlign = "center";
      ctx.font = "12px Inter, sans-serif";
      ctx.fillStyle = colours.soft;
      ctx.fillText(item.label, center, height - 18);
      ctx.fillStyle = item.gap >= 0 ? colours.green : colours.red;
      ctx.fillText((item.gap >= 0 ? "+" : "") + money(item.gap), center, y(item.value) - 8);
    });
  }

  function truncate(text, max) {
    const s = String(text ?? "");
    return s.length > max ? `${s.slice(0, max - 1)}…` : s;
  }

  function selectedStores() {
    return state.store === "ALL" ? data.stores : data.stores.filter((s) => s.code === state.store);
  }

  function selectedTrend() {
    return data.trends.find((s) => s.code === state.store) || data.trends.find((s) => s.code === "ALL") || data.trends[0];
  }

  function filteredMarginItems(limit = 12) {
    const items = data.margin_leaks.items || [];
    return items.filter((item) => state.store === "ALL" || item.store_code === state.store).slice(0, limit);
  }

  function storeNameFromAny(value) {
    const raw = String(value || "").toLowerCase();
    if (["cen", "centurion", "ho"].includes(raw)) return "Centurion";
    if (["gvs", "glen village"].includes(raw)) return "Glen Village";
    if (["edn", "edenvale"].includes(raw)) return "Edenvale";
    return value;
  }

  function worstStore() {
    return [...(data.stores || [])]
      .filter((s) => Number(s.target || 0) > 0)
      .sort((a, b) => Number(a.projected_target_pct || 0) - Number(b.projected_target_pct || 0))[0];
  }

  function renderHeader() {
    const ex = data.executive;
    const cover = Math.max(0, Number(ex.target_pct_projected || 0));
    const ring = Math.min(360, Math.round((cover / 100) * 360));
    const worst = worstStore();
    const topStock = (data.range_stock?.stock_risks || [])[0];
    const topMargin = (data.margin_leaks?.items || [])[0];

    $("asOf").textContent = `Data as of ${data.as_of || "unknown"}`;
    $("schema").textContent = data.schema_version;
    $("dateRange").textContent = data.date_range || "";
    $("heroRing").style.setProperty("--ring", `${ring}deg`);
    $("heroRingValue").textContent = pct(cover);
    $("heroGap").textContent = `${ex.projected_gap >= 0 ? "+" : ""}${money(ex.projected_gap)}`;
    $("heroToday").textContent = money(ex.today_revenue);
    $("heroGp").textContent = pct(ex.mtd_gp_pct);
    $("heroRisk").innerHTML = worst
      ? `<strong>${esc(worst.name)}</strong> is the main pace risk at ${pct(worst.projected_target_pct)} projected cover. Required run-rate: <strong>${money(worst.daily_needed)}/day</strong>.`
      : "No store pace risk available in the current source.";
    $("heroNarrative").innerHTML = `
      <div class="narrative-card"><small>Board read</small><strong>${pct(cover)}</strong><em>${money(ex.projected_eom)} projected against ${money(ex.target)} target.</em></div>
      <div class="narrative-card"><small>Store focus</small><strong>${esc(worst?.name || "n/a")}</strong><em>${worst ? `${money(Math.abs(worst.pace_gap_amount))} projected gap before interventions.` : "Store feed unavailable."}</em></div>
      <div class="narrative-card"><small>Next lever</small><strong>${esc(topStock ? "Stock" : "Margin")}</strong><em>${esc(topStock?.title || topMargin?.title || "No priority item loaded")}</em></div>
    `;
    $("storyExecutive").textContent = `${ex.projected_gap >= 0 ? "+" : ""}${money(ex.projected_gap)} forecast gap`;
    $("storyStore").textContent = worst ? `${worst.name}: ${pct(worst.projected_target_pct)} cover` : "Store pace unavailable";
    $("storyMargin").textContent = topMargin ? `${money(topMargin.recoverable_to_35)} top recovery` : "No candidates";
    $("storyStock").textContent = topStock ? `${topStock.inventory_quantity} units · ${topStock.stock_cover_days}d cover` : "No stock risks";
  }

  function renderSourceHealth() {
    $("sourceHealth").innerHTML = (data.source_health || []).map((s) => `
      <article class="health ${esc(s.status)}">
        <strong>${esc(s.label)}</strong>
        <span>${esc(String(s.status || "unknown").toUpperCase())}${s.age_days === null || s.age_days === undefined ? "" : ` · ${s.age_days}d old`}</span>
        <span>${esc(s.note || s.path || "")}</span>
      </article>
    `).join("");
  }

  function renderExecutive() {
    const ex = data.executive;
    const gapClass = ex.projected_gap >= 0 ? "good" : Math.abs(ex.projected_gap) < ex.target * 0.08 ? "warn" : "bad";
    const kpis = [
      { label: "MTD revenue", value: money(ex.mtd_revenue), note: `${pct(ex.target_pct_current)} of ${money(ex.target)} target`, cls: "" },
      { label: "Today", value: money(ex.today_revenue), note: `${pct(ex.today_gp_pct)} GP today`, cls: "" },
      { label: "MTD GP", value: pct(ex.mtd_gp_pct), note: `${money(ex.mtd_gross_profit)} gross profit`, cls: ex.mtd_gp_pct >= 35 ? "good" : "warn" },
      { label: "Projected EOM", value: money(ex.projected_eom), note: `${pct(ex.target_pct_projected)} projected target cover`, cls: gapClass },
      { label: "Projected gap", value: `${ex.projected_gap >= 0 ? "+" : ""}${money(ex.projected_gap)}`, note: "vs full-month target", cls: gapClass },
    ];
    $("kpiGrid").innerHTML = kpis.map((k) => `<article class="kpi ${k.cls}"><small>${esc(k.label)}</small><strong>${esc(k.value)}</strong><span>${esc(k.note)}</span></article>`).join("");

    $("projectionHeadline").textContent = `${money(ex.projected_eom)} forecast vs ${money(ex.target)} target`;
    $("projectionBadge").textContent = ex.projected_gap >= 0 ? "Target covered" : `${money(Math.abs(ex.projected_gap))} short`;
    $("projectionBadge").className = `status-badge ${ex.projected_gap >= 0 ? "good" : "watch"}`;
    $("projectionProgress").style.width = `${Math.min(110, Math.max(0, ex.target_pct_projected))}%`;
    $("projectionMeta").innerHTML = `<span>${pct(ex.target_pct_projected)} projected cover</span><span>${ex.projected_gap >= 0 ? "+" : ""}${money(ex.projected_gap)} gap</span>`;
    drawScenarioChart($("foresightChart"), data.foresight);
  }

  function actionMatches(action) {
    if (state.store === "ALL") return true;
    const code = String(action.store_code || "ALL").toUpperCase();
    const wantedName = storeNames[state.store];
    return code === "ALL" || code === state.store || storeNameFromAny(code) === wantedName;
  }

  function renderActions() {
    let actions = (data.actions || []).filter(actionMatches);
    if (actions.length < 3) actions = data.actions || [];
    $("actionCards").innerHTML = actions.slice(0, 3).map((a) => `
      <article class="action-card">
        <div class="action-top"><span class="priority ${priorityClass(a.priority)}">${esc(a.priority)}</span><span class="pill">${esc(a.lane)}</span></div>
        <h3>${esc(a.title)}</h3>
        <p><strong>Reason:</strong> ${esc(a.reason)}</p>
        <p><strong>Expected move:</strong> ${esc(a.expected_move)}</p>
        <div class="owner">Owner: ${esc(a.owner || "Unassigned")}</div>
      </article>
    `).join("");
  }

  function renderStorePace() {
    const stores = selectedStores();
    $("storeCards").innerHTML = stores.map((s) => `
      <article class="store-card">
        <div class="store-top"><h3>${esc(s.name)}</h3><span class="status-badge ${statusClass(s.status)}">${esc(s.status.replace("-", " "))}</span></div>
        <strong>${money(s.projected_eom)}</strong>
        <p class="muted">Projected EOM · ${pct(s.projected_target_pct)} of target</p>
        <dl>
          <div><dt>MTD</dt><dd>${money(s.mtd_revenue)}</dd></div>
          <div><dt>Target</dt><dd>${money(s.target)}</dd></div>
          <div><dt>Run-rate</dt><dd>${money(s.daily_run_rate)}/day</dd></div>
          <div><dt>Needed</dt><dd>${money(s.daily_needed)}/day</dd></div>
        </dl>
        ${s.alerts?.length ? `<ul class="alert-list">${s.alerts.slice(0, 3).map((a) => `<li>${esc(a)}</li>`).join("")}</ul>` : ""}
      </article>
    `).join("");
    drawLineChart($("trendChart"), selectedTrend());
    drawPaceChart($("paceChart"), stores);
  }

  function renderMargin() {
    const items = filteredMarginItems(10);
    const total = items.reduce((sum, item) => sum + Number(item.recoverable_to_35 || 0), 0);
    $("marginSummary").textContent = `${items.length} candidates in view · ${money(total)} recoverable to 35% GP if still current`;
    drawBarChart($("marginChart"), items.slice(0, 7).map((i) => ({
      label: i.title,
      value: i.recoverable_to_35,
      display: `${money(i.recoverable_to_35)} · ${pct(i.gp_pct)} GP`,
      colour: i.severity === "high" ? colours.red : colours.amber,
    })), { empty: "No margin candidates for this store" });

    const top = items[0];
    $("marginInsights").innerHTML = top ? `
      <li><strong>${esc(top.title)}</strong> is the biggest visible GP recovery candidate in this filter.</li>
      <li>Snapshot GP is <strong>${pct(top.gp_pct)}</strong> on ${money(top.revenue)} revenue, with roughly <strong>${money(top.recoverable_to_35)}</strong> recoverable to 35% GP.</li>
      <li>This source is stale. Treat it as a validation queue, not a price change instruction.</li>
    ` : `<li>No margin candidate in this filter. Switch back to All stores for the full queue.</li>`;

    $("marginTable").innerHTML = table(items.slice(0, 25), [
      ["Product", (r) => `<strong>${esc(r.title)}</strong><br><span class="muted">${esc(r.sku)} · ${esc(r.store)}</span>`],
      ["Revenue", (r) => money(r.revenue)],
      ["GP %", (r) => pct(r.gp_pct)],
      ["Recoverable", (r) => money(r.recoverable_to_35)],
      ["Supplier", (r) => esc(truncate(r.supplier, 34))],
    ]);
  }

  function rangeItemMatchesStore(item) {
    if (state.store === "ALL") return true;
    const wanted = storeNames[state.store];
    const stores = [...(item.reorder_stores || []), ...(item.missing_stores || [])].map(storeNameFromAny);
    return stores.includes(wanted);
  }

  function renderRangeStock() {
    const risks = (data.range_stock.stock_risks || []).filter(rangeItemMatchesStore);
    const visibleRisks = (risks.length ? risks : data.range_stock.stock_risks || []).slice(0, 4);
    $("stockRiskCards").innerHTML = visibleRisks.map((r) => `
      <article class="mini-card">
        <span class="priority ${r.severity === "high" ? "high" : r.severity === "medium" ? "medium" : "low"}">${esc(r.severity)}</span>
        <h3>${esc(r.title)}</h3>
        <p>${money(r.revenue_90)} 90d revenue · ${esc(r.inventory_quantity)} units · ${esc(r.stock_cover_days)} days cover</p>
        <p><strong>Move:</strong> ${esc(r.action)}${r.reorder_stores?.length ? ` · ${esc(r.reorder_stores.join(", "))}` : ""}</p>
      </article>
    `).join("");

    $("safePushList").innerHTML = (data.range_stock.safe_to_push || []).slice(0, 5).map((p) => `
      <div class="stack-item"><h4>${esc(p.title)}</h4><p>${esc(p.category)} · ${money(p.revenue_90)} 90d · ${pct(p.gross_profit_pct)} GP · ${esc(p.stock_cover_days)}d cover</p></div>
    `).join("") || `<div class="empty">No safe-push products in this source.</div>`;

    const gaps = (data.range_stock.range_gaps || []).filter(rangeItemMatchesStore).slice(0, 6);
    $("rangeGapList").innerHTML = (gaps.length ? gaps : (data.range_stock.range_gaps || []).slice(0, 6)).map((g) => `
      <div class="stack-item"><h4>${esc(g.title)}</h4><p>${money(g.revenue)} revenue · missing: ${esc((g.missing_stores || []).join(", "))} · ${esc(g.action)}</p></div>
    `).join("") || `<div class="empty">No range gaps found in this preview.</div>`;
  }

  function renderSupplier() {
    const rows = data.supplier.rows || [];
    const concentration = data.supplier.concentration || {};
    $("supplierSummary").textContent = `${concentration.supplier_count || rows.length} suppliers · top 5 hold ${pct(concentration.top5_revenue_share_pct)} of snapshot revenue`;
    drawBarChart($("supplierChart"), rows.slice(0, 10).map((r, idx) => ({
      label: r.supplier_code,
      value: r.revenue,
      display: `${money(r.revenue)} · ${pct(r.share_pct)} share · ${pct(r.gp_pct)} GP`,
      colour: idx < 3 ? colours.blue : colours.green,
    })), { empty: "No supplier data available" });
    $("supplierTable").innerHTML = table(rows.slice(0, 25), [
      ["Supplier", (r) => `<strong>${esc(r.supplier_code)}</strong><br><span class="muted">${esc(truncate(r.supplier, 58))}</span>`],
      ["Revenue", (r) => money(r.revenue)],
      ["Share", (r) => pct(r.share_pct)],
      ["GP %", (r) => pct(r.gp_pct)],
      ["SKUs", (r) => esc(r.sku_count)],
      ["Units", (r) => esc(fmt.format(r.quantity))],
    ]);
  }

  function renderOnlineSearchReviews() {
    const online = data.online_funnel || {};
    $("onlineCard").innerHTML = `
      <div class="card-head compact"><h3>Online funnel</h3><span class="status-badge ${online.status === "available" ? "good" : "watch"}">${esc(online.status || "limited")}</span></div>
      ${online.warning ? `<p class="notice">${esc(online.warning)}</p>` : ""}
      <div class="funnel">${(online.funnel || []).map((f) => `<div class="funnel-row"><span>${esc(f.stage)}</span><strong>${f.value === null || f.value === undefined ? "Missing" : (f.stage === "Revenue" ? money(f.value) : esc(f.value))}</strong></div>`).join("")}</div>
      <details class="drilldown"><summary>Top online cities</summary><div class="table-wrap">${table(online.top_cities_90d || [], [["City", r => esc(r.city)], ["Revenue", r => money(r.revenue)], ["Orders", r => esc(r.orders)], ["AOV", r => money(r.average_order_value)]])}</div></details>
    `;

    const sr = data.search_reviews || {};
    $("reviewsCard").innerHTML = `
      <div class="card-head compact"><h3>Google reviews</h3><span class="muted">${esc(sr.reviews_date || "No date")}</span></div>
      ${(sr.reviews || []).map((r) => `<div class="review-row"><span>${esc(r.store)}<br><span class="muted">${esc(r.total_reviews)} reviews · ${esc(r.one_two_star)} low ratings</span></span><strong>${esc(r.rating.toFixed ? r.rating.toFixed(1) : r.rating)}★</strong></div>`).join("") || `<div class="empty">No review snapshots available.</div>`}
    `;

    $("seoCard").innerHTML = `
      <div class="card-head compact"><h3>SEO opportunities</h3><span class="muted">Search-led cards</span></div>
      ${(sr.seo_opportunities || []).slice(0, 4).map((o) => `<div class="seo-card"><strong>${esc(o.theme)}</strong><p class="muted">${esc(o.why_now)}</p><p>${(o.products_to_push || []).slice(0, 2).map(esc).join(" · ")}</p></div>`).join("") || `<div class="empty">No SEO opportunity cards in this preview.</div>`}
    `;
  }

  function table(rows, cols) {
    if (!rows || !rows.length) return `<div class="empty">No rows for this drilldown.</div>`;
    return `<table><thead><tr>${cols.map(([h]) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${cols.map(([, fn]) => `<td>${fn(r)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  }

  function setTheme(theme) {
    state.theme = theme === "light" ? "light" : "dark";
    document.body.dataset.theme = state.theme;
    const toggle = $("themeToggle");
    if (toggle) toggle.textContent = state.theme === "dark" ? "Light mode" : "Dark mode";
    try { localStorage.setItem("onelife-intelligence-preview-theme", state.theme); } catch (_) { /* file:// safe */ }
  }

  function renderAll() {
    refreshColours();
    renderHeader();
    renderSourceHealth();
    renderExecutive();
    renderActions();
    renderStorePace();
    renderMargin();
    renderRangeStock();
    renderSupplier();
    renderOnlineSearchReviews();
  }

  $("storeFilter").addEventListener("change", (event) => {
    state.store = event.target.value;
    renderActions();
    renderStorePace();
    renderMargin();
    renderRangeStock();
  });
  $("resetFilter").addEventListener("click", () => {
    state.store = "ALL";
    $("storeFilter").value = "ALL";
    renderActions();
    renderStorePace();
    renderMargin();
    renderRangeStock();
  });
  $("themeToggle").addEventListener("click", () => {
    setTheme(state.theme === "dark" ? "light" : "dark");
    renderAll();
  });
  window.addEventListener("resize", () => requestAnimationFrame(renderAll));

  try { setTheme(localStorage.getItem("onelife-intelligence-preview-theme") || "dark"); } catch (_) { setTheme("dark"); }
  renderAll();
})();
