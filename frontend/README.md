# Skeldir Comparative Storybook

Aggregated Storybook workspace for side-by-side comparison of five design-agent iterations of:
- Application Shell
- Command Center Dashboard
- Single Channel Detail
- Channel Comparison

## Quick Start
```bash
npm install
npm run storybook
```

## CI Build
```bash
npm run ci:compare
```

## Storybook Sprint 3
- `Compare/Channel Comparison/Compare All` is the unified 5/5 evaluation surface.
- Each agent has a Channel Comparison story group with 7 states: `Default`, `NoWinner`, `ThreeChannels`, `FourChannels`, `EmptyState`, `LoadingState`, `ErrorState`.

## Required Logo
Add this file before CI/build:

`public/assets/Final_Skeldir_Logo__No_wording_.png`
