---
name: skeldir-master-skill
description: |
  The unified production capability engine for Skeldir: a Bayesian marketing attribution SaaS.
  Synthesizes senior frontend engineering, UX research, data visualization, content design,
  and aesthetic intelligence into a single operable intelligence.
  
  Use this skill for ALL Skeldir interface work: component generation, design token decisions,
  SVG animation specification, copy writing, color palette selection, and architectural validation.
  
  Triggers: any Skeldir interface task — component, screen, design decision, copy, animation.
version: "1.0.0"
author: Skeldir Systems Synthesis
---

# Skeldir Master Skill
## The Unified Interface Intelligence for Bayesian Attribution SaaS

---

## PART 0: FIRST-PRINCIPLES SYNTHESIS MAP

Before executing any task, internalize these axiomatic truths extracted from each source package.
Every decision in this skill flows downstream from these.

| Source Package | Surface Description | Axiomatic Truth | How It Governs Skeldir |
|---|---|---|---|
| `senior-frontend` | React/TS components | **Reduction of Implementation Entropy** — every abstraction exists to minimize states-that-can-go-wrong | All components have explicit, exhaustive state machines. Zero implicit states. |
| `ux-researcher-designer` | Persona + journey | **Psychological Load Minimization** — users do not have spare cognitive bandwidth; steal none of it | Prop names, copy, and interaction patterns derived from documented user mental models (Agency Director, Marketing Manager) |
| `visualization-expert` | Chart selection | **Minimization of Inference Distance** — the gap between raw data and user action must be zero | Chart type selection is determined by what decision the user must make, not by data shape alone |
| `ui-ux-pro-max` | Design system | **Systematic Aesthetic Authority** — visual decisions are a closed set, not an open creative field | All colors, fonts, spacing are pre-resolved tokens. Agents pick from defined sets, never invent |
| `frontend-ui-ux` | Aesthetic execution | **Intentional Differentiation** — forgettable interfaces have zero business value | Every screen has one unforgettable visual signature element |
| `content-design` | UI copy | **Copy as Interface Architecture** — words are load-bearing structural elements, not decoration | Every label, error, empty state is specified. No placeholder copy survives to production |
| `Skeldir Architecture Doc` | Product spec | **Trust as Computed Property** — trust is not assumed; it is produced by specific UI mechanisms | Confidence signaling, revenue verification, explainability — these are not features, they are trust-computing functions |
| `Skeldir Design Spec` | Implementation contracts | **Zero-Interpretation Execution** — ambiguity between design and code is a defect class | Every component has a TypeScript interface contract. Agent never infers; it reads the contract |

**The Fusion Rule:** When any two axiomatic truths appear to conflict (e.g., "Vibrant" vs. "Precision Trust"), resolve by asking: **"Which choice reduces the user's time-to-correct-action?"** That answer wins.

---

## PART 1: DESIGN TOKEN SYSTEM — THE RESOLVED PALETTE

### 1.1 Color Architecture

Skeldir's color system is not aesthetic preference. It is a **semantic encoding layer** for statistical states.

#### The Bayesian Color Axiom
> Color encodes **epistemic state** (what we know and how confidently), not decoration.
> A user should be able to read statistical confidence from color alone, without reading text.

#### Primary Palette: "Deep Signal"

