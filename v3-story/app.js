
(function(){
  const data = window.ONELIFE_DASHBOARD_DATA;
  const app = document.getElementById('app');
  const fmt = new Intl.NumberFormat('en-ZA', {maximumFractionDigits:0});
  const money = n => 'R' + fmt.format(Math.round(Number(n||0))).replace(/,/g,' ');
  const pct = n => `${Number(n||0).toFixed(Number(n)%1?1:0)}%`;
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const exec = data.executive || {};
  const stores = data.stores || [];
  const trends = data.trends || [];
  const allTrend = trends.find(t=>t.code==='ALL') || trends[0] || {points:[]};
  const actions = data.actions || [];
  const margin = data.margin_leaks || {summary:{},items:[]};
  const range = data.range_stock || {};
  const supplier = data.supplier || {rows:[],concentration:{}};
  const foresight = data.foresight || {};
  const worstStore = [...stores].sort((a,b)=>(a.pace_gap_amount||0)-(b.pace_gap_amount||0))[0] || {};
  const riskStores = stores.filter(s=>(s.pace_gap_amount||0)<0);
  const dailyNeededTotal = stores.reduce((s,x)=>s+(x.daily_needed||0),0);
  const dailyRunTotal = stores.reduce((s,x)=>s+(x.daily_run_rate||0),0);
  const currentGapPerDay = dailyNeededTotal - dailyRunTotal;

  function header(){
    const gap = exec.projected_gap || foresight.base_gap || 0;
    const gapText = gap < 0 ? `${money(Math.abs(gap))} short` : `${money(gap)} ahead`;
    const targetCover = foresight.target_cover_pct || exec.target_pct_projected || 0;
    return `
    <header class="topbar">
      <div class="brand"><div class="logo">OL</div><div><div class="eyebrow">Onelife Intelligence</div><h1>Month-end story</h1><div class="subtle">As of ${esc(data.as_of)} · ${esc(data.date_range)} · built for decisions, not decoration.</div></div></div>
      <div class="meta"><span class="pill good">Embedded data</span><span class="pill">${esc(data.schema_version||'v3 story')}</span><span class="pill warn">Margin GP source partly stale</span></div>
    </header>
    <section class="hero">
      <div class="hero-main">
        <div class="answer"><span class="answer-dot"></span><strong>Answer first</strong></div>
        <h2>No, current pace lands at <span>${pct(targetCover)}</span> of target.</h2>
        <p class="hero-copy">The business is projected at <b>${money(exec.projected_eom)}</b> against a <b>${money(exec.target)}</b> month target. The gap is concentrated in <b>${esc(worstStore.name||'the weakest store')}</b>, while Glen Village is covering above target. The next 7 to 12 trading days need store-specific recovery, not generic “sell more” noise.</p>
        <div class="kpi-row">
          <div class="kpi bad"><small>Projected gap</small><b>${gapText}</b></div>
          <div class="kpi"><small>Projected EOM</small><b>${money(exec.projected_eom)}</b></div>
          <div class="kpi"><small>MTD Revenue</small><b>${money(exec.mtd_revenue)}</b></div>
          <div class="kpi"><small>Today</small><b>${money(exec.today_revenue)}</b></div>
        </div>
      </div>
      <aside class="hero-side">
        <div class="next-action"><small>Do this next</small><h3>Recover ${esc(worstStore.name||'top risk store')} pace first.</h3><p>${esc(actions[0]?.expected_move || 'Use the store gap and daily-needed charts below to prioritise the highest leverage recovery move today.')}</p></div>
        <div class="mini-list">
          <div class="mini-item"><span>MTD GP</span><b>${money(exec.mtd_gross_profit)} · ${pct(exec.mtd_gp_pct)}</b></div>
          <div class="mini-item"><span>Daily pace shortfall</span><b>${money(Math.max(0,currentGapPerDay))}/day</b></div>
          <div class="mini-item"><span>Biggest store risk</span><b>${esc(worstStore.name||'n/a')} · ${money(Math.abs(worstStore.pace_gap_amount||0))}</b></div>
          <div class="mini-item"><span>Recoverable margin triage</span><b>${money(margin.summary?.total_recoverable_to_35)} to 35%</b></div>
        </div>
      </aside>
    </section>
    <nav class="story-nav">
      <a href="#s1"><b>01</b><strong>Will we hit target?</strong><span>Projected finish and scenarios.</span></a>
      <a href="#s2"><b>02</b><strong>Where is the gap?</strong><span>Store-level pressure.</span></a>
      <a href="#s3"><b>03</b><strong>What changed?</strong><span>Daily rhythm and run-rate.</span></a>
      <a href="#s4"><b>04</b><strong>Where is GP leaking?</strong><span>Recoverable margin.</span></a>
      <a href="#s5"><b>05</b><strong>What can we push?</strong><span>Stock risk and safe demand.</span></a>
      <a href="#s6"><b>06</b><strong>What do we do?</strong><span>Action queue.</span></a>
    </nav>`;
  }

  function sectionHead(id,num,title,copy,so){return `<section class="section" id="${id}"><div class="section-head"><div class="num">${num}</div><div><h2>${title}</h2><p>${copy}</p></div><div class="so-what"><b>So what:</b> ${so}</div></div>`}
  function svg(w,h,inner){return `<svg class="svg-chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="chart">${inner}</svg>`}
  function clamp(v,min,max){return Math.max(min,Math.min(max,v))}
  function pointsToPath(points,w,h,pad=28,key='revenue'){
    if(!points.length) return '';
    const vals=points.map(p=>Number(p[key]||0)); const max=Math.max(...vals,1); const min=Math.min(...vals,0);
    const span=max-min||1;
    return points.map((p,i)=>{const x=pad+i*((w-pad*2)/Math.max(1,points.length-1)); const y=h-pad-((Number(p[key]||0)-min)/span)*(h-pad*2); return `${i?'L':'M'}${x.toFixed(1)} ${y.toFixed(1)}`}).join(' ');
  }
  function areaPath(points,w,h,pad=28,key='revenue'){
    const line=pointsToPath(points,w,h,pad,key); if(!line) return ''; const lastX=pad+(points.length-1)*((w-pad*2)/Math.max(1,points.length-1)); return `${line} L${lastX} ${h-pad} L${pad} ${h-pad} Z`;
  }

  function targetGauge(){
    const cover = foresight.target_cover_pct || exec.target_pct_projected || 0;
    const angle = clamp(cover,0,120)/120*360;
    const r=72,c=2*Math.PI*r; const dash=c*clamp(cover,0,120)/120;
    const scenarios = foresight.scenarios || [];
    const maxVal=Math.max(exec.target||0, ...scenarios.map(s=>s.value||0), 1);
    const scenarioBars = scenarios.map((s,i)=>{const x=28; const y=218+i*44; const width=(s.value||0)/maxVal*500; const good=(s.gap||0)>=0; return `<text x="${x}" y="${y-8}" class="label">${esc(s.name)}</text><rect x="160" y="${y-22}" width="500" height="18" rx="9" fill="rgba(255,255,255,.08)"/><rect x="160" y="${y-22}" width="${width.toFixed(1)}" height="18" rx="9" class="${good?'bar-green':'bar-red'}"/><text x="675" y="${y-8}" class="label">${money(s.value)} · ${s.gap<0?money(Math.abs(s.gap))+' short':money(s.gap)+' ahead'}</text>`}).join('');
    return `<div class="panel"><div class="chart-title"><div><h3>Target cover and finish scenarios</h3><div class="panel-note">The headline problem: projected finish is below monthly target.</div></div><div class="big-number bad">${pct(cover)}</div></div><div class="chart-wrap">${svg(760,380,`
      <defs><linearGradient id="gauge" x1="0" x2="1"><stop offset="0" stop-color="#ff6b6b"/><stop offset=".7" stop-color="#ffc857"/><stop offset="1" stop-color="#38f08a"/></linearGradient></defs>
      <circle cx="115" cy="115" r="72" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="22"/>
      <circle cx="115" cy="115" r="72" fill="none" stroke="url(#gauge)" stroke-width="22" stroke-linecap="round" transform="rotate(-90 115 115)" stroke-dasharray="${dash.toFixed(1)} ${c.toFixed(1)}"/>
      <text x="115" y="108" text-anchor="middle" class="label" font-size="30" font-weight="900">${pct(cover)}</text><text x="115" y="132" text-anchor="middle" class="muted-label">projected cover</text>
      <text x="230" y="68" class="muted-label">Target</text><text x="230" y="100" class="label" font-size="28" font-weight="900">${money(exec.target)}</text>
      <text x="230" y="142" class="muted-label">Projected EOM</text><text x="230" y="174" class="label" font-size="28" font-weight="900">${money(exec.projected_eom)}</text>
      <line x1="160" y1="198" x2="700" y2="198" class="axis"/>${scenarioBars}`)}</div></div>`;
  }

  function storeGapChart(){
    const vals=stores.map(s=>s.pace_gap_amount||0); const max=Math.max(...vals.map(v=>Math.abs(v)),1);
    const rows=stores.map((s,i)=>{const y=60+i*72; const v=s.pace_gap_amount||0; const w=Math.abs(v)/max*205; const x=v<0?360-w:360; const cls=v<0?'bar-red':'bar-green'; return `<text x="24" y="${y+5}" class="label" font-weight="800">${esc(s.name)}</text><text x="190" y="${y+5}" class="muted-label">${pct(s.projected_target_pct)} cover</text><line x1="360" y1="${y-22}" x2="360" y2="${y+22}" stroke="rgba(255,255,255,.28)"/><rect x="${x}" y="${y-18}" width="${w}" height="36" rx="10" class="${cls}"/><text x="${v<0?Math.max(230,x-8):x+w+8}" y="${y+5}" text-anchor="${v<0?'end':'start'}" class="label">${v<0?'-':''}${money(Math.abs(v))}</text>`}).join('');
    return `<div class="panel"><div class="chart-title"><div><h3>Store projected gap</h3><div class="panel-note">Negative bars need recovery. Positive bars are covering the month.</div></div><span>Gap to target</span></div>${svg(720,310,`<text x="360" y="30" text-anchor="middle" class="muted-label">Target line</text>${rows}`)}</div>`;
  }

  function runRateChart(){
    const max=Math.max(...stores.flatMap(s=>[s.daily_needed||0,s.daily_run_rate||0]),1);
    const groups=stores.map((s,i)=>{const y=58+i*74; const run=(s.daily_run_rate||0)/max*300; const need=(s.daily_needed||0)/max*300; return `<text x="24" y="${y+6}" class="label" font-weight="800">${esc(s.code)}</text><rect x="110" y="${y-24}" width="${need}" height="18" rx="9" class="bar-red" opacity=".75"/><rect x="110" y="${y+4}" width="${run}" height="18" rx="9" class="bar-green" opacity=".9"/><text x="${118+Math.max(need,run)}" y="${y-10}" class="small-label">Need ${money(s.daily_needed)}</text><text x="${118+run}" y="${y+18}" class="small-label">Run ${money(s.daily_run_rate)}</text>`}).join('');
    return `<div class="panel"><div class="chart-title"><div><h3>Daily run-rate required</h3><div class="panel-note">Shows whether each store is running fast enough for the remaining days.</div></div><span>Need vs current</span></div>${svg(640,310,`<text x="110" y="26" class="muted-label">red = required/day · green = current/day</text>${groups}`)}</div>`;
  }

  function revenueBars(){
    const max=Math.max(exec.target||0, exec.projected_eom||0, exec.mtd_revenue||0,1);
    const bars=[['MTD now',exec.mtd_revenue,'bar-blue'],['Projected',exec.projected_eom,'bar-amber'],['Target',exec.target,'bar-green']];
    const out=bars.map((b,i)=>{const y=70+i*66; const w=b[1]/max*450; return `<text x="24" y="${y+5}" class="label" font-weight="800">${b[0]}</text><rect x="130" y="${y-20}" width="450" height="32" rx="12" fill="rgba(255,255,255,.08)"/><rect x="130" y="${y-20}" width="${w}" height="32" rx="12" class="${b[2]}"/><text x="${140+w}" y="${y+2}" class="label">${money(b[1])}</text>`}).join('');
    return `<div class="panel"><div class="chart-title"><div><h3>Revenue bridge</h3><div class="panel-note">Current month-to-date, projected finish, and the actual target in one view.</div></div><span>MTD → EOM</span></div>${svg(660,275,out)}</div>`;
  }

  function trendChart(){
    const pts=allTrend.points||[]; if(!pts.length) return `<div class="panel"><h3>Daily sales trend</h3><div class="empty">Daily trend data missing.</div></div>`;
    const w=780,h=330,pad=42; const vals=pts.map(p=>p.revenue||0); const max=Math.max(...vals,1); const avg=(exec.target||0)/(stores[0]?.trading_days_total||31);
    const yAvg=h-pad-(avg/max)*(h-pad*2); const markers=pts.map((p,i)=>{if(i%3!==0 && i!==pts.length-1) return ''; const x=pad+i*((w-pad*2)/Math.max(1,pts.length-1)); const y=h-pad-((p.revenue||0)/max)*(h-pad*2); return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.5" fill="#38f08a"/><text x="${x.toFixed(1)}" y="${h-13}" text-anchor="middle" class="small-label">${String(p.date).slice(8)}</text>`}).join('');
    return `<div class="panel"><div class="chart-title"><div><h3>Daily revenue rhythm</h3><div class="panel-note">The line tells the story of consistency. Dips are where the month slipped.</div></div><span>All stores</span></div>${svg(w,h,`<defs><linearGradient id="areaGreen" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="rgba(56,240,138,.35)"/><stop offset="1" stop-color="rgba(56,240,138,0)"/></linearGradient></defs><line x1="${pad}" y1="${h-pad}" x2="${w-pad}" y2="${h-pad}" class="axis"/><line x1="${pad}" y1="${pad}" x2="${pad}" y2="${h-pad}" class="axis"/><path d="${areaPath(pts,w,h,pad)}" class="area-green"/><path d="${pointsToPath(pts,w,h,pad)}" class="line-green"/><line x1="${pad}" y1="${yAvg.toFixed(1)}" x2="${w-pad}" y2="${yAvg.toFixed(1)}" class="line-red"/><text x="${w-pad-6}" y="${yAvg-8}" text-anchor="end" class="muted-label">rough target/day ${money(avg)}</text>${markers}<text x="${pad}" y="24" class="label">Peak ${money(max)}</text>`)}</div>`;
  }

  function marginChart(){
    const items=(margin.items||[]).slice(0,8); const max=Math.max(...items.map(x=>x.recoverable_to_35||0),1);
    const rows=items.map((x,i)=>{const y=48+i*42; const w=(x.recoverable_to_35||0)/max*360; return `<text x="24" y="${y+5}" class="small-label">${esc(x.title).slice(0,32)}</text><rect x="260" y="${y-14}" width="360" height="24" rx="9" fill="rgba(255,255,255,.08)"/><rect x="260" y="${y-14}" width="${w}" height="24" rx="9" class="${x.severity==='high'?'bar-red':'bar-amber'}"/><text x="${270+w}" y="${y+4}" class="label">${money(x.recoverable_to_35)} · ${pct(x.gp_pct)} GP</text>`}).join('');
    return `<div class="panel"><div class="chart-title"><div><h3>Margin leak recovery queue</h3><div class="panel-note">Triage only: ANA GP source is stale, but the order of magnitude is too big to ignore.</div></div><div class="big-number amber">${money(margin.summary?.total_recoverable_to_35)}</div></div>${svg(760,405,rows)}</div>`;
  }

  function supplierChart(){
    const rows=(supplier.rows||[]).slice(0,8); const max=Math.max(...rows.map(r=>r.revenue||0),1);
    const out=rows.map((r,i)=>{const y=45+i*38; const w=(r.revenue||0)/max*330; const low=(r.gp_pct||0)<32; return `<text x="24" y="${y+5}" class="small-label">${esc(r.supplier_code||r.supplier).slice(0,14)}</text><rect x="150" y="${y-13}" width="330" height="22" rx="8" fill="rgba(255,255,255,.08)"/><rect x="150" y="${y-13}" width="${w}" height="22" rx="8" class="${low?'bar-red':'bar-green'}"/><text x="${490}" y="${y+4}" class="label">${money(r.revenue)} · ${pct(r.gp_pct)} GP</text>`}).join('');
    return `<div class="panel"><div class="chart-title"><div><h3>Supplier concentration + GP</h3><div class="panel-note">Top supplier revenue, coloured by GP quality. LOVE is a visible margin pressure point.</div></div><span>Top 8 suppliers</span></div>${svg(650,350,out)}</div>`;
  }

  function stockRiskChart(){
    const risks=(range.stock_risks||[]).slice(0,7); const maxRev=Math.max(...risks.map(r=>r.revenue_90||0),1);
    const out=risks.map((r,i)=>{const x=70+i*80; const cover=clamp(r.stock_cover_days||0,0,120); const y=240-(cover/120)*170; const rad=8+(r.revenue_90||0)/maxRev*20; return `<circle cx="${x}" cy="${y}" r="${rad}" class="${r.stock_cover_days===0?'bar-red':'bar-amber'}" opacity=".78"/><text x="${x}" y="282" text-anchor="middle" class="small-label">${esc(r.title).split(' ')[0]}</text>`}).join('');
    return `<div class="panel"><div class="chart-title"><div><h3>Stock risk map</h3><div class="panel-note">Lower is worse: zero-cover products with proven demand must be protected before creative pushes them.</div></div><span>Cover days vs 90d revenue</span></div>${svg(660,320,`<line x1="45" y1="250" x2="620" y2="250" class="axis"/><line x1="45" y1="55" x2="45" y2="250" class="axis"/><text x="45" y="36" class="muted-label">Higher cover</text><text x="45" y="274" class="muted-label">Zero/low cover</text>${out}`)}</div>`;
  }

  function safePushChart(){
    const safe=(range.safe_to_push||[]).slice(0,5); const max=Math.max(...safe.map(x=>x.revenue_90||0),1);
    const rows=safe.map((x,i)=>{const y=48+i*48; const w=(x.revenue_90||0)/max*360; return `<text x="24" y="${y+5}" class="small-label">${esc(x.title).slice(0,34)}</text><rect x="280" y="${y-15}" width="360" height="26" rx="10" fill="rgba(255,255,255,.08)"/><rect x="280" y="${y-15}" width="${w}" height="26" rx="10" class="bar-green"/><text x="${290+w}" y="${y+4}" class="label">${money(x.revenue_90)} · ${pct(x.gross_profit_pct)} GP</text>`}).join('');
    return `<div class="panel"><div class="chart-title"><div><h3>Safe-to-push products</h3><div class="panel-note">Demand exists and stock cover is safe enough for content/commercial pushes.</div></div><span>90d revenue + GP</span></div>${svg(760,310,rows)}</div>`;
  }

  function actionsTable(){
    const rows=actions.map(a=>`<tr><td><span class="priority ${String(a.priority).toLowerCase()}">${esc(a.priority)}</span></td><td><b>${esc(a.title)}</b><br><span class="subtle">${esc(a.lane)} · ${esc(a.owner)}</span></td><td>${esc(a.reason)}</td><td>${esc(a.expected_move)}</td></tr>`).join('');
    return `<div class="panel"><div class="chart-title"><div><h3>Action queue</h3><div class="panel-note">This is the operator view: what to do, why, and what it should move.</div></div><span>${actions.length} moves</span></div><table class="table"><thead><tr><th>Priority</th><th>Action</th><th>Why it matters</th><th>Expected move</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  function healthStrip(){
    const h=(data.source_health||[]).map(x=>`<div class="health"><b><span class="dot ${esc(x.status)}"></span>${esc(x.label)}</b><small>${esc(x.status)} · ${x.age_days}d old</small><small>${esc(x.note).slice(0,96)}</small></div>`).join('');
    return `<div class="panel"><div class="chart-title"><div><h3>Source health</h3><div class="panel-note">Freshness matters. Margin and review trend need refreshed feeds before final decisions.</div></div><span>Data reliability</span></div><div class="health-strip">${h}</div></div>`;
  }

  function storeCards(){
    return `<div class="cards">${stores.map(s=>`<div class="story-card"><h4>${esc(s.name)} · ${s.status==='behind'?'<span class="bad">Behind</span>':'<span class="good">On track</span>'}</h4><p>Projected <b>${pct(s.projected_target_pct)}</b> of target. Needs <b>${money(s.daily_needed)}</b>/day, currently running <b>${money(s.daily_run_rate)}</b>/day. ${esc((s.alerts||[])[0]||'No major alert.')}</p></div>`).join('')}</div>`;
  }

  app.innerHTML = header()
    + sectionHead('s1','01','Are we going to hit target?','One headline view of target, projected finish, and best/worst recovery scenarios.',`Current pace leaves a ${money(Math.abs(exec.projected_gap||0))} gap. Recovery push is the only scenario that clears target.`)
    + `<div class="grid two">${targetGauge()}${revenueBars()}</div></section>`
    + sectionHead('s2','02','Which store is causing the gap?','The dashboard should show the actual pressure point, not hide it in totals.',`${esc(worstStore.name||'One store')} is the first recovery lane; Glen Village is not the fire.`)
    + `<div class="grid wide">${storeGapChart()}<div>${storeCards()}</div></div><div class="grid two" style="margin-top:16px">${runRateChart()}${healthStrip()}</div></section>`
    + sectionHead('s3','03','What trend explains the miss?','Daily revenue rhythm shows whether the problem is isolated bad days or a structural pace issue.',`The month needs a higher remaining-day cadence than the current run-rate.`)
    + `<div class="grid two">${trendChart()}${revenueBars()}</div></section>`
    + sectionHead('s4','04','Where is margin leaking?','Revenue recovery is only half the story. GP leakage needs its own queue.',`Margin triage shows ${money(margin.summary?.total_recoverable_to_35)} theoretical recovery to 35%, but verify stale ANA data first.`)
    + `<div class="grid two">${marginChart()}${supplierChart()}</div></section>`
    + sectionHead('s5','05','What stock and content moves matter?','Protect winners before pushing them. Then scale products with stock cover and high GP.',`Do not drive demand into zero-cover SKUs. Push safe products with clear GP upside.`)
    + `<div class="grid two">${stockRiskChart()}${safePushChart()}</div></section>`
    + sectionHead('s6','06','What should happen next?','A dashboard earns its keep when it produces a short, ranked action list.',`Start with store pace, then stock protection, then margin validation.`)
    + actionsTable() + `</section><div class="footer">Offline single-file dashboard · data embedded from ${esc(data.as_of)} · no external dependencies.</div>`;
})();
