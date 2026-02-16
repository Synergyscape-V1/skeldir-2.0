# A4-ATLAS Asset Attribution

## SVG Components

### EvidenceAccumulatorRing
- **Source:** Original creation for Skeldir
- **License:** Project-internal
- **Description:** 14-segment circular SVG ring encoding evidence accumulation. Each segment represents one day of the model's 14-day observation window.
- **Modifications:** N/A (original work)

## Icons

All icons sourced from [Lucide Icons](https://lucide.dev/):
- `Activity`, `HelpCircle` — shell status indicators
- `TrendingUp`, `TrendingDown`, `Minus` — metric trend indicators
- `AlertTriangle`, `AlertCircle`, `Info` — priority action severity
- `ArrowUpDown` — table sort affordance
- `RefreshCw`, `Plug`, `Clock`, `Radio`, `Lock` — state machine views
- **License:** ISC License
- **Modifications:** None — used as React components via `lucide-react`

## Fonts

- **Syne** (headings) — via CSS variables / Tailwind `font-sans`
- **IBM Plex Sans** (body) — via CSS variables / Tailwind `font-sans`
- **IBM Plex Mono** (data/numbers) — via CSS variables / Tailwind `font-mono`
- **License:** SIL Open Font License 1.1
- **Source:** Google Fonts

## Colors

All colors sourced from project token system via CSS custom properties:
- `--brand-tufts`, `--channel-*`, `--verified`, `--unverified`, `--destructive`
- Zero hardcoded hex/rgb values in component files.
