# Reports Page Rules

## Authentication
- SHA-256 password hash compared via `crypto.subtle.digest('SHA-256', ...)` (`reports.html:3006`)
- Session persists via `sessionStorage` key set at `reports.html:3013`, read at `:3033` (cleared on browser close)
- The full page DOM is parsed as normal - the `.auth-overlay` element (`z-index:9999`, `inset:0`) visually blocks all content until the hash matches. Content is not lazily mounted; it's covered.

## Report Loading
- JSON reports fetched and rendered using site templates (`.jr-report-body`, `.jr-trade-table`, `.jr-stats-grid`, etc.)
- Legacy HTML reports loaded via `<iframe>` (backward compatibility - detected by `format` field in index entry, or absence of explicit format)
- `reports-index.json` is the index of all available reports
- Sort order: date descending, then time descending within a date (strictest recent-first)

## Report Body Container
- `.jr-report-body` is the content wrapper for every JSON-rendered report
- `max-width: 1100px`, centered via `margin: 0 auto`
- Horizontal padding `clamp(1rem, 2vw, 1.8rem)`; top `1.4rem`, bottom `3rem`
- `font-family: 'Share Tech Mono', monospace`
- Inside `.jr-report-body`, the `.rpt-trade-wrap` gets `overflow-x: hidden; overflow-y: auto` - horizontal scrollbars never appear inside a JSON report; vertical scroll within the table body is preserved
- `.rpt-trade-wrap` default has `max-height: 60vh` so the trade table body scrolls while sticky headers stay in place

## Dynamic TP Columns (Trading Activity table)
Always shown: **Bot, TF, Side, Entry, Status, Duration**

Dynamic, inserted between Status and Duration (only when data present):
- TP1 PnL (any trade has non-null `tp1_pnl_usd`)
- TP2 PnL (any trade has non-null `tp2_pnl_usd`)
- TP3 PnL (any trade has non-null `tp3_pnl_usd`)
- Final PnL (any trade has non-null `final_pnl_usd`)

Ticker group header rows must use `colspan` equal to the total visible column count.

## Trading Activity Table Layout
- `.jr-trade-table { width: 100%; table-layout: auto }` - columns size to their content while the table fills the container
- `border-collapse: collapse`
- `white-space: nowrap` on cells; `font-variant-numeric: tabular-nums` on PnL columns
- No `<colgroup>` emitted - the earlier fixed-width spec (140/50/60/110/180/90/90) is obsolete and should not be reintroduced

## Multi-View
- Max panels computed by `getMaxPanels()` (reports.html:1759):
  - viewport `< 2560px` → 1 panel
  - `< 3440px` → 2 panels
  - `< 5120px` → 3 panels
  - `>= 5120px` → 4 panels
- The multi-view toggle is auto-hidden when `maxPanels < 2`
- Each `.mv-panel` is a `flex: 1 1 0` column inside `.mv-panels-wrap`
- Narrower panels get narrower `.jr-report-body` (capped at `100% of parent`)

## Report Picker / Swap Modal
- Report picker (compare mode): `#cpt1Modal` overlay with filter pills (`#cpt1Filters`) and the filtered list (`#cpt1List`)
- Swap modal (desktop): `#swapModalOverlay` with per-slot pills and a filtered list (`#swapList`)
- Reports already open in the primary panel or an mv-panel appear dimmed and are non-selectable

## Report Types (all rendered natively from JSON schema v1.0)
- `morning_briefing` / `evening_briefing`: TLDR, Trading Activity, Partial Closes, Pipeline Snapshot, Bot Status, Errors, Action Items
- `weekly_review`: TLDR, Trading Performance, Ticker Groups, Market Conditions, Promotion Candidates, Partial Closes Summary, Bot Status, Errors, Action Items
- `strategy_comparison`: TLDR, Head-to-Head per ticker, Rankings, Market Condition Context, Monthly Deep Dive (only when `included: true`)
