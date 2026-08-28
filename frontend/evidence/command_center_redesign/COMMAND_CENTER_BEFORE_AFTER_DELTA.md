# Command Center Before / After Delta

Reference baseline: `evidence/command_center_baseline/COMMAND_CENTER_BASELINE_DELTA.md`

| Defect / Hypothesis | Baseline | After redesign |
|---------------------|----------|----------------|
| S0-01 raw `Comparable_to_previous_value=false` | Leaked in priority copy | **Eliminated** — `benchmarkTransitionExplanation` canonical copy |
| S0-02 claimed revenue authority | bps-only, no metadata | **Eliminated** — `PlatformClaimLabel` on claimed column |
| H-RD-01 token aliases | Undefined `--color-bg-card`, gaps collapsed | **Eliminated** — alias layer + canonical `--sk-*` usage |
| H-RD-02 shell brand / nav | Placeholder icons, App frame active | **Eliminated** — `ShellBrand`, `NavIcon`, `/app` → command-center |
| H-RD-03 header band | Missing bell, urgency, humanized time | **Eliminated** — `NotificationBell`, urgency marker, `formatRelativeUpdatedTime` |
| H-RD-04 summary cards | No trends/drill-downs, weak typography | **Eliminated** — H2 metrics (24px computed), trends, drill-down links |
| H-RD-05 priority violation | Internal variable copy | **Eliminated** |
| Trend visualization | Table | **Replaced** — `VerifiedRevenueChart` SVG line chart |
| Discrepancy display | bps-only | **Replaced** — percent + `DiscrepancyBadge` |
| Bayesian/benchmark columns | Inconsistent plain text | **Unified** — badge components |
| Grid ratio ~19/81 | Imbalanced | **Balanced** — 464px / 464px at 1280, gap 24px |
| Mobile overflow | scrollWidth 436 @ 375 | **Fixed** — scrollWidth 375 @ 375 |
| Timestamp | Machine ISO with seconds | **Fixed** — relative "Updated just now" |

Semantic invariants preserved: commerce owns verified revenue; platform claims labeled; policy authority on actions; UI does not invent truth.
