# Data Health Multi-Agent Runbook

## Branch Topology
- `feat/data-health/agent-a`
- `feat/data-health/agent-b`
- `feat/data-health/agent-c`
- `feat/data-health/agent-d`
- `feat/data-health/agent-e`
- `feat/data-health/integration`

## Freeze Baseline
- Frozen shared core is implemented under `src/data-health/core/`.
- Agent implementation contract is published in `docs/agent-implementation-kit.md`.

## Agent Ownership
- Agent A: `src/data-health/variants/agent-a/*`
- Agent B: `src/data-health/variants/agent-b/*`
- Agent C: `src/data-health/variants/agent-c/*`
- Agent D: `src/data-health/variants/agent-d/*`
- Agent E: `src/data-health/variants/agent-e/*`

## Integrator Ownership
- `src/comparison/AgentShellDataHealth.tsx`
- `src/comparison/CompareDataHealthOverview.tsx`
- `src/stories/sharedDataHealthStoryFactory.tsx`
- `src/stories/compare-data-health-overview.stories.tsx`

## Certification Command
```bash
npm run certify:data-health
```

## Deliverables
- Iteration orientation note: `docs/data-health-iteration-orientation.md`
- Certification report: `docs/data-health-certification-report.md`
- Comparison scorecard: `docs/data-health-comparison-scorecard.md`
