import React from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { AgentShellDataHealth } from "../comparison/AgentShellDataHealth";
import { AGENTS } from "../comparison/agents";
import type { DataHealthScenario, DataHealthUiState } from "../data-health/core/types";

export type DataHealthStoryArgs = {
  scenario: DataHealthScenario;
  uiState: DataHealthUiState;
  stale: boolean;
  density: 90 | 100;
};

export const dataHealthArgTypes = {
  scenario: {
    control: { type: "radio" },
    options: ["good", "warning", "critical"],
  },
  uiState: {
    control: { type: "radio" },
    options: ["steady", "initial_loading", "error", "no_data"],
  },
  stale: {
    control: { type: "boolean" },
  },
  density: {
    control: { type: "inline-radio" },
    options: [100, 90],
  },
} as const;

export const dataHealthDefaultArgs: DataHealthStoryArgs = {
  scenario: "warning",
  uiState: "steady",
  stale: false,
  density: 100,
};

export function buildAgentMeta(title: string): Meta<DataHealthStoryArgs> {
  return {
    title,
    args: dataHealthDefaultArgs,
    argTypes: dataHealthArgTypes as Meta<DataHealthStoryArgs>["argTypes"],
    parameters: {
      docs: {
        description: {
          component: "Data Health variant rendered in the fixed application shell. Use controls to validate state and scenario behavior.",
        },
      },
    },
  };
}

export function createAgentStory(agentId: "A" | "B" | "C" | "D" | "E"): StoryObj<DataHealthStoryArgs> {
  const theme = AGENTS.find((candidate) => candidate.id === agentId);
  if (!theme) {
    throw new Error(`Missing theme for agent ${agentId}`);
  }

  return {
    render: (args) => (
      <div className="story-shell-wrap">
        <AgentShellDataHealth
          theme={theme}
          scenario={args.scenario}
          uiState={args.uiState}
          stale={args.stale}
          density={args.density}
        />
      </div>
    ),
  };
}

export function CompareAllDataHealthView(args: DataHealthStoryArgs) {
  return (
    <section className="story-compare-all-root">
      {AGENTS.map((agent) => (
        <article key={agent.id} className="story-compare-all-card">
          <header>
            <h2>{agent.navLabel}</h2>
            <p>{agent.signature}</p>
          </header>
          <div className="story-compare-all-frame">
            <AgentShellDataHealth
              theme={agent}
              scenario={args.scenario}
              uiState={args.uiState}
              stale={args.stale}
              density={args.density}
            />
          </div>
        </article>
      ))}
    </section>
  );
}
