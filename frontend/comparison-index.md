# Comparative Storybook Index

## Purpose
Single aggregated Storybook instance for evaluating all five design-agent iterations of:
- Application Shell
- Command Center Dashboard
- Single Channel Detail
- Channel Comparison

## Run
```bash
npm install
npm run storybook
```

## Build
```bash
npm run ci:compare
```
Build output is emitted to `storybook-static/`.

## Story Groups
- `Compare/Overview`
- `Compare/Single Channel Detail Overview`
- `Compare/Channel Comparison/Compare All`
- `Channel Comparison/Compare All`
- `Agent A - Northstar Grid/Shell + CommandCenter`
- `Agent B - Signal Console/Shell + CommandCenter`
- `Agent C - Ledger Editorial/Shell + CommandCenter`
- `Agent D - Modular Atlas/Shell + CommandCenter`
- `Agent E - Atmos Field/Shell + CommandCenter`
- `Agent A - Northstar Grid/Shell + SingleChannelDetail`
- `Agent B - Signal Console/Shell + SingleChannelDetail`
- `Agent C - Ledger Editorial/Shell + SingleChannelDetail`
- `Agent D - Modular Atlas/Shell + SingleChannelDetail`
- `Agent E - Atmos Field/Shell + SingleChannelDetail`
- `Agent 1 / Minimal Geometric / Channel Comparison`
- `Agent 2 / Data-Forward Density / Channel Comparison`
- `Agent 3 / Editorial Luxury / Channel Comparison`
- `Agent 4 / Systematic Modularity / Channel Comparison`
- `Agent 5 / Atmospheric Technical / Channel Comparison`
- `Channel Comparison/Agent A - Clarity First`
- `Channel Comparison/Agent B - Data Density and Power Users`
- `Channel Comparison/Agent C - Confidence as Hero`
- `Channel Comparison/Agent D - Action-Forward`
- `Channel Comparison/Agent E - Canonical Fidelity`

## Required States per Agent
- `Ready`
- `Loading`
- `Empty`
- `Error`
- `PollingDegraded`

## Required Viewports
- Mobile 375x812
- Tablet 768x1024
- Desktop 1440x900

## Compare/Overview Controls
- Scenario selector
- Viewport selector
- Density zoom toggle (100%/90%)
- Dataset selector (`high`, `mixed`, `low`)

## Contract Checks
- Logo asset must exist at `public/assets/Final_Skeldir_Logo__No_wording_.png`
- Logo must be clickable to `/` with `aria-label="Skeldir home"`
- Shared fixtures are enforced through common story factory usage