```css
/* tokens/colors.css */
:root {
  /* --- FOUNDATION --- */
  --color-bg-primary:    #0A0E1A;  /* Deep navy — the "void" from which data emerges */
  --color-bg-secondary:  #111827;  /* Card surfaces */
  --color-bg-tertiary:   #1F2937;  /* Nested content, hover states */
  --color-bg-elevated:   #263244;  /* Modals, dropdowns — feels "above" the surface */

  /* --- TEXT --- */
  --color-text-primary:   #F0F4FF;  /* Near-white with blue cast — readable, not harsh */
  --color-text-secondary: #8B9AB8;  /* Labels, metadata */
  --color-text-muted:     #4A5568;  /* Disabled, placeholders */
  --color-text-inverse:   #0A0E1A;  /* Text on bright backgrounds */

  /* --- BORDERS --- */
  --color-border-subtle:  rgba(139, 154, 184, 0.12);
  --color-border-default: rgba(139, 154, 184, 0.24);
  --color-border-strong:  rgba(139, 154, 184, 0.48);

  /* --- BRAND ACCENT --- */
  --color-brand-primary:  #3D7BF5;  /* Skeldir blue — primary CTAs, active nav */
  --color-brand-glow:     rgba(61, 123, 245, 0.20); /* Ambient glow for brand elements */

  /* --- BAYESIAN CONFIDENCE SPECTRUM (semantic, not decorative) --- */
  /* HIGH confidence: user can act now, data is solid */
  --color-confidence-high:       #10D98C;  /* Emerald — signal is strong */
  --color-confidence-high-bg:    rgba(16, 217, 140, 0.08);
  --color-confidence-high-border: rgba(16, 217, 140, 0.24);

  /* MEDIUM confidence: user should note uncertainty before acting */
  --color-confidence-medium:       #F5A623;  /* Amber — proceed with awareness */
  --color-confidence-medium-bg:    rgba(245, 166, 35, 0.08);
  --color-confidence-medium-border: rgba(245, 166, 35, 0.24);

  /* LOW confidence: more data needed before major budget decisions */
  --color-confidence-low:       #F04E4E;  /* Coral red — flag, don't block */
  --color-confidence-low-bg:    rgba(240, 78, 78, 0.08);
  --color-confidence-low-border: rgba(240, 78, 78, 0.24);

  /* --- DATA CHANNEL COLORS (7-channel max, WCAG accessible on dark bg) --- */
  /* These are the ONLY colors used in channel attribution charts */
  --color-channel-1: #3D7BF5;  /* Brand blue — usually Facebook/Meta */
  --color-channel-2: #10D98C;  /* Emerald — usually Google */
  --color-channel-3: #F5A623;  /* Amber — usually TikTok */
  --color-channel-4: #B36CF5;  /* Violet — usually Email */
  --color-channel-5: #F54E8B;  /* Rose — usually Pinterest */
  --color-channel-6: #36BFFA;  /* Sky — usually LinkedIn */
  --color-channel-7: #FB7C4C;  /* Coral — usually Other/Direct */
  /* If more than 7 channels: group remainder under --color-channel-7 as "Other" */

  /* --- FUNCTIONAL STATES --- */
  --color-success:    #10D98C;
  --color-warning:    #F5A623;
  --color-error:      #F04E4E;
  --color-info:       #3D7BF5;

  /* --- DISCREPANCY SEVERITY (revenue verification use only) --- */
  --color-discrepancy-safe:     #10D98C;  /* <5% — within noise floor */
  --color-discrepancy-warning:  #F5A623;  /* 5–15% — flag for review */
  --color-discrepancy-critical: #F04E4E;  /* >15% — requires investigation */
}
```

#### Why Dark Background?
**Defensible rationale:** Agency directors and marketing managers work across time zones, often at 11 PM (documented in Architecture doc "11 PM login scenario"). Dark backgrounds reduce photopic eye strain during extended night sessions. More critically, dark surfaces allow the confidence-spectrum colors (emerald, amber, red) to carry their full chromatic weight — on white backgrounds, these same colors lose 40% of their perceptual impact, degrading the semantic encoding system.

#### Typography Tokens

```typescript
// tokens/typography.ts
export const typography = {
  // HEADING FONT: Syne
  // Rationale: Syne is the analytical-premium intersection we need.
  // Its geometric precision signals rigor (statistical platform trust).
  // Its subtle irregularities signal intelligence over bureaucracy (vs. Poppins' corporate blankness).
  // NOT Space Grotesk (overused in tech), NOT Inter (too neutral), NOT Playfair (too editorial).
  fontHeading: "'Syne', sans-serif",

  // BODY FONT: IBM Plex Sans
  // Rationale: Designed for technical interfaces (IBM's design system).
  // Its monospace cousin (IBM Plex Mono) shares visual DNA — creates subliminal
  // continuity between prose text and data values without using mono everywhere.
  // Exceptional legibility at 12px (table data density requirement).
  fontBody: "'IBM Plex Sans', sans-serif",

  // NUMERIC/DATA FONT: IBM Plex Mono (for all metric values)
  // Rationale: Tabular numerals in monospace prevent number columns from "dancing"
  // as values update. Essential for live-polling revenue counters and ROAS tables.
  // Users read numbers differently than prose — different font = different cognitive mode.
  fontData: "'IBM Plex Mono', monospace",

  // TYPE SCALE (modular, ratio: 1.25 — Major Third)
  scale: {
    displayLg:  { size: '48px', weight: 700, lineHeight: 1.1, font: 'heading', tracking: '-0.02em' },
    displayMd:  { size: '36px', weight: 700, lineHeight: 1.15, font: 'heading', tracking: '-0.015em' },
    headingLg:  { size: '24px', weight: 600, lineHeight: 1.3, font: 'heading', tracking: '-0.01em' },
    headingMd:  { size: '20px', weight: 600, lineHeight: 1.4, font: 'heading', tracking: '-0.005em' },
    headingSm:  { size: '16px', weight: 600, lineHeight: 1.4, font: 'heading', tracking: '0' },
    bodyLg:     { size: '16px', weight: 400, lineHeight: 1.65, font: 'body', tracking: '0' },
    bodyMd:     { size: '14px', weight: 400, lineHeight: 1.6, font: 'body', tracking: '0' },
    bodySm:     { size: '12px', weight: 400, lineHeight: 1.5, font: 'body', tracking: '0.01em' },
    // DATA VARIANT — used for all metric values, table cells with numbers
    dataLg:     { size: '36px', weight: 600, lineHeight: 1.0, font: 'data', tracking: '-0.02em' },
    dataMd:     { size: '24px', weight: 600, lineHeight: 1.0, font: 'data', tracking: '-0.01em' },
    dataSm:     { size: '14px', weight: 500, lineHeight: 1.0, font: 'data', tracking: '0' },
    dataXs:     { size: '12px', weight: 400, lineHeight: 1.0, font: 'data', tracking: '0.01em' },
  },
} as const;
```

