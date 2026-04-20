# Site Design Rules

## Fonts
- Headings: `'Oxanium', sans-serif`
- Body / data / monospace: `'Share Tech Mono', monospace`
- Never use Arial, Helvetica, or system fonts on the site
- Google Fonts imported at the top of each page's `<style>` (`@import url('https://fonts.googleapis.com/css2?family=Oxanium:wght@300;400;600;700;800&family=Share+Tech+Mono&display=swap')`)

## Site CSS Variables (`:root` in index.html)
These are the real site tokens - use them instead of hardcoded hex where possible.

| Token | Value | Use |
|---|---|---|
| `--bg` | `#080c14` | Page background |
| `--bg-card` | `#0d1424` | Card / raised surfaces |
| `--bg-raised` | `#0f1a30` | Raised panels |
| `--bg-surface` | `#1a2a50` | Highest surfaces |
| `--accent` | `#64b4ff` | Primary accent, links, underlines |
| `--accent-2` / `--accent2` | `#4a9aee` | Secondary accent |
| `--accent-3` / `--accent3` | `#a78bfa` | Tertiary accent (purple) |
| `--text` | `#e8f4ff` | Primary text |
| `--text-sub` / `--sub` | `#7a90aa` | Secondary text |
| `--text-dim` / `--dim` | `rgba(232,244,255,0.3)` (reports) / `0.25` (index) | Tertiary text |
| `--green` | `#00ff64` | Site-wide green (positive/live indicators) |
| `--red` | `#ff4a36` | Site-wide red (negative/error) |
| `--amber` | `#f5a94f` | Amber warn |
| `--blue` | `#64b4ff` | Blue accent |
| `--purple` | `#a855f7` | Purple accent |
| `--orange` | `#ff8c42` | Orange accent |
| `--pink` | `#f739f7` | Pink accent |
| `--border` | `rgba(255,255,255,0.06)` | Subtle border |
| `--border-b` | `rgba(255,255,255,0.12)` | Stronger border |

`reports.html` defines its own overlapping set: `--bg-card:#0d1424`, `--accent:#64b4ff`, `--text:#e8f4ff`, `--sub:#7a90aa`, `--dim:rgba(232,244,255,0.3)`, plus `--gray:#8892a4`, `--teal:#4ecca3`, and the ticker palette.

Do NOT introduce new top-level site tokens unless necessary.

## Nav Bar
- `background: rgba(8,12,20,0.85)`
- `backdrop-filter: blur(12px)` + `-webkit-backdrop-filter: blur(12px)`
- Fixed, `z-index:200`, `height: clamp(48px, 5.5vh, 60px)`
- Applies to all three pages (`.site-nav` selector)

## Context-Specific Colors (not site tokens)

### Roadmap Category Colors (`index.html:1269, 1281`)
- Completed: `#5DCAA5`
- In Progress: `#85B7EB`
- Short-term: `#AFA9EC`
- Mid-term: `#F0997B`
- Long-term: `#B4B2A9`

### Security Gauge Colors (dynamic by percentage, `index.html:1606`)
- ≥ 80%: `#00ff64` (green, same as `--green`)
- 60-79%: `#F0997B` (orange)
- < 60%: `#e24b4a` (red)

### JSON Report PnL Colors (reports.html, `.jr-*` classes)
These are report-specific, NOT site-wide text tokens.
- Positive: `#00c896` (`.jr-pos`)
- Negative: `#e84142` (`.jr-neg`) - also the AVAX ticker color
- Zero: `#e8eaf0` (`.jr-zero`)
- Null / dash: `#8892a4` (`.jr-null`, same as `--gray` in reports.html)

### Email-Template HTML Reports (legacy iframe content under `reports/`)
Separate palette used inside email-style HTML reports only:
- Body bg: `#0d0f1a`
- Inner card: `#1a1a2e`
- Header / footer: `#12152e`
- Teal accent: `#4ecca3`

These do NOT apply to the site shell.

## Layout Rules
- Do not add new em dashes - use regular dashes in all new content (existing em dashes remain; no sweep)
- All numbers from `site-data.json` via `data-site="..."` attributes (20+ in index.html, 14+ in pipeline.html)
- Each section has its own Intersection Observer. Actual thresholds in index.html: `0.2` (4 occurrences), `0.3` (2 occurrences), plus 0.08 and 0.01 for specific edge cases. When adding a new observer, match the 0.2 / 0.3 convention.
- No chain reactions from section title animations

## Report Rendering (summary - see rules/reports.md for full spec)
- Reports render from JSON using native site templates, not iframes
- Dynamic TP columns: only show TP1 / TP2 / TP3 / Final PnL when at least one trade has non-null data for that level
- PnL coloring uses the `.jr-pos/.jr-neg/.jr-zero/.jr-null` classes above
- All timestamps displayed in America/New_York (ET)
- Column naming: "TP1 PnL", "TP2 PnL", "TP3 PnL", "Final PnL" - never "P&L"
