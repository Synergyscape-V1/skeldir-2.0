# Problem Articulation Iteration Review

## Mandatory Phase 8: Storybook Comparison Deployment

This phase is required after all five agent outputs are complete and before archive.

### Inputs

- `public/implementations/agent-a/`
- `public/implementations/agent-b/`
- `public/implementations/agent-c/`
- `public/implementations/agent-d/`
- `public/implementations/agent-e/`
- `public/implementations/reference/solution-articulation-final.jpg`

### Actions

1. Populate normalized static mounts under `public/implementations/`.
2. Launch Storybook.
3. Verify `ComparisonGrid` and each agent focus story route.
4. Confirm every tile renders and each `Open Agent [X] Focus` action navigates correctly.

### Run Storybook

```bash
npm run storybook -- --port 6006 --host 0.0.0.0
```

## Story Routes

- Home: `http://localhost:6006/`
- Comparison Grid: `http://localhost:6006/?path=/story/solutionarticulation-comparisongate--comparison-grid`
- Agent A Focus: `http://localhost:6006/?path=/story/solutionarticulation-comparisongate--agent-a-focus`
- Agent B Focus: `http://localhost:6006/?path=/story/solutionarticulation-comparisongate--agent-b-focus`
- Agent C Focus: `http://localhost:6006/?path=/story/solutionarticulation-comparisongate--agent-c-focus`
- Agent D Focus: `http://localhost:6006/?path=/story/solutionarticulation-comparisongate--agent-d-focus`
- Agent E Focus: `http://localhost:6006/?path=/story/solutionarticulation-comparisongate--agent-e-focus`

## Completion Gate

- Grid shows six tiles in fixed order: Reference, Agent A, Agent B, Agent C, Agent D, Agent E.
- Reference is pinned in grid.
- All five agent tiles are clickable to focus stories.
- Archive is blocked until the Storybook gate passes.

## Risk Handling Addendum

- If one or more tiles fail to render:
  - Block archive.
  - Rebuild static mounts in `public/implementations/`.
  - Re-run Storybook health check.
  - On second failure, isolate failing tile and use last valid artifact snapshot with failure log.
- If tile action does not navigate:
  - Block archive.
  - Fix story ID mapping.
  - Re-run route interaction check.
  - If unresolved, publish temporary explicit deep-link panel and mark non-final.

## Files

- Iterations: `src/components/layout/iterations/`
- Story (legacy): `src/stories/posthero/ProblemStatementComparison.stories.tsx`
- Story (new): `src/stories/solution-articulation/SolutionArticulationComparison.stories.tsx`
- Fixtures: `src/stories/solution-articulation/SolutionArticulationFixtures.tsx`
- Story README: `src/stories/solution-articulation/README.md`
- Directive: `orchestration/problem-articulation/agent-directive.md`
- Rubric: `orchestration/problem-articulation/evaluation/rubric.md`
- Comparison artifacts: `orchestration/problem-articulation/comparisons/`
