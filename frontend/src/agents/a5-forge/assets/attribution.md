# A5-FORGE Asset Attribution

## SVG Components

### PulseCascadeIndicator
- **Source:** Original creation for Skeldir
- **License:** Project-internal
- **Description:** Segmented horizontal cascade indicator. On poll completion, segments flash sequentially (50ms stagger, 300ms per segment) to confirm data freshness. Encodes "data just arrived and propagated through the pipeline."
- **Modifications:** N/A (original work)

## Icons

All icons sourced from [Lucide Icons](https://lucide.dev/):
- `Anvil` — shell brand icon (forge metaphor)
- `Activity`, `Wifi`, `WifiOff` — status bar indicators
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
