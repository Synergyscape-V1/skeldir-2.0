import React from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { AgentShellPlatformIntegrations } from "../comparison/AgentShellPlatformIntegrations";
import { AGENTS } from "../comparison/agents";
import type {
  PlatformIntegrationsScenario,
  PlatformIntegrationsUiState,
} from "../platform-integrations/core/types";

export type PlatformIntegrationsStoryArgs = {
  scenario: PlatformIntegrationsScenario;
  uiState: PlatformIntegrationsUiState;
  density: 90 | 100;
};

export const platformIntegrationsArgTypes = {
  scenario: {
    control: { type: "radio" },
    options: ["all_healthy", "mixed", "critical"],
  },
  uiState: {
    control: { type: "radio" },
    options: ["steady", "initial_loading", "error", "no_data"],
  },
  density: {
    control: { type: "inline-radio" },
    options: [100, 90],
  },
} as const;

export const platformIntegrationsDefaultArgs: PlatformIntegrationsStoryArgs = {
  scenario: "mixed",
  uiState: "steady",
  density: 100,
};

export function buildAgentMeta(title: string): Meta<PlatformIntegrationsStoryArgs> {
  return {
    title,
    args: platformIntegrationsDefaultArgs,
    argTypes: platformIntegrationsArgTypes as Meta<PlatformIntegrationsStoryArgs>["argTypes"],
    parameters: {
      docs: {
        description: {
          component:
            "Platform Integrations variant rendered in the fixed application shell. Use controls to validate state and scenario behavior.",
        },
      },
    },
  };
}

export function createAgentStory(
  agentId: "A" | "B" | "C" | "D" | "E"
): StoryObj<PlatformIntegrationsStoryArgs> {
  const theme = AGENTS.find((candidate) => candidate.id === agentId);
  if (!theme) {
    throw new Error(`Missing theme for agent ${agentId}`);
  }

  return {
    render: (args) => (
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
}

export function CompareAllPlatformIntegrationsView(
  args: PlatformIntegrationsStoryArgs
) {
  return (
    <section className="story-compare-all-root">
      {AGENTS.map((agent) => (
        <article key={agent.id} className="story-compare-all-card">
          <header>
            <h2>{agent.navLabel}</h2>
            <p>{agent.signature}</p>
          </header>
          <div className="story-compare-all-frame">
            <AgentShellPlatformIntegrations
              theme={agent}
              scenario={args.scenario}
              uiState={args.uiState}
              density={args.density}
            />
          </div>
        </article>
      ))}
    </section>
  );
}