#### Spacing Tokens

```typescript
// tokens/spacing.ts — 4px base grid
export const spacing = {
  px: '1px',
  0.5: '2px',
  1:   '4px',
  1.5: '6px',
  2:   '8px',
  3:   '12px',
  4:   '16px',
  5:   '20px',
  6:   '24px',
  8:   '32px',
  10:  '40px',
  12:  '48px',
  16:  '64px',
  20:  '80px',
  24:  '96px',
} as const;

export const radius = {
  sm:   '4px',
  md:   '8px',
  lg:   '12px',
  xl:   '16px',
  full: '9999px',
} as const;
```

---

## PART 2: COMPONENT ARCHITECTURE — ENTROPY-MINIMIZED PATTERNS

### 2.1 The State Machine Imperative

**Rule:** Every Skeldir component that touches data MUST implement all four states explicitly.
No component is allowed to exist in an undefined visual state.

```typescript
// The Skeldir Component State Contract
type SkeldirComponentState = 
  | { status: 'loading' }                        // Skeleton/shimmer
  | { status: 'empty';  emptyVariant: EmptyVariant } // Contextual empty states
  | { status: 'error';  error: SkeldirError }    // Recoverable error with action
  | { status: 'ready';  data: unknown }          // Nominal operating state

type EmptyVariant = 
  | 'no-data-yet'        // Data pipeline not connected
  | 'building-model'     // Connected, insufficient history (<14 days)
  | 'no-results-filter'  // Connected, model exists, filter returns nothing
  | 'feature-locked'     // Tier restriction

type SkeldirError = {
  message: string;           // Human-readable, actionable
  correlationId: string;     // For support traces
  retryable: boolean;
  action?: { label: string; onClick: () => void };
}
```

### 2.2 Core Component Contracts

#### MetricCard — The Trust-Emitting Primitive

This is the most semantically loaded component in Skeldir. Every instance must compute trust.

```typescript
// components/MetricCard/MetricCard.types.ts

export interface MetricCardProps {
  // IDENTITY
  label: string;               // Short label: "Verified ROAS", "Ad Spend", "Revenue"
  labelTooltip?: string;       // "Why this metric?" — triggers explainability layer

  // VALUE (always pre-formatted — Zero Mental Math Principle)
  value: string;               // "$43,820" not "43820.44"
  valueTrend?: {
    displayText: string;       // "+$4.2K vs. last period"
    direction: 'up' | 'down' | 'flat';
    isPositive: boolean;       // Direction !== positivity (cost: down is good)
  };

  // BAYESIAN CONFIDENCE (drives color automatically — see rendering logic)
  confidence: 'high' | 'medium' | 'low';
  confidenceRange?: {
    low: string;               // "$38,500" — lower bound
    high: string;              // "$49,100" — upper bound
    percentMargin: number;     // ±12%
  };
  confidenceExplanation?: string; // "90 days of stable data with consistent CVR"

  // VERIFICATION (revenue verification use case)
  platformClaim?: string;      // "$52,300 claimed by Facebook"
  verifiedValue?: string;      // "$43,820 verified via Stripe"
  discrepancyPercent?: number; // Computed: auto-colored by severity thresholds

  // INTERACTION
  onClick?: () => void;        // Navigates to detail view
  isLoading?: boolean;
}
```

**Rendering Logic — Confidence-to-Color Binding:**

```typescript
// components/MetricCard/MetricCard.tsx
const confidenceConfig = {
  high:   { color: 'var(--color-confidence-high)',   bg: 'var(--color-confidence-high-bg)',   border: 'var(--color-confidence-high-border)',   label: '✓ High Confidence',  icon: HighConfidenceIcon },
  medium: { color: 'var(--color-confidence-medium)', bg: 'var(--color-confidence-medium-bg)', border: 'var(--color-confidence-medium-border)', label: '◐ Medium Confidence', icon: MediumConfidenceIcon },
  low:    { color: 'var(--color-confidence-low)',    bg: 'var(--color-confidence-low-bg)',    border: 'var(--color-confidence-low-border)',    label: '⚠ Low Confidence',   icon: LowConfidenceIcon },
} as const;
```

#### ConfidenceIntervalBar — The Living Uncertainty Visualizer

This component is Skeldir's most architecturally unique UI element. It replaces a single number with a **living range** that breathes as new data arrives.

