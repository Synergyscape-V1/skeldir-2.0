# Skeldir Agent Decision Reference
## Runtime Intelligence for Zero-Interpretation Execution

This file is read by AI agents executing Skeldir interface tasks.
It resolves all ambiguity before code is written.

---

## DECISION TREE 1: What chart do I use?

Ask: **What decision must the user make from this data?**

```
User must RANK channels by performance?
  → Horizontal bar chart, sorted descending, channel colors from token map
  → NEVER: pie chart, donut chart

User must assess TREND over time?
  → Line chart with confidence band (mean ± bound shaded at 15% opacity)
  → NEVER: bar chart for time series, scatter plot

User must understand ATTRIBUTION composition (what % from which channel)?
  → Stacked area chart (over time) OR stacked horizontal bar (snapshot)
  → Segments colored by channel color tokens, deterministic order
  → NEVER: pie chart (angle perception too imprecise for financial decisions)

User must detect ANOMALY (is today unusual)?
  → Time series with control band (mean ± 2σ) shaded
  → Band color: channel color at 12% opacity
  → NEVER: plain line (no reference = no anomaly detection)

User must COMPARE two channels side by side?
  → Grouped bar chart OR dual-axis line (if time series)
  → Always show pre-calculated delta: "+$0.40 vs Google"
  → NEVER: show two numbers without pre-calculated comparison

User must ASSESS CONFIDENCE in a number?
  → ConfidenceBreath SVG component (see svg-system/svg-animations.tsx)
  → NEVER: just a color badge without range
  → NEVER: error bars without explanation

User is seeing DISCREPANCY between platform and verified?
  → DiscrepancyGap SVG component
  → MetricCard with platformClaim + verifiedValue + discrepancyPercent props
```

---

## DECISION TREE 2: What color do I use?

```
This element represents a CONFIDENCE LEVEL?
  → High:   --color-confidence-high   (#10D98C)
  → Medium: --color-confidence-medium (#F5A623)
  → Low:    --color-confidence-low    (#F04E4E)
  → Import: getConfidenceTokens(confidence) from design-tokens.ts

This element represents a SPECIFIC CHANNEL?
  → Use the deterministic channel color map: colors.channels[channelIndex]
  → Channel order is fixed: Meta(1), Google(2), TikTok(3), Email(4), Pinterest(5), LinkedIn(6), Other(7)
  → NEVER invent new channel colors; NEVER use brand blue for channels

This element is a PRIMARY ACTION (CTA, main button)?
  → --color-brand-primary (#3D7BF5)

This element is a REVENUE DISCREPANCY?
  → <5%:   --color-discrepancy-safe     (#10D98C)
  → 5-15%: --color-discrepancy-warning  (#F5A623)
  → >15%:  --color-discrepancy-critical (#F04E4E)
  → Import: getDiscrepancyTokens(percent) from design-tokens.ts

This is body text?
  → Primary text:   --color-text-primary   (#F0F4FF)
  → Secondary text: --color-text-secondary (#8B9AB8)
  → Muted/disabled: --color-text-muted     (#4A5568)

This is a background surface?
  → Page:    --color-bg-primary   (#0A0E1A)
  → Card:    --color-bg-secondary (#111827)
  → Nested:  --color-bg-tertiary  (#1F2937)
  → Elevated (modal/dropdown): --color-bg-elevated (#263244)

NEVER hardcode a hex value. NEVER use a color not in the token system.
```

---

## DECISION TREE 3: What font/size do I use?

```
This is a HEADING or SCREEN TITLE?
  → fontFamily: typography.fontHeading ('Syne')
  → Size: typography.scale.headingLg (24px) or headingMd (20px)

This is BODY COPY, LABEL, DESCRIPTION, TOOLTIP?
  → fontFamily: typography.fontBody ('IBM Plex Sans')
  → Size: bodyMd (14px) for labels, bodyLg (16px) for descriptions

This is a NUMERIC VALUE (ROAS, revenue, percentage, count)?
  → fontFamily: typography.fontData ('IBM Plex Mono')
  → Large metric: dataLg (36px), card secondary: dataMd (24px), table cell: dataSm (14px)
  → Tabular numerals are NON-NEGOTIABLE for all number columns

This is a PAGE-LEVEL DISPLAY (hero number, landing stat)?
  → fontFamily: typography.fontHeading ('Syne')
  → Size: displayLg (48px) or displayMd (36px)
```

---

## DECISION TREE 4: What animation do I use?

