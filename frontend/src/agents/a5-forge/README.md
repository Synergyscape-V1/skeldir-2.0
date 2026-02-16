# A5-FORGE: Data-Forward Tabular Workspace

## Design Rationale

### Target Persona

FORGE is optimized for **Persona B: The Marketing Manager** — a practitioner who lives in spreadsheets, who trusts numbers over visualizations, and whose primary question is: *"Which channels are performing and which need intervention?"* This persona wants to see every number, compare across rows, sort by any column, and identify outliers instantly.

While the Agency Director gets fast answers from the compressed metrics strip, FORGE's true power is its tabular density. The channel performance table is the primary visual element — it gets maximum vertical space, prominent positioning, and the most sophisticated interaction model (multi-column sort with visual state).

### Time-to-Correct-Action Optimization

FORGE minimizes time-to-correct-action through radical prioritization of tabular data:

1. **Metrics compressed to a single strip.** Three metrics occupy a single 48px horizontal bar with inline values, trends, and confidence margins. This is intentionally compressed — FORGE treats metrics as context headers, not primary content. The Marketing Manager glances at the strip to confirm overall trajectory, then focuses on the table below.

2. **Channel table as primary visual element.** Unlike other designs where the table is one of several peer components, in FORGE the table dominates. It receives maximum vertical space, sits directly below the metrics strip, and uses low-confidence-first default sort to surface problems immediately. Low-confidence rows get a subtle background tint (destructive/5) — the manager's eye naturally gravitates to colored rows.

3. **Priority actions as inline tabular rows.** Rather than cards or panels, priority actions are rendered as severity-coded horizontal rows — consistent with FORGE's tabular philosophy. Each row has an icon, title, affected channel badge, and quantified impact. The visual language is the same as the channel table: scan top-to-bottom, read left-to-right.

4. **No chrome competition.** The tab bar provides navigation without stealing vertical space. The status bar at the bottom provides ambient system health. Between these two 28-48px strips, every pixel belongs to data.

### Shell Metaphor: Tabbed Workspace + Status Bar

FORGE borrows from industrial monitoring software and IDE layouts:

- **48px header** at top: brand icon (Anvil — the forge metaphor), product name "FORGE" in tight tracking, user avatar. No breadcrumbs, no timestamps in the header — those belong in the status bar.
- **48px tab bar** below the header: six navigation items styled as workspace tabs. Active tab has a bottom border in primary color with subtle primary/5 background. Tabs include both icon and label for immediate readability. The bottom-border tab pattern is universally understood and requires zero learning.
- **28px status bar** at bottom edge: system connection status (Wifi icon + "Connected"), polling status ("Polling active"), and real-time clock in font-mono. This is the forge's instrument panel — always visible, always current, never demanding attention.
- **Mobile (<768px):** Tab bar moves to bottom of screen (above the status bar) as a standard mobile tab bar. Labels are truncated to icons + short labels at 9px.

The overall vertical budget: 48px header + 48px tabs + 28px status = 124px of chrome, leaving the remaining viewport for pure data content.

### Motion Thesis: Pulse Cascade Indicator

The PulseCascadeIndicator is FORGE's signature element. It communicates data freshness through a sequential wave pattern:

- **16 horizontal segments** arranged in a 3px-tall bar spanning the full content width, positioned between the header and the data content.
- **On each 30-second poll completion**, segments flash sequentially from left to right. Each segment activates 50ms after the previous one, creating a wave that travels across the indicator in ~800ms total.
- **Active segments** briefly show `var(--brand-tufts)` at 80% opacity, then fade back to muted. The wave confirms "data just arrived and propagated through every metric."
- **The cascade metaphor** evokes a forge's production line: raw data enters on the left, gets processed through each station, and emerges as verified metrics on the right. Each segment lighting up represents a processing stage completing.
- **prefers-reduced-motion:** Only the first segment flashes (single 300ms pulse), no cascade. Data freshness is still communicated, just without the sequential motion.

The cascade is deliberately subtle — a 3px-tall bar cannot demand attention. But in the Marketing Manager's peripheral vision, the left-to-right wave provides continuous confirmation that the system is active and data is current.

### Architecture Compliance

| Contract | Implementation |
|----------|---------------|
| Polling 30s / 5min | `useForgePolling` wraps `usePollingManager` |
| Silent updates | State spread, no flicker |
| State machine | All 4 states, 4 empty variants |
| No business logic | Values as received |
| Nav SSOT | `NAV_ITEMS` drives tab bar |
| Token compliance | Zero hardcoded hex |
| Accessibility | ARIA landmarks, focus rings, reduced-motion, aria-live |

### Master Skill Citations

- Part 0: Reduction of Implementation Entropy — exhaustive state machine, zero implicit states
- Part 1: Token System — all colors via CSS variables, no hardcoded values
- Part 2: Typography — Syne headings, IBM Plex Sans body, IBM Plex Mono for ALL numbers/data
- Part 3: Motion — cascade stagger 50ms, segment flash 300ms, total ~800ms
- Part 4: SVG-02 cascade pattern — PulseCascadeIndicator sequential activation
- Part 5: Copy System — closed confidence vocabulary, no forbidden patterns
- Part 6: Persona B — Marketing Manager optimization, table-first design
- Part 7: Visualization — no pie charts, tabular presentation for comparison tasks
- Part 8: Anti-patterns — no hardcoded hex, no decorative animation, all motion encodes data
- Part 9: Psychological Load — single scan direction (top-to-bottom), no competing panels
- Part 10: Unforgettable Element — PulseCascadeIndicator = "data flows through the forge"
- Part 11: Architecture Boundary — frontend displays backend values only