```typescript
export interface ConfidenceIntervalBarProps {
  // Data
  pointEstimate: number;       // e.g. 3.2 (ROAS)
  lowerBound: number;          // e.g. 2.8
  upperBound: number;          // e.g. 3.8
  domainMin: number;           // Chart axis minimum
  domainMax: number;           // Chart axis maximum
  formatValue: (v: number) => string; // e.g. (v) => `$${v.toFixed(2)}`

  // Confidence state drives animation amplitude
  confidence: 'high' | 'medium' | 'low';

  // Animation (see SVG System in Part 3)
  isLive: boolean;             // When true, activates breathing animation
  lastUpdated?: Date;          // Drives pulse animation on update
}
```

#### ChannelPerformanceTable — Zero Mental Math Enforced

```typescript
export interface ChannelTableRow {
  channelId: string;
  channelName: string;
  channelColor: string;         // From channel color map, deterministic
  channelIcon: React.ReactNode; // SVG icon, never emoji

  // Pre-calculated (backend computes, frontend never calculates)
  verifiedRevenue: string;      // "$43,820"
  platformClaimedRevenue: string; // "$52,300"
  discrepancy: string;          // "-16%" — pre-formatted with sign
  discrepancyColor: string;     // Computed from severity thresholds

  roas: string;                 // "$3.20" — formatted with $ prefix
  roasVsAverage: string;        // "+$0.40 vs avg" — pre-calculated delta
  roasVsAverageDelta: 'above' | 'below' | 'at';

  adSpend: string;              // "$13,680"
  confidence: 'high' | 'medium' | 'low';
  lastUpdated: string;          // "2 minutes ago" — pre-formatted

  // Navigation
  detailPath: string;           // "/channels/facebook"
}

export interface ChannelPerformanceTableProps {
  rows: ChannelTableRow[];
  sortBy: ChannelSortField;
  onSortChange: (field: ChannelSortField) => void;
  onRowClick: (channelId: string) => void;
  state: SkeldirComponentState;
}

export type ChannelSortField = 'verifiedRevenue' | 'roas' | 'adSpend' | 'discrepancy' | 'confidence';
```

---

## PART 3: SVG ANIMATION SYSTEM — FUNCTIONAL MOTION

### 3.1 The Motion Axiom
> Animation in Skeldir is not decoration. Every animated element must answer:
> **"What state change or data insight does this motion communicate?"**
> If it cannot answer that question, the animation is deleted.

### 3.2 Animation Duration/Easing Standard

```typescript
// tokens/motion.ts
export const motion = {
  // MICRO (feedback — button press, toggle, checkbox)
  micro:     { duration: '120ms', easing: 'cubic-bezier(0.4, 0, 0.2, 1)' },
  // SHORT (component state transitions — skeleton → content)
  short:     { duration: '200ms', easing: 'cubic-bezier(0.4, 0, 0.2, 1)' },
  // MEDIUM (panel open/close, modal appear)
  medium:    { duration: '300ms', easing: 'cubic-bezier(0.4, 0, 0.6, 1)' },
  // LONG (page transitions, complex reveals)
  long:      { duration: '500ms', easing: 'cubic-bezier(0.4, 0, 0.2, 1)' },
  // BREATHE (living confidence interval — slow, biological, non-anxiety-inducing)
  breathe:   { duration: '3000ms', easing: 'cubic-bezier(0.45, 0, 0.55, 1)', iteration: 'infinite', direction: 'alternate' },
  // PULSE (data update notification — one-shot)
  pulse:     { duration: '600ms', easing: 'cubic-bezier(0, 0, 0.2, 1)', iteration: 1 },
} as const;
```

### 3.3 SVG Animation Catalog

Each SVG below has a **Bayesian semantic purpose** — it explains a statistical concept through motion.

---

#### SVG-01: ConfidenceBreath — The Living Interval

**Explains:** Bayesian posterior distribution width. Narrow = high confidence; wide = low confidence.
**Placement:** Within `ConfidenceIntervalBar` component. Also usable in empty states during model building.

