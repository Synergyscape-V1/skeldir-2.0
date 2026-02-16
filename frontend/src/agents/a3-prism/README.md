# A3-PRISM: Adaptive Cockpit

## Design Rationale

### Target Persona

PRISM serves both personas simultaneously. The **Agency Director** gets priority actions in the always-visible left panel — never scrolled away, never hidden behind a tab. The **Marketing Manager** gets the full metric cards and channel table in the resizable right panel, with enough space to cross-reference numbers.

### Time-to-Correct-Action Optimization

PRISM's split-pane architecture reduces time-to-correct-action through persistent context:

1. **Priority actions never disappear.** In SENTINEL and MERIDIAN, priority actions compete for vertical space with metrics and the channel table. In PRISM, they occupy the left panel permanently. The director's eye can check the left panel in peripheral vision while the right panel shows detailed data. Two information channels, zero scrolling.

2. **Resizable split = user-controlled density.** The director who wants more alert space drags the divider right. The manager who wants more table space drags it left. The split position persists across sessions. The interface adapts to the user, not the other way around.

3. **ConvergenceGapBars inside metric cards** make verification status visible inline. Each metric card shows two bars converging — platform-reported vs. Skeldir-verified. The gap width directly encodes uncertainty. The director sees "these bars don't touch" and knows the number needs investigation. No hover tooltip, no click-through — the visual gap IS the signal.

### Shell Metaphor: Split-Pane Cockpit

The cockpit metaphor is borrowed from aviation: a primary flight display (right panel) and a navigation/alerting display (left panel). The pilot — the Agency Director — monitors both simultaneously but focuses attention based on urgency.

The resizable divider (shadcn `ResizableHandle`) includes a visible grip indicator, making the split point discoverable. On mobile (<1024px), the layout linearizes — the left panel's priority actions appear inline in the main flow, and the resizable split is replaced by standard vertical scrolling.

### Motion Thesis: Convergence Gap Bars

The ConvergenceGapBars are PRISM's unforgettable element. They encode verification convergence as a physical visual metaphor:

- Two bars start separated (load animation, 800ms) and slide toward each other
- Gap width = `(1 - confidence/100) * maxGap` — direct data encoding
- High confidence (>80): bars overlap completely, single solid bar — "aligned"
- Medium (50-80): small gap, amber tint in gap space — "check this"
- Low (<50): pronounced gap with breathing red glow (3000ms cycle) — "investigate"
- On data update: bars briefly separate and re-converge (600ms pulse)

The bars also appear in miniature (120px wide) within each channel table row, so every channel's verification status is visible at a glance. This creates a coherent visual language: the same convergence metaphor at three scales (overview indicator, metric card, table row).

Under `prefers-reduced-motion`, bars render at their final position without animation. The gap width still encodes confidence.

### Architecture Compliance

| Contract | Implementation |
|----------|---------------|
| Polling 30s / 5min | `usePrismPolling` wraps `usePollingManager` |
| Silent updates | State spread, no flicker |
| State machine | All 4 states, 4 empty variants |
| No business logic | Values as received |
| Nav SSOT | `NAV_ITEMS` drives both panels |
| Token compliance | Zero hardcoded hex |
| Accessibility | ARIA landmarks, focus rings, reduced-motion |

### Master Skill Citations

- Part 0: Reduction of Implementation Entropy — exhaustive state machine
- Part 1: Token System — all colors via CSS variables
- Part 3: Motion — convergence 800ms, breathe 3000ms, pulse 600ms
- Part 4: SVG-03 DiscrepancyGap — adapted as ConvergenceGapBars
- Part 6: Both personas — left panel for Director, right panel for Manager
- Part 7: Visualization matrix — no pie charts, bar comparison for ranking
- Part 8: Anti-patterns — no hardcoded hex, no decorative animation
- Part 11: Architecture boundary — frontend displays backend values only
