# Single Channel Detail - Agent Deliverables Notes

## Shared Implementation Notes
- Route contract implemented as `/channels/:channelId` with date range query sync via `useSearchParams()`.
- Canonical channel detail types added in `src/types/channel.ts`.
- Snake_case -> camelCase transformation implemented in `transformChannelDetailResponse` (`src/mocks/channelDetailFixtures.ts`).
- Shared data hook/state machine implemented in `src/hooks/useChannelDetailData.ts`.
- Trend chart implemented with Recharts (`ComposedChart`) and chart-only updating overlay state.
- Actions row includes compare navigation and CSV export download behavior.

## Agent A - Northstar Grid (Evidence Through Precision)
- Revenue Verification: sparse split rows and oversized discrepancy hero with severity underline.
- Confidence Range: minimal number-line SVG with stroke weight confidence semantics.
- Chart: reduced visual noise and restrained axis density.
- Signature: discrepancy typography as first-read element.

## Agent B - Signal Console (Everything Visible, Nothing Hidden)
- Revenue Verification: compact three-column claimed/verified/delta treatment.
- Confidence Range: inline numeric expression and concise micro-explanation.
- Chart: denser marks with visible dots and full label context.
- Signature: contextualized numbers with adjacent comparators.

## Agent C - Ledger Editorial (The Verdict Page)
- Revenue Verification: verdict-led card with display-scale discrepancy headline and tinted wash.
- Confidence Range: explanatory prose elevated alongside numeric range.
- Chart: editorial rhythm, dominant revenue line, muted spend support line.
- Signature: typographic hierarchy conveys the verdict first.

## Agent D - Modular Atlas (Panel Architecture)
- Revenue Verification: modular parent/child panel composition with elevated delta panel.
- Confidence Range: segmented bar and nested explanation panel.
- Chart: contained panel treatment with modular boundaries and systemized spacing.
- Signature: visible panel hierarchy communicates information priority.

## Agent E - Atmos Field (Living Data)
- Revenue Verification: animated discrepancy gap as primary explanatory mechanism.
- Confidence Range: breathing interval behavior that reacts to confidence level.
- Chart: atmospheric confidence treatment with stronger dynamic tone.
- Signature: motion communicates certainty/uncertainty state, not ornament.
