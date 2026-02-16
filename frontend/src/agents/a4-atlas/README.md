# A4-ATLAS: Card-First Scannable Grid

## Design Rationale

### Target Persona

ATLAS optimizes for both **Persona A (Agency Director)** and **Persona B (Marketing Manager)** through a card-based information architecture. The Agency Director scans card headings top-to-bottom: revenue card, channels card, model confidence card — three fixation points, three answers. The Marketing Manager drills into each card's detail: the channel table card supports sorting and comparison, the priority action cards surface severity with quantified impact.

The card metaphor borrows from cartographic atlases: each card is a "page" of the atlas, a self-contained unit of information that can be read independently. You don't need to read the whole atlas to find what you need — you flip to the relevant page. ATLAS brings this mental model to the Command Center.

### Time-to-Correct-Action Optimization

ATLAS achieves rapid time-to-correct-action through three design choices:

1. **Everything is a scannable card.** No component shares visual boundaries with another. Each metric, each priority action, each data table occupies its own card with consistent padding and clear separation. The Agency Director's eyes follow a grid-scan pattern: left-to-right across the metric cards row, then down to priority action cards, then to the channel table card. Consistent card sizing means the scan pattern never breaks.

2. **Floating icon rail minimizes chrome.** The 56px translucent rail auto-hides on scroll down and reappears on scroll up. When the director is scanning data, navigation chrome disappears entirely — 100% of the viewport is data cards. When they need to navigate, a single upward scroll gesture brings the rail back. This isn't a gimmick; it's a deliberate trade: navigation accessibility vs. data viewport real estate, weighted toward data because the primary use case is scanning, not navigating.

3. **Status ribbon as ambient awareness.** The 32px top ribbon provides system health and timestamp without occupying a full header bar. "System nominal" in green plus a real-time clock gives the director instant confidence that what they're seeing is current and trustworthy, using only 32 pixels of vertical space.

### Shell Metaphor: Floating Rail + Status Ribbon

The ATLAS shell eliminates both the traditional sidebar and the full-width header. Instead:

- **32px status ribbon** at the top edge: system health indicator, real-time clock, help button, user avatar. This is the minimal header — it earns its 32px by providing always-visible temporal and system context.
- **56px floating icon rail** on the left: translucent (bg-card/80 + backdrop-blur), positioned fixed, auto-hides on scroll-down via scroll direction detection. Six nav icons with active-state highlighting (primary tint + left border accent). On hover, each icon shows its label via the `title` attribute.
- **Mobile (<1024px):** The floating rail transforms into a bottom tab bar (14px tall icons + 9px labels). The status ribbon remains at top. This matches mobile OS navigation conventions — tab bars are thumb-reachable, side rails are not.

The auto-hide behavior uses a scroll direction comparator: `scrollTop < lastScrollTop` means scrolling up, which reveals the rail. `scrollTop > lastScrollTop` hides it. The transition is 300ms ease-in-out via Tailwind's `transition-transform`. Passive scroll listeners ensure zero jank.

### Motion Thesis: Evidence Accumulator Ring

The EvidenceAccumulatorRing is ATLAS's unforgettable element. It encodes a functional meaning that no static element can communicate:

- **14 arc segments** represent the model's 14-day observation window. Each segment = 1 day of evidence.
- **Filled segments** use `var(--brand-tufts)` with a drop-shadow glow. Empty segments use `var(--muted)` at low opacity. The visual ratio of filled-to-empty instantly communicates how much evidence the model has accumulated.
- **Center text** displays "Day X of 14" in font-mono, providing the exact number for those who need precision beyond the visual ratio.
- **Breathing animation** (scale 1.0 → 1.02, 3000ms sinusoidal cycle) communicates "the system is alive, evidence is accumulating." The amplitude is subtle enough to register in peripheral vision without demanding focal attention.
- **Data update pulse** (500ms): when new evidence arrives, the newest segment animates its fill from 0 to 1, while the ring briefly scales to 1.04 then returns to the breathing cycle. This confirms "new data just arrived" without disrupting the reading flow.
- **prefers-reduced-motion:** All animation disabled. Ring renders at static final state. Segment fill states still encode the same information — the ring remains fully functional as a data visualization even without motion.

The ring's semantic density is its key differentiator: it simultaneously encodes three dimensions of information (evidence quantity, evidence freshness, system liveness) in a single 80px circular element.

### Architecture Compliance

| Contract | Implementation |
|----------|---------------|
| Polling 30s / 5min | `useAtlasPolling` wraps `usePollingManager` |
| Silent updates | State spread, no flicker |
| State machine | All 4 states, 4 empty variants |
| No business logic | Values as received |
| Nav SSOT | `NAV_ITEMS` drives floating rail + mobile tabs |
| Token compliance | Zero hardcoded hex |
| Accessibility | ARIA landmarks, focus rings, reduced-motion |

### Master Skill Citations

- Part 0: Reduction of Implementation Entropy — exhaustive state machine, zero implicit states
- Part 1: Token System — all colors via CSS variables, no hardcoded values
- Part 2: Typography — Syne headings, IBM Plex Sans body, IBM Plex Mono for ALL numbers
- Part 3: Motion — breathe=3000ms ring, pulse=500ms segment fill, micro=120ms transitions
- Part 4: SVG-03 EvidenceAccumulator — 14-segment ring encodes observation window progress
- Part 6: Both personas — card-first scan for Director, sortable detail for Manager
- Part 7: Visualization — no pie charts, evidence ring for model state
- Part 8: Anti-patterns — no hardcoded hex, no decorative animation, no AI-slop aesthetics
- Part 10: Unforgettable Element — EvidenceAccumulatorRing = "the model is learning, evidence is accumulating"
- Part 11: Architecture Boundary — frontend displays backend values only
