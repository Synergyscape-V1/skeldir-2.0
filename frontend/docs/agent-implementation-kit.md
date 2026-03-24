# Data Health Agent Implementation Kit

## Frozen Interface Contract

```ts
interface DataHealthRendererProps {
  state: DataHealthState;
  scenario: "good" | "warning" | "critical";
  onRefresh: () => Promise<void> | void;
  onNavigateToIntegrations: () => void;
  onRetry: () => Promise<void> | void;
}
```

## Required State Behavior
- `initial_loading`: render skeleton only.
- `error`: render error card with retry action.
- `no_data`: render empty state with route to `/data/integrations`.
- `steady`: render complete dashboard (header, score, metrics, issues, fix guides).

## Required Functional Checks
- Score gauge color maps: healthy->success, warning->warning, critical->error.
- Metric cards: status-driven left border colors.
- Issue groups: Critical expanded by default; Warning and Info collapsed.
- Fix guide affordance hidden for zero-step guides.
- Stale warning banner appears when `lastUpdated > 24h` and supports refresh.

## Accessibility Checklist
- All interactive elements keyboard reachable.
- `aria-expanded` and region relationships for issue sections.
- Focus-visible treatment on buttons/links.
- Interactive touch targets >= 44x44px.

## Story Args Contract
- `scenario`: good | warning | critical
- `uiState`: steady | initial_loading | error | no_data
- `stale`: boolean
- `density`: 90 | 100