```svg
<!-- SVG-01: ConfidenceBreath
  Props: confidence ('high'|'medium'|'low'), pointEstimate (0-1 normalized), isLive (bool)
  
  Behavior:
  - The central dot (point estimate) is fixed
  - The surrounding range area BREATHES — expands/contracts based on confidence level
  - HIGH confidence: barely moves (±3% amplitude)  
  - MEDIUM confidence: gentle swell (±10% amplitude)
  - LOW confidence: pronounced oscillation (±22% amplitude)
  - On data update: brief bright PULSE from center outward, then resumes breathing
-->
<svg viewBox="0 0 280 64" xmlns="http://www.w3.org/2000/svg" aria-label="Confidence interval visualization">
  <defs>
    <!-- Gradient: confidence → color mapped from prop -->
    <linearGradient id="ci-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%"   stop-color="var(--ci-color, #10D98C)" stop-opacity="0"/>
      <stop offset="35%"  stop-color="var(--ci-color, #10D98C)" stop-opacity="0.18"/>
      <stop offset="50%"  stop-color="var(--ci-color, #10D98C)" stop-opacity="0.35"/>
      <stop offset="65%"  stop-color="var(--ci-color, #10D98C)" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="var(--ci-color, #10D98C)" stop-opacity="0"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>

  <!-- Track: the full possible range baseline -->
  <rect x="16" y="30" width="248" height="2" rx="1" fill="var(--color-border-default)"/>

  <!-- Confidence range: breathing element (width/position driven by JS/CSS custom props) -->
  <rect 
    class="ci-range" 
    x="var(--ci-range-x, 70)" 
    y="22" 
    width="var(--ci-range-width, 140)" 
    height="18" 
    rx="9" 
    fill="url(#ci-gradient)"
    style="animation: ci-breathe var(--ci-breathe-duration, 3000ms) cubic-bezier(0.45,0,0.55,1) infinite alternate"
  />

  <!-- Bound markers -->
  <line class="ci-lower-marker" x1="var(--ci-lower-x, 70)" y1="20" x2="var(--ci-lower-x, 70)" y2="44" stroke="var(--ci-color, #10D98C)" stroke-width="1.5" stroke-opacity="0.5"/>
  <line class="ci-upper-marker" x1="var(--ci-upper-x, 210)" y1="20" x2="var(--ci-upper-x, 210)" y2="44" stroke="var(--ci-color, #10D98C)" stroke-width="1.5" stroke-opacity="0.5"/>

  <!-- Point estimate: fixed central dot with glow -->
  <circle class="ci-point" cx="var(--ci-point-x, 140)" cy="31" r="5" fill="var(--ci-color, #10D98C)" filter="url(#glow)"/>
  <circle class="ci-point-inner" cx="var(--ci-point-x, 140)" cy="31" r="2.5" fill="white"/>

  <!-- Update pulse: class toggled by JS on data refresh -->
  <circle class="ci-pulse" cx="var(--ci-point-x, 140)" cy="31" r="5" fill="none" stroke="var(--ci-color, #10D98C)" stroke-width="1.5"
    style="animation: ci-pulse-ring 600ms cubic-bezier(0,0,0.2,1) forwards; opacity: 0; transform-origin: center"/>
</svg>

<!--
CSS KEYFRAMES (inject into global stylesheet or component styles):
@keyframes ci-breathe {
  from { transform: scaleX(1);    opacity: 0.6; }
  to   { transform: scaleX(var(--ci-breathe-scale, 1.08)); opacity: 0.9; }
}
@keyframes ci-pulse-ring {
  0%   { transform: scale(1);   opacity: 0.8; }
  100% { transform: scale(4);   opacity: 0; }
}
-->
```

**Implementation Hook:**

```typescript
// hooks/useConfidenceAnimation.ts
export function useConfidenceAnimation(confidence: 'high' | 'medium' | 'low') {
  const config = {
    high:   { breatheScale: 1.02, breatheDuration: '4000ms', color: 'var(--color-confidence-high)'   },
    medium: { breatheScale: 1.10, breatheDuration: '2800ms', color: 'var(--color-confidence-medium)' },
    low:    { breatheScale: 1.22, breatheDuration: '2000ms', color: 'var(--color-confidence-low)'    },
  };
  return config[confidence];
}
```

---

#### SVG-02: DataFlowPulse — The Attribution Path Visualizer

**Explains:** How revenue is being attributed across channels. Used on Channel Detail screen.
**Semantic:** Shows money flowing from touchpoints to verified revenue — makes attribution tangible.

```typescript
// SVG-02 specification (render via React component)
// DataFlowPulse.tsx

interface DataFlowPulseProps {
  channels: Array<{
    id: string;
    name: string;
    color: string;    // From channel color map
    weight: number;   // Attribution weight 0–1
    spend: string;    // Formatted "$12,400"
  }>;
  verifiedRevenue: string;  // "$43,820"
  isAnimating: boolean;
}

// Visual: vertical lanes, one per channel, animated particles travel left→right
// Particle density proportional to attribution weight
// Particles converge at right side to "verified revenue" node
// Particle speed: 2s for high-weight channels, 3.5s for low-weight
// On confidence state change: particle color updates, brief sparkle at convergence node
```

---

#### SVG-03: ModelBuildingProgress — The Onboarding Intelligence Indicator

**Explains:** The 14-day data accumulation required before Bayesian model fires.
**Placement:** Empty state on Command Center while data is insufficient.
**Semantic:** Transforms "waiting" into "evidence accumulating" — reframes anxiety as progress.

```svg
<!-- SVG-03: ModelBuildingProgress
  Behavior: 
  - A circular "evidence accumulator" — like a watch face but filling with data
  - Each day of data = one segment lighting up
  - Segments glow in channel colors (data from multiple channels = multiple glowing arcs)
  - Center: shows "Day X of 14" in IBM Plex Mono
  - When all 14 segments lit: brief celebration pulse, then transitions to live dashboard
  - NEVER shows a generic spinner — this is semantically specific to the Bayesian concept
-->
```

