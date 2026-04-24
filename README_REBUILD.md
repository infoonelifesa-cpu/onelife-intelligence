# Onelife Intelligence Dashboard v2 Preview

Safe rebuild preview for the Onelife Intelligence dashboard. This does **not** replace `index.html`, push to GitHub Pages, touch credentials, or call external systems.

## Preview paths

- Local preview entry: `v2-preview/index.html`
- Static data contract: `v2-preview/public/data/onelife-intelligence-latest.json`
- File-friendly inline data mirror: `v2-preview/public/data/onelife-intelligence-data.js`
- Data generator: `v2-preview/generate_preview_data.py`

## How to open

Fastest:

```bash
open v2-preview/index.html
```

Cleaner browser-server preview:

```bash
python3 -m http.server 8765
# then open http://localhost:8765/v2-preview/
```

## Rebuild the data snapshot

```bash
python3 v2-preview/generate_preview_data.py
```

The generator only reads local files:

- `memory/omni_cache.json`
- `memory/daily-sales-cache.json`
- `memory/snapshots/2026-02/ana_popular_gp.json`
- `data/trade_brief_latest.json`
- `data/suppliers_master.json`
- `data/google_reviews/review_history.json`
- `v7_data.json`

## What changed in the experience

- Premium hero/executive command section with projection ring, narrative cards and Board-ready visual hierarchy.
- Dark/light theme toggle with a bespoke visual system, no Bootstrap/admin-template styling.
- Executive KPI strip with month-end target projection.
- Top action cards with priority, owner placeholder, reason and expected move.
- Store filter for Centurion, Glen Village and Edenvale.
- Store pace cards plus daily trend and target-vs-projection charts.
- Margin leak view with chart first and drilldown table collapsed.
- Range + stock cards focused on action, not raw rows.
- Supplier Pareto/concentration view with collapsed supplier detail.
- Online/Search/Reviews section with graceful warnings where source detail is missing.
- Foresight scenario panel for soft/current/recovery month-end outcomes.
- Source freshness chips so stale data is visible before decisions are made.

## Known limitations before replacing live

- Product GP/margin leak data comes from the February ANA snapshot and must be refreshed before operational action.
- Daily sales legacy cache is stale; Omni cache drives the current pace view.
- Google review history has one snapshot only, so it is a tracker card rather than a trend chart.
- Online funnel has Shopify order/revenue metrics but no local channel/device/session funnel detail yet.
- The preview is static vanilla HTML/CSS/JS. Before live replacement, wire the data contract into the real refresh pipeline and add screenshot/regression checks.
