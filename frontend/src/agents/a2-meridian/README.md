# A2-MERIDIAN: Spacious Executive Brief

## Design Rationale

### Target Persona

MERIDIAN optimizes for **Persona A: The Agency Director** during their 30-second daily check-in at 11 PM. The core question: *"Is anything on fire?"* — answered by large, scannable numbers visible from arm's length.

Unlike SENTINEL's dense control room, MERIDIAN bets on the insight that cognitive load decreases when visual noise decreases. The Agency Director at 11 PM has depleted attention. They need three numbers, three trends, and zero effort to parse them. MERIDIAN gives each metric an entire card with 48px display typography — the value is visible before conscious reading begins.

### Time-to-Correct-Action Optimization

MERIDIAN reduces time-to-correct-action through typographic dominance:

1. **48px metric values** in IBM Plex Mono create an instant visual hierarchy. The director's eye lands on the number before the label. At desktop width, all three metrics sit above the fold in a single row — total revenue, active channels, model confidence. Three glances. Three answers. Under 5 seconds.

2. **Priority actions in a dedicated card** with severity left borders create a clear "attention gradient" — red/amber/blue from critical to info. The card sits between metrics and the channel table, forcing the director's gaze through it. Impact values are quantified inline so the director knows the magnitude without clicking.

3. **Channel table below the fold by design.** The 30-second check-in does not require channel-level detail. If a priority action references a channel problem, the action links directly to it. The table exists for the occasional deep-dive, not the daily scan.

### Shell Metaphor: Grouped Sidebar with Executive Header

The full-height sidebar with grouped navigation sections mirrors the information architecture explicitly:

- **Operations** (Command Center, Channels, Budget) — the daily workflow
- **Intelligence** (Data, Investigations) — the occasional analysis
- **Administration** (Settings) — the rare configuration

This grouping reduces cognitive mapping. The director does not need to remember which icon means what — the section labels provide context. The sidebar collapses to icon-only (64px) for users who internalize the layout, preserving horizontal space.

The header is deliberately minimal: just the current page name (breadcrumb-style), timestamp, and avatar. No logo duplication (it's in the sidebar). No search bar (this is a monitoring tool, not a search product). No notification badges (priority actions handle alerting).

### Motion Thesis: Breathing Horizon Glow

The BreathingHorizonGlow is MERIDIAN's unforgettable element — a full-width SVG gradient bar positioned behind the metric cards that gently oscillates opacity between 0.05 and 0.15 over a 3000ms breathe cycle.

This encodes a functional semantic: **the platform is alive**. Data is flowing. The Bayesian models are updating. The gradient intensity maps to confidence — higher confidence produces a more visible glow, lower confidence dims it. The director perceives this subconsciously: a bright, calm glow means "things are healthy." A dim, barely-visible glow means "data is thin."

On data update (30s polling cycle), the glow briefly pulses to 0.3 opacity over 600ms, then resumes breathing. This confirms "fresh data just arrived" without disrupting the reading flow. The cross-fade on metric card values (250ms) ensures smooth number transitions with zero layout shift.

Under `prefers-reduced-motion`, the glow holds at a static 0.1 opacity. The semantic information is still present (gradient intensity = confidence) but without the animation.

### Architecture Compliance

| Contract | Implementation |
|----------|---------------|
| Polling 30s | `useMeridianPolling` → `usePollingManager(30000)` |
| Polling 5min | Second `usePollingManager(300000)` for channels |
| Silent updates | State spread, no status transition, cross-fade values |
| State machine | loading / empty(4) / error(correlationId+retry) / ready |
| No business logic | Values displayed as received, no Math.* |
| Animated values | `useAnimatedValue` for MetricCard numbers |
| Nav SSOT | NAV_ITEMS grouped into Operations/Intelligence/Administration |
| Token compliance | Zero hardcoded hex. All via Tailwind → CSS variables |
| Copy compliance | `formatConfidenceLabel`, no forbidden patterns |
| Accessibility | ARIA landmarks, aria-live, focus rings, reduced-motion |

### Master Skill Citations

- Part 0: Psychological Load Minimization — spacious layout reduces visual noise
- Part 1: Token System — all colors via CSS variables
- Part 2: Typography — 48px display-font for metrics, font-mono for all data
- Part 3: Motion — breathe=3000ms, pulse=600ms, cross-fade=250ms
- Part 4: SVG-01 ConfidenceBreath — BreathingHorizonGlow encodes data freshness
- Part 5: Copy System — closed vocabulary, no forbidden patterns
- Part 6: Persona A — large values visible without hover, priority actions prominent
- Part 8: Anti-patterns — no hardcoded hex, no decorative animation
- Part 10: Unforgettable element — BreathingHorizonGlow = "the platform is alive"
