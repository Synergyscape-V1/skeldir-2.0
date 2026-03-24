# Channel Comparison Multi-Agent Runbook

## Branch Topology
- `feat/channel-comparison/agent-a`
- `feat/channel-comparison/agent-b`
- `feat/channel-comparison/agent-c`
- `feat/channel-comparison/agent-d`
- `feat/channel-comparison/agent-e`
- `feat/channel-comparison/integration`

## Freeze Baseline
- Shared core contract under `src/channel-comparison/core/`.
- Shared renderer contract in `src/types/comparison.ts` (`ChannelComparisonRendererProps`).

## Agent Ownership
- Agent A: `src/channel-comparison/variants/agent-a/*`
- Agent B: `src/channel-comparison/variants/agent-b/*`
- Agent C: `src/channel-comparison/variants/agent-c/*`
- Agent D: `src/channel-comparison/variants/agent-d/*`
- Agent E: `src/channel-comparison/variants/agent-e/*`

## Integrator Ownership
- `src/comparison/AgentShellChannelComparison.tsx`
- `src/comparison/CompareChannelComparisonOverview.tsx`
- `src/stories/sharedChannelComparisonStoryFactory.tsx`
- `src/stories/compare-channel-comparison-overview.stories.tsx`
- `src/channel-comparison/evaluation/ChannelComparisonEvaluationPanel.tsx`

## Certification Command
```bash
npm run certify:channel-comparison
```

## Deliverables
- Iteration orientation note: `docs/channel-comparison-iteration-orientation.md`
- Certification report: `docs/channel-comparison-certification-report.md`
- Comparison scorecard: `docs/channel-comparison-comparison-scorecard.md`
