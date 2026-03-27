# Evaluation Rubric (Locked Pre-Review)

| Dimension | Points | Evidence |
|---|---:|---|
| Structural fidelity to reference | 20 | Storybook visual review + DOM checks |
| Chart fidelity (bars/labels/order/annotations) | 25 | Side-by-side against reference |
| Copy/text fidelity | 15 | String-level comparison |
| Typography/spacing hierarchy | 10 | Computed style sampling |
| Color fidelity | 10 | Pixel/color checks |
| Responsive integrity | 10 | Storybook viewport switch |
| Scope discipline (no out-of-scope edits) | 5 | git diff audit |
| Build/lint pass | 5 | Command output |

## Acceptance Rules
- Minimum acceptance threshold: 85
- Disqualifiers:
  - touched out-of-scope sections
  - missing core chart/callout/bullet elements
  - build failure

## Tie-breakers
1. Higher Chart fidelity score
2. Higher Structural fidelity score
3. Smaller unrelated diff