```
This component SHOWS LIVE POLLING DATA (metrics update every 30s)?
  → Add ConfidenceBreath SVG with isLive=true
  → On data update: set hasNewData=true → pulse fires → reset to false

This is a STATE TRANSITION (loading → ready, collapsed → expanded)?
  → Duration: motion.short (200ms)
  → Easing: cubic-bezier(0.4, 0, 0.2, 1)
  → Use transform/opacity ONLY (never width, height, max-height — causes reflow)

This is a MICRO INTERACTION (button press, toggle, checkbox)?
  → Duration: motion.micro (120ms)

This is a MODAL or PANEL opening?
  → Duration: motion.medium (300ms)
  → Entrance: transform: translateY(8px) → translateY(0) + opacity 0 → 1

This is a DESTRUCTIVE ACTION confirmation?
  → No animation on the destructive action itself (animation ≠ urgency)
  → Use static red border + confirmation text instead

There is NO user-facing state change communicated by this animation?
  → DELETE the animation. It is decoration and violates the motion axiom.

respects prefers-reduced-motion? ALWAYS:
  @media (prefers-reduced-motion: reduce) {
    * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
  }
```

---

## DECISION TREE 5: What empty state do I show?

```
Platform not connected yet?
  → emptyVariant: 'no-data-yet'
  → CTA: "Connect [Platform Name]" (specific platform if known)

Platform connected but <14 days of data?
  → emptyVariant: 'building-model'
  → Show ModelBuildingProgress SVG with currentDay value
  → NEVER show a generic spinner here — this is semantically significant

Platform connected, data exists, but filter returns nothing?
  → emptyVariant: 'no-results-filter'
  → CTA: "Clear Filters"
  → Show what filters are active

Feature requires higher tier?
  → emptyVariant: 'feature-locked'
  → CTA: "Upgrade to Agency"
  → State which plan includes this feature
```

---

## DECISION TREE 6: What error state do I show?

All error states MUST include:
1. What happened (specific, not "something went wrong")
2. Why it happened (root cause, one sentence)
3. What to do (action button with specific label)
4. Correlation ID (for support traces)

```
API timeout?
  → errorCopy.apiTimeout(correlationId) from copy-templates.ts
  → Primary action: "Retry" (if retryable: true)
  → Secondary action: "Report issue #{correlationId}"

OAuth connection failed?
  → errorCopy.oauthFailed(platformName) from copy-templates.ts
  → Primary action: "Try Again"
  → Secondary action: "Get Help"

Data gap (missing data for date range)?
  → errorCopy.dataGap(platform, dateRange) from copy-templates.ts
  → Render as WARNING banner, not blocking error
  → Show data that IS available; flag the gap

Tracking tag missing?
  → errorCopy.trackingTagMissing(missingPercent) from copy-templates.ts
  → Render as WARNING banner in Data Health screen
  → Primary action: "Fix Tracking Tag"
```

---

## DECISION TREE 7: Screen-level unforgettable element selection

Every screen must have exactly ONE unforgettable element:

```
Building Command Center Dashboard?
  → Ambient confidence glow: bgSecondary card has subtle box-shadow
    pulsing in the confidence color of the top-ranked metric
  → Implementation: read top metric's confidence → apply shadows.high/medium/low
    to the SummaryCardRow wrapper, 3s breathe animation

Building Channel Detail screen?
  → DataFlowPulse SVG: animated attribution flow from touchpoints to revenue
  → Position: below the MetricCard row, full width

Building Budget Optimizer?
  → Gaussian distribution overlay on scenario probability bars
  → Each scenario bar has a soft bell curve ghost above it in channel color

Building Onboarding (Revenue Source selection)?
  → Selected card emits radiating rings in brand blue (like a radar ping)
  → Other cards dim to 40% opacity when one is selected

Building Data Health screen?
  → ModelBuildingProgress ring: large, centered, with channel arc colors
  → OR: if model is built, show a "signal strength" indicator (4 bars, like WiFi)
```

---

## RULE: The Zero-Mental-Math Validation

Before declaring any screen/component complete, check every visible number:

```
For each displayed number, answer:
  Does the user need to compare it to anything? → Show pre-calculated delta
  Does the user need to contextualize it? → Show percentage change or vs-average
  Does the user need to trust it? → Show confidence badge + verification source
  Does the user need to act on it? → Show recommendation or CTA adjacent

If any answer is "yes" and the pre-calculation is absent → implement it.
Frontend must NEVER display raw numbers the user must interpret alone.
```

---

## ARCHITECTURE BOUNDARY ENFORCEMENT

```
✓ Frontend CAN:
  - Format pre-computed values (currency, percentage)
  - Sort/filter rendered data client-side (UX only)
  - Poll API on interval and re-render
  - Trigger async operations via API calls
  - Display confidence ranges provided by backend

✗ Frontend CANNOT:
  - Perform attribution calculations
  - Compute confidence intervals
  - Score channels or rank them algorithmically
  - Reconstruct user identity
  - Perform statistical operations of any kind

If you find yourself writing Math.* for statistical purposes in a React component,
you are violating the architecture. Move it to an API call.
```
