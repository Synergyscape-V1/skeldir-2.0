import type { Meta, StoryObj } from "@storybook/react";
import {
  platformIntegrationsArgTypes,
  platformIntegrationsDefaultArgs,
  CompareAllPlatformIntegrationsView,
} from "./sharedPlatformIntegrationsStoryFactory";
import type { PlatformIntegrationsStoryArgs } from "./sharedPlatformIntegrationsStoryFactory";

const meta: Meta<PlatformIntegrationsStoryArgs> = {
  title: "Platform Integrations/Compare All",
  args: platformIntegrationsDefaultArgs,
  argTypes: platformIntegrationsArgTypes as Meta<PlatformIntegrationsStoryArgs>["argTypes"],
  parameters: {
    docs: {
      description: {
        component: [
          "## Platform Integrations — 5-Agent Design Sprint Comparison",
          "",
          "| Agent | Paradigm | Hypothesis |",
          "|-------|----------|------------|",
          "| **A — Minimalist Data Density** | Linear / Vercel | Max info per viewport with zero noise = faster comprehension |",
          "| **B — Status-First Hierarchy** | PagerDuty / Datadog | Pre-attentive color + icon processing = glance triage in <1.5s |",
          "| **C — Progressive Disclosure** | Notion / Linear | Minimal default + expand-on-demand = lower cognitive load |",
          "| **D — Command Console** | GitHub Actions / AWS | Table/list hybrid outperforms card grids for 6+ integrations |",
          "| **E — Trust-Signal Centered** | Grafana / Monte Carlo | Data freshness as primary signal builds attribution trust |",
          "",
          "Use the controls to toggle scenario and UI state across all five agents simultaneously.",
        ].join("\n"),
      },
    },
  },
};

export default meta;

export const Overview: StoryObj<PlatformIntegrationsStoryArgs> = {
  render: (args) => CompareAllPlatformIntegrationsView(args),
};