---

#### SVG-04: DiscrepancyAlert — The Revenue Verification Signal

**Explains:** The gap between platform-claimed and Stripe-verified revenue.
**Placement:** MetricCard with verification data, Data Health screen.
**Semantic:** Makes invisible fraud/misattribution visible through motion.

```typescript
// SVG-04: Two converging bars (platform claim vs verified)
// When discrepancy > 15%: gap between bars pulses with --color-discrepancy-critical
// When discrepancy 5-15%: gap amber, no pulse (warning not alarm)
// When discrepancy < 5%: gap overlaps fully, static green — "aligned"
// The visual is designed so users understand the concept before reading the numbers
```

---

## PART 4: UX-DERIVED COMPONENT LOGIC

### 4.1 The Two Personas — Governing All Interaction Decisions

These are not marketing personas. They are **behavioral constraints** that govern prop values and interaction patterns.

#### Persona A: The Agency Director
- **Cognitive state at login:** Fragmented attention, <5 minutes before next context switch
- **Primary question:** "Is anything on fire?"
- **UI implication — derived prop requirements:**
  - `MetricCard.confidence` MUST be visible without hover — no tooltips required to see trust signal
  - `PriorityActionsSection` MUST load within P90 ≤ 1.5s — anything slower gets a skeleton that looks like a real card
  - `ChannelPerformanceTable` default sort = `confidence === 'low'` first — surface problems, not wins
  - Empty state copy: action-first, not empathetic-first ("Connect Facebook Ads" not "Let's get started!")

#### Persona B: The Marketing Manager
- **Cognitive state:** CFO asked a question 10 minutes ago; needs a defensible answer now
- **Primary question:** "Which number do I put in my presentation?"
- **UI implication — derived prop requirements:**
  - Every metric must have `confidenceExplanation` prop populated — the CFO will ask "how do you know?"
  - `MetricCard.valueTrend` MUST include `isPositive` (decoupled from direction) — cost metrics: down is good
  - Export button must be in viewport without scroll — this user copies numbers into slides
  - Error states must include `correlationId` — they will forward this to their developer

### 4.2 Psychological Load Audit — Before Every Component Release

Run this checklist on every new component:

```markdown
## Skeldir Psychological Load Audit

**Memory Load:**
- [ ] User does not need to remember information from a previous screen to operate this component
- [ ] All required context is visible in the component itself
- [ ] State is preserved if user navigates away and returns

**Decision Load:**
- [ ] Component presents maximum ONE primary action
- [ ] Secondary actions are visually subordinate (lower contrast, smaller)
- [ ] Default state is the correct action for 80% of users 80% of the time

**Inference Load:**
- [ ] User does not need to calculate anything (all comparisons pre-computed)
- [ ] Color meaning is explained on first encounter (tooltip or legend)
- [ ] Confidence terminology is consistent: always "High/Medium/Low", never synonyms

**Anxiety Load:**
- [ ] Error states are recoverable — always include action button
- [ ] Loading states communicate what is happening, not just that something is happening
- [ ] Destructive actions have confirmation with consequence preview
```

---

## PART 5: VISUALIZATION DECISION MATRIX

### 5.1 Chart Selection — Decision-First, Not Data-First

Select charts based on the **decision the user must make**, not the data shape.

| User Question | Decision | Correct Chart | Forbidden Chart | Rationale |
|---|---|---|---|---|
| "Which channel should get more budget?" | Rank comparison | Horizontal bar, sorted descending | Pie chart | Ranking requires length comparison; angle is imprecise |
| "Is my ROAS trending up?" | Trend assessment | Line chart with confidence band | Bar chart | Temporal continuity requires continuous encoding |
| "How much of my revenue came from each channel?" | Attribution composition | Stacked area (over time) OR horizontal stacked bar (snapshot) | Donut chart | Attribution is partial and uncertain — stacking shows the whole |
| "Is today's performance unusual?" | Anomaly detection | Time series with control bands (mean ± 2σ shaded) | Simple line | Without the band, users cannot assess "normal" |
| "Should I trust this number?" | Confidence assessment | `ConfidenceIntervalBar` (custom, see Part 3) | Any point estimate chart | This is the Skeldir-specific chart type; deploy it aggressively |
| "What's the discrepancy between channels?" | Divergence comparison | Diverging bar chart from zero baseline | Grouped bars | Diverging bars make +/- immediately readable |

### 5.2 Data-Density-Driven Color Palette Rule

When data density is high (>5 channels, >90 days, >50 rows), **reduce color usage** — do not increase it.
High data density = more neutral backgrounds, fewer accent colors, more whitespace.

