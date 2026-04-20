# AutoBots Nexus - GitHub Pages Site

## What This Is
The public-facing website for the AutoBots Trading ecosystem. Hosted on GitHub Pages at https://dsatt22.github.io/autobots-nexus/. Shows how the ecosystem works, the architecture, pipeline, and roadmap. The Reports section is password-protected and displays trading reports for the operator only.

## Tech Stack
- Static HTML/CSS/JS (no framework, no build step)
- GitHub Pages deployment (auto-deploys from main branch)
- No npm dependencies in production
- Dev-only tooling: ESLint, Stylelint, HTMLHint, Gitleaks (run via scan.py)
- Dev config files at repo root: `.htmlhintrc`, `.stylelintrc.json`, `eslint.config.mjs`

## Pages
- `index.html` - main site (hero, architecture, playbook, notifications, security, roadmap sections)
- `pipeline.html` - standalone pipeline page
- `reports.html` - password-protected reports viewer (loads JSON reports; falls back to iframe for legacy HTML reports)

## Nav Order (all pages)
HOME, ARCHITECTURE, PLAYBOOK, NOTIFICATIONS, SECURITY, ROADMAP, PIPELINE, REPORTS

## Nav Bar (all three pages)
- `background: rgba(8,12,20,0.85)`
- `backdrop-filter: blur(12px)` (with `-webkit-backdrop-filter` fallback)
- Fixed, `z-index:200`, height `clamp(48px, 5.5vh, 60px)`
- Semi-transparent with blur so nav text stays legible over any content

## Design System
- Background: Dark Navy `#080c14`, forced dark theme, no switcher
- Mesh Aurora canvas background (persistent across all sections)
- Fonts: Oxanium for headings, Share Tech Mono for body/monospace/data
- No gradients or glow effects that don't match existing sections
- Do not add new em dashes - use regular dashes in all new content (existing em dashes remain; don't sweep them)

See `.claude/rules/site-design.md` for the full token list and detailed rules.

## Ticker Colors
BTC `#f7931a`, ETH `#627eea`, SOL `#9945ff`, BNB `#f3ba2f`, ADA `#3cc8c8`, DOGE `#ba8f1a`, DOT `#e6007a`, AVAX `#e84142`, LINK `#2a5ada`, XRP `#00aae4`
Defined as CSS variables in `reports.html` (`--btc`, `--eth`, ...) and as the `TC` lookup object in JS.

## Dynamic Data
- All numbers on the site come from `site-data.json` via `data-site="..."` attributes
- The site auto-updater (in the trading-bot repo) generates and pushes `site-data.json` twice daily
- Roadmap data comes from the `ops.roadmap_items` table via the auto-updater
- Never hardcode numbers in HTML - use `data-site` attributes for hydration

## Reports System
- JSON reports live in `reports/daily/`, `reports/weekly/`, `reports/comparison/`
- `reports-index.json` tracks every available report (type, date, time, file path, optional `format: "json"`)
- JSON reports are fetched and rendered natively in the page DOM using the site's design system (`.jr-report-body`, `.jr-trade-table`, etc.)
- Legacy HTML reports (email-template style, located in the same `reports/` subdirs) are loaded via `<iframe>` for backward compatibility
- Reports page is password-protected: SHA-256 hash comparison via `crypto.subtle.digest`, session persisted via `sessionStorage`. The page DOM is parsed as normal; an `.auth-overlay` element (`z-index:9999`, `inset:0`) visually blocks all content until the hash matches.

See `.claude/rules/reports.md` for the rendering contract and multi-view details.

## Scanning
- `scan.py` runs HTMLHint, ESLint (on extracted `<script>` blocks), Stylelint (on extracted `<style>` blocks), and Gitleaks
- Only scans `index.html` and `pipeline.html` (`reports.html` is not currently in the scan target list)
- Run before pushing to verify no new issues

## Git Workflow
- Feature branches for significant changes
- Minor fixes can commit directly to main
- GitHub Pages auto-deploys within 1-2 minutes of push to main
- The trading-bot repo pushes to this repo (site-updater writes `site-data.json`; reporting bot writes files under `reports/`)

## Excluded Files (.gitignore)
- `autobots-hero.html`, `architecture.html`, `notifications.html`, `playbook.html`, `security.html` (absorbed into `index.html`)
- `.claude/settings.local.json`
- `node_modules/`, `.DS_Store`, `*.log`

## Locked Sections (do not redesign)
- Hero animation and layout
- Architecture network graph
- Pipeline bubble burst intro, dissolve wipe outro, mouse-wheel navigation (trackpad handling was added on top; mouse behavior preserved)
- Security arc gauges
- Playbook scrolling cards
- Notifications hub layout
