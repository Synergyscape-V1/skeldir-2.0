# A1-SENTINEL: Dense Control Room

## Design Rationale

### Target Persona

SENTINEL is optimized for **Persona A: The Agency Director** — a decision-maker with fragmented attention, under five minutes before the next context switch, whose primary question is: *"Is anything on fire?"*

This persona does not explore. They scan. They need every critical signal visible at first glance without hover, scroll, or click. The dense control room metaphor mirrors the operational environments this persona mentally models: an air traffic control center, a network operations dashboard, a trading floor terminal. Every pixel earns its place; there is no decorative whitespace.

### Time-to-Correct-Action Optimization

SENTINEL is architected to minimize the interval between page load and the user's first correct decision. The design achieves this through three mechanisms:

1. **Horizontal metric strips** replace tall card grids. Three compact strips stack vertically in under 120px of total height, each showing value + confidence + trend in a single scan line. The Agency Director reads left-to-right, top-to-bottom — exactly once — and knows the state of all three primary metrics in under 3 seconds.

2. **Priority actions as inline alert strips** sit directly between metrics and the channel table. They are severity-coded with left borders (red/amber/blue) and include quantified impact values inline. The director does not need to open a separate panel or navigate to a different section — the fire is visible the moment the metrics section ends.

3. **Channel performance table with default low-confidence-first sort** surfaces problems before successes. The director's eye hits the worst-performing channel first. Combined with channel color dots and inline confidence badges, a glance at the first two rows answers "Is anything on fire?" definitively.

The entire Command Center content fits above the fold at 1024px viewport height. No scrolling required for the 30-second daily check-in.

### Shell Metaphor: Top-Nav Command Bar + Utility Rail

The top-nav command bar eliminates the sidebar entirely. This is an intentional departure from the traditional admin dashboard layout. The rationale:

- **Horizontal navigation preserves vertical viewport** — in a data-dense interface, every vertical pixel is premium real estate. A sidebar (even collapsed at 64px) steals that space permanently. The 64px horizontal command bar is a fixed cost that does not grow with navigation items.
- **Icon + label buttons in a horizontal strip** allow the 6 navigation items to sit in the director's peripheral vision while they focus on the main content. Active-state highlighting uses a bottom border + primary tint, creating a "tab" metaphor that is instantly parseable.
- **The 48px utility rail** on the left edge provides tool-at-hand access (refresh, system status, notifications) without competing with primary navigation. These are operational tools, not navigation destinations — they belong in a separate visual channel.

On mobile (<1024px), the command bar nav collapses to a hamburger menu overlay and the utility rail hides completely. The mobile experience is necessarily simplified — the Agency Director persona rarely uses mobile for deep dashboard analysis (per Architecture Guide mobile use case analysis), so graceful degradation is appropriate.

### Motion Thesis: Radar Confidence Sweep

The RadarConfidenceSweep is SENTINEL's unforgettable element. It encodes a functional meaning:

- **Sweep angle = uncertainty width.** A narrow arc (72°) means high confidence — the model has converged, the posterior is tight. A wide arc (290°) means low confidence — the model is uncertain, the evidence is thin. This is not decorative rotation; it is a data-semantic animation.
- **Rotation speed maps to urgency.** High confidence rotates slowly (4000ms) — calm, vigilant, steady. Low confidence rotates faster (2000ms) — alert, scanning more frequently, reflecting the system's own uncertainty.
- **The 600ms pulse on data update** confirms "fresh data just arrived" without disrupting the reading flow. It's a momentary ring expansion from the center dot outward — visible in peripheral vision, gone before the next conscious glance.
- **prefers-reduced-motion** disables all rotation and reduces the sweep to a static arc indicator. The semantic information (arc angle = confidence) is preserved even without animation.

### Architecture Compliance

| Contract | Implementation |
|----------|---------------|
| Polling: 30s dashboard | `useSentinelPolling` wraps `usePollingManager` at 30,000ms |
| Polling: 5min channels | Second `usePollingManager` at 300,000ms |
| Silent updates | State update via setState spread, no status transition, no flicker |
| State machine | 4 states: loading (skeletons match ready dimensions), empty (4 variants), error (correlationId + retry), ready |
| No UI business logic | All values displayed as received. No `Math.*` in components. |
| Animated transitions | `useAnimatedValue` for smooth MetricStrip number changes |
| Navigation SSOT | All nav items from `src/config/nav.ts` NAV_ITEMS array |
| Token compliance | Zero hardcoded hex/rgb. All via Tailwind classes → CSS variables |
| Copy compliance | `formatConfidenceLabel` for closed vocabulary. No forbidden patterns. |
| Accessibility | ARIA landmarks, `aria-live="polite"`, focus rings, `prefers-reduced-motion` |

### Master Skill Section Citations

- **Part 0 (First-Principles Axioms):** Reduction of Implementation Entropy — exhaustive state machine, zero implicit states
- **Part 1 (Token System):** All colors via CSS variables, no hardcoded values
- **Part 2 (Typography):** Syne for headings, IBM Plex Sans for body, IBM Plex Mono for ALL data
- **Part 3 (Motion Tokens):** micro=120ms transitions, breathe=3000ms radar, pulse=600ms update
- **Part 4 (SVG-01 ConfidenceBreath):** RadarConfidenceSweep encodes Bayesian posterior width
- **Part 5 (Copy System):** Closed confidence vocabulary, forbidden pattern avoidance
- **Part 6 (Persona A):** Agency Director optimization — confidence visible without hover, P90 ≤1.5s
- **Part 8 (Anti-Pattern Registry):** No hardcoded hex, no pie charts, no AI-slop aesthetics
- **Part 9 (Psychological Load Audit):** One primary action per context, state preserved, no mental math
- **Part 10 (Unforgettable Element):** RadarConfidenceSweep = "the system is scanning, vigilant, active"
- **Part 11 (Architecture Boundary):** Frontend displays backend-provided values only
