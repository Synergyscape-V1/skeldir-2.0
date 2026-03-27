# Solution Articulation Comparison Handoff

This folder contains the Storybook comparison handoff artifacts for ORCH-SOL-ART-003.

## Runbook

1. From `marketing/`, run `npm run storybook`.
2. Open the comparison grid: `http://localhost:6006/?path=/story/solutionarticulation-comparisongate--comparison-grid`.
3. Use the viewport addon to switch between:
- Desktop 1920
- Desktop 1440 (default)
- Desktop 1280
- Tablet 768
- Mobile 375
4. Open any agent focus story from the tile CTA to inspect live implementation + metadata + reference.

## Mounted implementation roots

- `public/implementations/reference/solution-articulation-final.jpg`
- `public/implementations/agent-a/`
- `public/implementations/agent-b/`
- `public/implementations/agent-c/`
- `public/implementations/agent-d/`
- `public/implementations/agent-e/`

## Validation

- Populate from run outputs with:
- `npm run populate:solution-iterations -- orchestration/problem-articulation/runs/run-2026-02-19-orch-sol-art-003`
- Validate file contract with:
- `npm run validate:solution-iterations`

## Notes

- Storybook renders each implementation in an iframe to prevent CSS cross-contamination.
- Evaluation and winner selection are intentionally out of scope for this package.