```typescript
// hooks/useChartDensity.ts
export type DensityLevel = 'sparse' | 'moderate' | 'dense';

export function getDensityLevel(params: {
  channelCount: number;
  dayRange: number;
  rowCount?: number;
}): DensityLevel {
  const score = (
    (params.channelCount > 5 ? 2 : params.channelCount > 3 ? 1 : 0) +
    (params.dayRange > 90 ? 2 : params.dayRange > 30 ? 1 : 0) +
    ((params.rowCount ?? 0) > 50 ? 2 : (params.rowCount ?? 0) > 20 ? 1 : 0)
  );
  if (score >= 4) return 'dense';
  if (score >= 2) return 'moderate';
  return 'sparse';
}

// Dense: use 2 accent colors max, increase border opacity, reduce glow effects
// Moderate: standard token set
// Sparse: enable glows, wider confidence intervals, more saturated accents
```

---

## PART 6: CONTENT DESIGN SYSTEM

### 6.1 Copy Axioms

1. **Lead with outcome, append context.** "ROAS improved 16%" not "We noticed your ROAS metric has changed"
2. **Quantify everything that can be quantified.** "40% of pages missing tag" not "some pages missing tag"
3. **Confidence terminology is a closed vocabulary.** Use ONLY: "High Confidence", "Medium Confidence", "Low Confidence". Never: "likely", "probably", "approximately", "around", "roughly"
4. **Never anthropomorphize the algorithm.** "The model shows" not "Skeldir thinks" or "our AI believes"
5. **Error messages must contain:** what happened + why + exactly what to do next

### 6.2 Copy Templates by Surface

```typescript
// copy/templates.ts

export const copy = {
  confidence: {
    high:   'High Confidence · ±{margin}%',
    medium: 'Medium Confidence · ±{margin}%',
    low:    'Low Confidence · ±{margin}% — more data needed',
  },

  discrepancy: {
    safe:     'Within noise floor (±{percent}%)',
    warning:  '{percent}% discrepancy — review source data',
    critical: '{percent}% discrepancy — investigate before decisions',
  },

  emptyStates: {
    noDataYet:      'Connect your first platform to begin attribution modeling.',
    buildingModel:  'Day {current} of 14 — accumulating evidence for your first model.',
    noResultFilter: 'No channels match this filter. Adjust range or clear filters.',
    featureLocked:  'Available on Agency plan. {upgradeLink}',
  },

  errors: {
    apiTimeout:  'Dashboard timed out loading. Your data is safe. [Retry] [Report issue #{correlationId}]',
    oauthFailed: 'Connection to {platform} failed. Check permissions in your {platform} Business Account. [Try Again] [Get Help]',
    dataGap:     '{platform} data missing for {dateRange}. Attribution for this period shows wider confidence ranges.',
  },

  actions: {
    primary: {
      connectPlatform: 'Connect {platformName}',
      approveBudget:   'Approve Budget Shift',
      viewDetail:      'View {channelName} Analysis',
      exportReport:    'Export Report',
    },
    secondary: {
      whyThisNumber:  'Why this range?',
      seeTransactions: 'See {count} transactions',
      learnMore:       'How attribution works',
      connectLater:    'Connect Later',
    },
  },

  tooltips: {
    roas:       'Revenue attributed to this channel per $1 spent. Calculated using Bayesian posterior mean, verified against {revenueSource} transactions.',
    confidence: 'Model certainty based on {days} days of data and {conversionCount} conversions. High = ±10%, Medium = ±25%, Low = ±50%.',
    discrepancy: 'Difference between what {platform} claims as revenue and what {revenueSource} recorded in the same period.',
  },
} as const;
```

### 6.3 Forbidden Copy Patterns

```typescript
// Never use these patterns in Skeldir UI
const FORBIDDEN_COPY = [
  "Get started",           // Replace with specific first action
  "Something went wrong",  // Replace with what specifically went wrong
  "Loading...",            // Replace with what is loading
  "No data found",         // Replace with why and what to do
  "Invalid input",         // Replace with what is invalid and valid format
  "Are you sure?",         // Replace with consequence: "Remove Facebook? Attribution data for this channel will be deleted."
  "AI thinks",             // Anthropomorphizes — replace with "The model shows"
  "Probably",              // Vague — replace with confidence level
  "We're working on it",   // Replace with specific ETA or status
] as const;
```

---

## PART 7: AGENT EXECUTION PROTOCOL

When an AI agent uses this skill to build a Skeldir interface, it MUST follow this sequence:

### Step 1: Classify the Task

```
Is this a new SCREEN? → Read Part 2 (state machine), Part 4 (persona audit), Part 5 (charts)
Is this a new COMPONENT? → Read Part 2 (contracts), Part 6 (copy)
Is this a DESIGN DECISION? → Read Part 1 (tokens), Part 3 (motion), Part 5 (visualization)
Is this COPY? → Read Part 6 exclusively
```

### Step 2: Resolve Color/Motion Before Writing Code

1. Identify the confidence state(s) this component can be in
2. Map confidence → color token (never hardcode hex)
3. Determine if live polling is involved → if yes, add `ConfidenceBreath` animation
4. Check data density → apply density rule from Part 5.2
5. Select chart type from Part 5.1 decision matrix BEFORE writing chart code

