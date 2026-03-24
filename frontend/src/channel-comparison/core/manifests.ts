import type { ChannelComparisonValidationGateResult, ChannelComparisonVariantManifest } from "../../types/comparison";

function baseValidation(): ChannelComparisonValidationGateResult[] {
  return [
    { key: "spatial", label: "SPATIAL", pass: true, evidence: "" },
    { key: "typography", label: "TYPOGRAPHY", pass: true, evidence: "" },
    { key: "logos", label: "LOGOS", pass: true, evidence: "24px in panel headers, 20px in chips/selector via platformMeta()." },
    { key: "color", label: "COLOR", pass: true, evidence: "All color values reference tokens.css custom properties." },
    { key: "confidence", label: "CONFIDENCE", pass: true, evidence: "" },
    { key: "deltaLabels", label: "DELTA LABELS", pass: true, evidence: "All deltas pre-computed via buildDerivedMetrics(); displayed inline." },
    { key: "states", label: "STATES", pass: true, evidence: "Empty/loading/populated/error-panel/error-global implemented." },
    { key: "accessibility", label: "ACCESSIBILITY", pass: true, evidence: "" },
    { key: "responsiveness", label: "RESPONSIVENESS", pass: true, evidence: "CSS media queries at 1023px and 767px breakpoints." },
    { key: "dataContract", label: "DATA CONTRACT", pass: true, evidence: "Mock data matches Spec_03 ComparisonChannelData schema." },
  ];
}

function withEvidence(overrides: Partial<Record<string, string>>): ChannelComparisonValidationGateResult[] {
  return baseValidation().map((gate) => ({
    ...gate,
    evidence: overrides[gate.key] ?? gate.evidence,
  }));
}

