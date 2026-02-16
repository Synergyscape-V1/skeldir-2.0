# Skeldir Master Skill
## Unified Production Interface Intelligence

**Version:** 1.0.0 | **Status:** Production-Ready Specification

---

## What This Is

This is not a collection of design guidelines. It is a **closed, operable system** — a set of
decisions already made, encoded as executable artifacts, that an AI agent or engineer can follow
without interpretation gaps.

The skill was synthesized from six source packages (senior-frontend, ux-researcher-designer,
visualization-expert, ui-ux-pro-max, frontend-ui-ux, content-design) and two Skeldir
specification documents. Every decision is traceable to an axiomatic truth from one of those
sources.

---

## Directory Structure

```
skeldir-master-skill/
│
├── SKILL.md                              ← Read this first. Master reference.
│   ├── Part 0: First-Principles Synthesis Map
│   ├── Part 1: Design Token System
│   ├── Part 2: Component Architecture
│   ├── Part 3: SVG Animation System
│   ├── Part 4: UX-Derived Component Logic
│   ├── Part 5: Visualization Decision Matrix
│   ├── Part 6: Content Design System
│   ├── Part 7: Agent Execution Protocol
│   ├── Part 8: Unforgettable Element Rules
│   └── Part 9: Anti-Pattern Registry
│
├── tokens/
│   └── design-tokens.ts                  ← Single source of truth: colors, type, spacing, motion
│
├── svg-system/
│   └── svg-animations.tsx                ← Functional motion primitives:
│                                            ConfidenceBreath, ModelBuildingProgress, DiscrepancyGap
│
├── copy-system/
│   └── copy-templates.ts                 ← All UI copy: empty states, errors, tooltips, CTAs
│
├── scripts/
│   └── skeldir_component_generator.py    ← Scaffolds components with correct contracts
│
└── references/
    └── agent-decision-reference.md       ← Runtime decision trees for AI agents
```

---

## How to Use

### For AI Agents Building Skeldir Components

1. Read `SKILL.md` Part 7 (Agent Execution Protocol) first
2. Consult `references/agent-decision-reference.md` for specific decisions
3. Import from `tokens/design-tokens.ts` — never hardcode values
4. Use SVG components from `svg-system/svg-animations.tsx` for live data
5. Source all copy from `copy-system/copy-templates.ts`
6. Scaffold new components: `python scripts/skeldir_component_generator.py ComponentName --type card`

### For Engineers Building Skeldir Screens

1. Every component needs all 4 states: loading, empty, error, ready
2. Every metric value uses `fontData` (IBM Plex Mono) — tabular numerals required
3. Color comes from token functions (`getConfidenceTokens`, `getDiscrepancyTokens`)
4. Copy comes from `copy-templates.ts` — fill variables, never write from scratch
5. Run Psychological Load Audit (SKILL.md Part 4.2) before merge

### For Design Reviews

Validate against Anti-Pattern Registry (SKILL.md Part 9).
Check Unforgettable Element Rules (SKILL.md Part 8) — every screen needs one.

---

## The Three Hardest Constraints

These are where teams consistently violate the architecture. Enforce them.

**1. Frontend never computes statistics.**
If you see `Math.` for anything statistical, it's a backend call disguised as frontend logic.

**2. Confidence level drives color automatically.**
Components don't receive a color prop. They receive a `confidence` prop and the color resolves
through `getConfidenceTokens()`. There are no exceptions.

**3. Users never calculate.**
Every number displayed must be pre-contextualized: delta shown, comparison shown, recommendation
adjacent. A raw number with no context is an interface defect, not a feature.

---

## Synthesis Decisions Log

| Decision | Chosen Option | Rejected Option | Reasoning |
|---|---|---|---|
| Dark vs. Light theme | Dark (#0A0E1A base) | Light (#FFFFFF base) | 11PM use scenario; confidence colors carry more semantic weight on dark surfaces |
| Heading font | Syne | Space Grotesk, Inter, Poppins | Geometric precision signals rigor; irregular details signal intelligence over bureaucracy |
| Body font | IBM Plex Sans | Open Sans, Nunito, System | Technical interface DNA; monospace cousin creates visual continuity with data values |
| Data font | IBM Plex Mono | Roboto Mono, JetBrains Mono | IBM Plex family cohesion; tabular figures prevent "dancing" numbers in polling updates |
| Confidence encoding | Color + range (both required) | Color badge alone | Badge alone allows uncalibrated color-blindness failure; range is the actual Bayesian quantity |
| Animation trigger | State change only | Decorative/constant | Every animation must answer: what state change does this communicate? |
| Empty state during model build | ModelBuildingProgress SVG | Generic spinner | "Building model" is semantically different from "loading" — it is evidence accumulating |
| Channel color assignment | Deterministic index map | Dynamic/random | Consistent channel colors across sessions = reduced cognitive load; users learn channel = color |
