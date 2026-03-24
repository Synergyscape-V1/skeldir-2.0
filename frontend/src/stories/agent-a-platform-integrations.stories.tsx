import type { Meta } from "@storybook/react";
import { AgentShellPlatformIntegrations } from "../comparison/AgentShellPlatformIntegrations";
import { AGENTS } from "../comparison/agents";
import {
  platformIntegrationsArgTypes,
  platformIntegrationsDefaultArgs,
  type PlatformIntegrationsStoryArgs,
} from "./sharedPlatformIntegrationsStoryFactory";

const theme = AGENTS.find((candidate) => candidate.id === "A");
if (!theme) {
  throw new Error("Missing theme for agent A");
}

const meta: Meta<PlatformIntegrationsStoryArgs> = {
  title: "Platform Integrations/Agent A - Minimalist Data Density",
  args: platformIntegrationsDefaultArgs,
  argTypes: platformIntegrationsArgTypes as Meta<PlatformIntegrationsStoryArgs>["argTypes"],
};

export default meta;

export const Interactive = {
  render: (args: PlatformIntegrationsStoryArgs) => (
    <div className="story-shell-wrap">
      <AgentShellPlatformIntegrations
        theme={theme}
        scenario={args.scenario}
        uiState={args.uiState}
        density={args.density}
      />
    </div>
  ),
};