export const CHANNEL_COMPARISON_MANIFESTS: ChannelComparisonVariantManifest[] = [
  {
    agentId: "A",
    hypothesis:
      "Maximum cognitive clarity through aggressive hierarchy, whitespace, and clinical reduction of visual complexity. Minimal treatment paradoxically increases trust.",
    keyDecisions: [
      "Replaced ChannelCards with ClarityHeroMetrics — oversized 48px ROAS numbers in horizontal strip.",
      "Replaced ConfidenceRangeFigure with ClarityConfidenceStrip — minimal 6px bars, no chart frame.",
      "WinnerBanner restyled to understated centered text with thin border separators.",
      "Revenue chart rendered borderless, floating in whitespace.",
      "Budget recommendation stripped to simple text line + blue CTA.",
      "Max-width 960px centered container for controlled reading width.",
    ],
    specInterpretations: [
      "Confidence tiers communicated via subtle background tints (6% opacity) on hero cells.",
      "All borders and box-shadows removed except functional separators.",
    ],
    validation: withEvidence({
      spatial: "Hero metrics horizontal strip; max-width 960px centered; generous spacing-xxl gaps.",
      typography: "ROAS uses display-lg (48px/600); labels use body-sm uppercase; secondary metrics body-sm.",
      confidence: "Tier-colored background tints (green/amber/red at 6% opacity) on hero cells; 6px bars tier-colored.",
      accessibility: "role='article' on hero cells; role='figure' on confidence strip; aria-label on remove buttons.",
    }),
  },
  {
    agentId: "B",
    hypothesis:
      "Power users arriving at 11 PM with a client deliverable need maximum information per pixel and single eye-movement scanning.",
    keyDecisions: [
      "Replaced ChannelCards+DenseMatrix with unified DenseComparisonTable — all metrics in one table.",
      "Replaced ConfidenceRangeFigure with CompactConfidenceOverlay — SVG-based 60px strip with overlap hatching.",
      "12px base font, 8px cell padding, no border-radius — pure data density.",
      "Winner banner reduced to single compact line.",
      "Revenue chart height reduced to 180px.",
      "First column sticky on mobile for horizontal scroll.",
    ],
    specInterpretations: [
      "Zero Mental Math maintained: every numeric cell shows inline delta label.",
      "Confidence level cells marked with colored left-border (3px) for glance-able tier identification.",
    ],
    validation: withEvidence({
      spatial: "Single unified table; 0px border-radius; minimal padding; 180px chart height.",
      typography: "12px base; 10px metric labels; 13px bold values; 11px delta labels.",
      confidence: "SVG overlapping rectangles with hatched overlap zone; 3px tier border on confidence cells.",
      accessibility: "role='table' on DenseComparisonTable; aria-label on remove buttons; sticky first column preserves readability.",
    }),
  },
  {
    agentId: "C",
    hypothesis:
      "Confidence (not ROAS) is the visual anchor. The interface should make uncertainty the first thing users encounter.",
    keyDecisions: [
      "ConfidenceHeroBanner replaces both ConfidenceRangeFigure and WinnerBanner — large SVG with overlapping bands.",
      "Channels grouped by confidence tier (High/Medium/Low) instead of selection order.",
      "Dark theme (slate-900 background) creates editorial, analytical feel.",
      "Diamond markers on SVG for point estimates; tier-colored bands (green/amber/red).",
      "Budget banner prefixed with 'Based on confidence analysis:' to reinforce confidence-first narrative.",
      "Mobile fallback: vertical tier-colored rows replace SVG.",
    ],
    specInterpretations: [
      "Winner determination derived from SVG overlap visualization, not separate banner.",
      "Tier grouping reorders channels from spec's selection-order to confidence-order.",
    ],
    validation: withEvidence({
      spatial: "Full-width SVG hero (200px+); tier-grouped cards below; dark slate-900 background.",
      typography: "Heading-md for hero title; body-sm uppercase tier headers; heading-sm card metrics.",
      confidence: "SVG bands colored by tier (green/amber/red); hatched overlap zones; diamond markers; tier-grouped cards.",
      accessibility: "role='figure' on SVG; role='article' on tier cards; focus-visible rings on dark background.",
    }),
  },
  {
    agentId: "D",
    hypothesis:
      "Budget recommendation and winner are the most economically consequential elements. An action-forward design pulls them to maximum prominence.",
    keyDecisions: [
      "DecisionHero card dominates viewport — combines winner + budget recommendation in one block.",
      "EvidenceAccordion uses native <details>/<summary> for zero-JS accordion with built-in a11y.",
      "SecondaryActionBar repeats CTA as sticky bottom bar (IntersectionObserver-driven).",
      "Decision hero gradient: green when winner exists, amber when not.",
      "All metrics demoted to accordion evidence sections — action first, data second.",
      "Prominent 14px-padded CTA button in primary blue.",
    ],
    specInterpretations: [
      "Progressive disclosure: recommendation → evidence. Inverts spec's typical data-first flow.",
      "CTA duplicated in hero and sticky bar for maximum commitment surface area.",
    ],
    validation: withEvidence({
      spatial: "Full-width decision hero; 2-column inner grid; accordion sections with 4px left rail.",
      typography: "Heading-lg for winner name; 11px uppercase labels; body-md detail text.",
      confidence: "Confidence tier description displayed in budget lift text; hero gradient reflects winner state.",
      accessibility: "role='status' on decision hero; native <details>/<summary> provides keyboard accordion; sticky bar conditionally visible.",
    }),
  },
  {
    agentId: "E",
    hypothesis:
      "Highest quality comes from faithful canonical execution of the supplied spec and reference screenshot with flawless micro-interactions.",
    keyDecisions: [
      "Composition matches reference: WinnerBanner → ChannelCards (3-col) → ConfidenceRange → DenseMatrix → RevenueChart → BudgetBanner.",
      "Entrance animations: fade+slide-up with staggered 100ms delay per card.",
      "Enhanced skeleton loading with smoother gradient and varied line heights.",
      "Alternating row tints and hover highlights on DenseMatrix.",
      "All shared components reused — differentiation is entirely CSS polish.",
      "Box shadows, border-radius, and transitions on every interactive element.",
    ],
    specInterpretations: [
      "Conservative: no reordering, no novel visualizations — trust the spec design.",
      "Loading states extend spec skeleton pattern with smoother 1.4s ease-in-out animation.",
    ],
    validation: withEvidence({
      spatial: "3-column card grid; stacked sections matching reference screenshot order; 10px border-radius.",
      typography: "Heading-lg for page title; heading-sm section titles; body-sm uppercase labels with letter-spacing.",
      confidence: "Reuses shared ConfidenceRangeFigure with polished 12px track height and 20px markers.",
      accessibility: "Inherits all shared component ARIA roles; focus-visible with 4px offset; staggered animations use prefers-reduced-motion.",
    }),
  },
];
