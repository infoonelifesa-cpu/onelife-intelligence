# Onelife Weekly Board Report — Template Spec

## Overview
Premium 3–4 page PDF board report generated every Monday morning from live Omni POS data.
Delivered via Telegram to the Jarvis HO topic.

## Page Layout

### Page 1: Executive Summary
- Onelife logo top-left (official PNG)
- Title: "Onelife Intelligence — Weekly Report"
- Subtitle: "Week ending [date]"
- KPI cards row: MTD Revenue | GP% | Avg Daily Revenue | Days Traded
- Branch performance table with traffic-light pace indicators
- Columns: Store | MTD Revenue | Target | Pace to Target | GP%
- Traffic lights: Green >= 90%, Amber 70–89%, Red < 70%

### Page 2: Branch Deep Dive
- Daily revenue trend (30 days, line per branch + total)
- Top 5 products per branch by revenue
- Branch-level KPIs: transactions, basket size, GP%

### Page 3: Stock & Gaps
- Cross-store gap table (products selling at one branch, not stocked at another)
- Top 10 gap opportunities ranked by estimated missed revenue
- Supplier concentration: top 10 suppliers by revenue with ABC class

### Page 4: Insights & Actions
- Auto-generated key observations from alerts (critical/warning)
- Recommended actions
- Week ahead focus areas

## Colour Palette
| Token   | Hex     | Usage                     |
|---------|---------|---------------------------|
| Primary | #1B4332 | Headers, logo bar         |
| Accent  | #2D6A4F | Section headers, accents  |
| Light   | #D8F3DC | KPI card backgrounds      |
| Text    | #1B1B1B | Body copy                 |
| Muted   | #6B7280 | Secondary labels, footers |
| Green   | #16A34A | Pace >= 90%               |
| Amber   | #F59E0B | Pace 70–89%               |
| Red     | #DC2626 | Pace < 70%                |

## Data Source
`onelife-intelligence/v7_data.json` — regenerated from Omni POS before each build.

## Financials
All values in South African Rand (R), excluding VAT.

## Generation
Script: `reports/generate_weekly_board_report.py`
Output: `reports/onelife-weekly-report-YYYY-MM-DD.pdf`