### Step 3: Write TypeScript Interface First

The interface contract is the spec. Code without an interface contract is unauthorized.

```typescript
// REQUIRED pattern — always define interface before implementation
interface [ComponentName]Props {
  // All props must have JSDoc explaining their semantic purpose
  // No prop named 'data' — always name by what the data IS
  // No prop named 'type' — always name by what the type SELECTS
}
```

### Step 4: Implement State Machine

```typescript
// REQUIRED pattern — no component skips this
const [ComponentName]: React.FC<[ComponentName]Props> = (props) => {
  if (props.state.status === 'loading') return <[ComponentName]Skeleton />;
  if (props.state.status === 'error')   return <ErrorState {...props.state.error} />;
  if (props.state.status === 'empty')   return <EmptyState variant={props.state.emptyVariant} />;
  // Nominal render — props.state.status === 'ready'
  return <[ComponentName]Ready {...props} />;
};
```

### Step 5: Apply Psychological Load Audit (Part 4.2)

Run the checklist. If any item fails, fix before declaring component complete.

### Step 6: Write Copy from Templates

Use Part 6 templates. Fill in all variables. No placeholder copy.

---

## PART 8: THE UNFORGETTABLE ELEMENT — SCREEN SIGNATURE RULES

Every screen must have ONE visually unforgettable element that:
1. Is unique to that screen (not repeated on other screens)
2. Encodes a statistical or product concept through form
3. Cannot be mistaken for decoration

| Screen | Unforgettable Element | Concept It Encodes |
|---|---|---|
| Command Center | `ConfidenceBreath` ambient background glow — pulses subtly in the confidence color of the top metric | The platform is live, polling, and thinking |
| Channel Detail | `DataFlowPulse` attribution river — animated particles showing money attribution in real time | Attribution is not static; it updates with every transaction |
| Budget Optimizer | Scenario probability bars with gaussian curve overlays — each scenario shows its distribution | Budget optimization is probabilistic, not deterministic |
| Data Health | `ModelBuildingProgress` ring — fills as evidence accumulates | Bayesian models require evidence, not just data |
| Onboarding (Step 2) | Revenue source selection cards with radiating "truth signal" glow on selection | One truth source is architecturally enforced, not a preference |

---

## PART 9: ANTI-PATTERN REGISTRY

These are confirmed failure modes, derived from competitor analysis and the Skeldir product spec.

```typescript
const ANTI_PATTERNS = {
  visual: [
    'Using confidence badge color without range display — users cannot calibrate to a badge alone',
    'Pie/donut charts for attribution — angle perception is too imprecise for financial decisions',
    'Inline calculations shown to users (e.g., showing subtracted ROAS values) — violates Zero Mental Math',
    'Purple gradients on white — immediately reads as "AI slop", destroys premium positioning',
    'Generic stock photography — destroys technical credibility',
    'Emoji icons — replace with SVG icons from the icon system',
    'Solid color backgrounds — always use layered depth (gradient, noise, or subtle grid)',
  ],
  engineering: [
    'Business logic in React components — frontend is a window, backend is the brain',
    'Hardcoded color hex values — always use design tokens',
    'Components without explicit loading/error/empty states — implicit states are defects',
    'any types on confidence or state — these are the load-bearing types of the system',
    'Synchronous chat UIs for financial decisions — Skeldir is async review-and-approve only',
    'Client-side attribution math of any kind — attribution is computed exclusively in backend',
  ],
  copy: [
    '"Get started" — replace with first action',
    'Synonym variation for confidence levels — use only High/Medium/Low',
    'Anthropomorphizing the algorithm — "The model shows" not "Skeldir thinks"',
    'Vague error messages — always: what happened + why + what to do',
    'Missing correlationId on error states — support team cannot debug without it',
  ],
} as const;
```

---

## QUICK REFERENCE: TOKEN INDEX

| Token | Value | Use When |
|---|---|---|
| `--color-confidence-high` | `#10D98C` | Confidence badge, CI bar, passing data health |
| `--color-confidence-medium` | `#F5A623` | Medium confidence badge, caution states |
| `--color-confidence-low` | `#F04E4E` | Low confidence badge, data gap warnings |
| `--color-brand-primary` | `#3D7BF5` | CTAs, active nav, interactive elements |
| `--color-bg-primary` | `#0A0E1A` | Page background |
| `--color-bg-secondary` | `#111827` | Card backgrounds |
| `fontHeading` | Syne | All headings, display text |
| `fontBody` | IBM Plex Sans | Body copy, labels, descriptions |
| `fontData` | IBM Plex Mono | All numeric metric values |
| `motion.breathe` | 3000ms alternate infinite | Live confidence intervals |
| `motion.pulse` | 600ms one-shot | Data update flash |
| `motion.short` | 200ms ease | State transitions |
