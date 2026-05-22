# Solution Articulation Storybook Comparison Gate

This folder defines the mandatory Storybook comparison gate for five distinct solution-articulation implementations.

## Files

- `SolutionArticulationFixtures.tsx`: mount paths, story IDs, and metadata typing.
- `SolutionArticulationComparison.stories.tsx`: sticky-reference comparison story + 5 focus stories with metadata panels.

## Required mounted paths

- `public/implementations/reference/solution-articulation-final.jpg`
- `public/implementations/agent-a/`
- `public/implementations/agent-b/`
- `public/implementations/agent-c/`
- `public/implementations/agent-d/`
- `public/implementations/agent-e/`

Each agent folder must contain:

- `index.html`
- `metadata.json`
- `screenshots/desktop-1440.png`
- `screenshots/tablet-768.png`
- `screenshots/mobile-375.png`

## Story IDs (stable)

- `solutionarticulation-comparisongate--comparison-grid`
- `solutionarticulation-comparisongate--agent-a-focus`
- `solutionarticulation-comparisongate--agent-b-focus`
- `solutionarticulation-comparisongate--agent-c-focus`
- `solutionarticulation-comparisongate--agent-d-focus`
- `solutionarticulation-comparisongate--agent-e-focus`

## Comparison behavior

- Reference image is rendered in a sticky header at the top of comparison view.
- Agent A-E render as live isolated iframes.
- Grid breakpoints: desktop `3x2`, tablet `2x3`, mobile `1x5`.
- Each agent tile links to its focus story.
- Focus stories include a metadata panel sourced from `/implementations/agent-x/metadata.json`.
- Missing metadata or reference assets render explicit diagnostics.
