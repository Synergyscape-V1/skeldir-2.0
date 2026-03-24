import React, { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";
import { AGENTS } from "../comparison/agents";
import { AgentShellChannelComparison } from "../comparison/AgentShellChannelComparison";
import type { DateRangeValue } from "../types/channel";
import type { ChannelComparisonUiState, ComparisonScenario } from "../types/comparison";
import { ChannelComparisonEvaluationPanel } from "../channel-comparison/evaluation/ChannelComparisonEvaluationPanel";
import { CHANNEL_COMPARISON_MANIFESTS } from "../channel-comparison/core/manifests";

export type ChannelComparisonStoryArgs = {
  scenario: ComparisonScenario;
  uiState: ChannelComparisonUiState;
  dateRange: DateRangeValue;
  density: 90 | 100;
  viewportWidth: 375 | 768 | 1440;
};

export const channelComparisonArgTypes = {
  scenario: {
    control: { type: "radio" },
    options: ["default", "no_winner", "three_channels", "four_channels", "empty"],
  },
  uiState: {
    control: { type: "radio" },
    options: ["populated", "loading", "error_panel", "error_global", "empty"],
  },
  dateRange: {
    control: { type: "radio" },
    options: ["last_7_days", "last_30_days", "last_60_days", "last_90_days"],
  },
  density: {
    control: { type: "inline-radio" },
    options: [100, 90],
  },
  viewportWidth: {
    control: { type: "inline-radio" },
    options: [1440, 768, 375],
  },
} as const;

export const channelComparisonDefaultArgs: ChannelComparisonStoryArgs = {
  scenario: "default",
  uiState: "populated",
  dateRange: "last_30_days",
  density: 100,
  viewportWidth: 1440,
};

export function buildAgentMeta(title: string): Meta<ChannelComparisonStoryArgs> {
  return {
    title,
    args: channelComparisonDefaultArgs,
    argTypes: channelComparisonArgTypes as Meta<ChannelComparisonStoryArgs>["argTypes"],
    parameters: {
      docs: {
        description: {
          component:
            "Channel Comparison variant rendered in the fixed shell. Controls synchronize scenario, state, date range, and viewport width.",
        },
      },
    },
  };
}

export function createAgentStory(
  agentId: "A" | "B" | "C" | "D" | "E"
): StoryObj<ChannelComparisonStoryArgs> {
  const theme = AGENTS.find((candidate) => candidate.id === agentId);
  if (!theme) throw new Error(`Missing theme for agent ${agentId}`);

  return {
    render: (args) => (
      <div className="story-shell-wrap">
        <MemoryRouter initialEntries={["/channels/compare"]}>
          <div style={{ width: args.viewportWidth, maxWidth: "100%" }}>
            <AgentShellChannelComparison
              theme={theme}
              scenario={args.scenario}
              uiState={args.uiState}
              dateRange={args.dateRange}
              density={args.density}
            />
          </div>
        </MemoryRouter>
      </div>
    ),
  };
}

type CompareLayout = "2-up" | "3-up" | "5-up";

export function CompareAllChannelComparisonView(args: ChannelComparisonStoryArgs) {
  const [layout, setLayout] = useState<CompareLayout>("5-up");

  const visibleCount = layout === "2-up" ? 2 : layout === "3-up" ? 3 : 5;
  const visibleAgents = AGENTS.slice(0, visibleCount);

  return (
    <MemoryRouter initialEntries={["/channels/compare"]}>
      <>
        <div className="cc-compare-toolbar">
          <span className="cc-compare-toolbar-label">Layout:</span>
          {(["2-up", "3-up", "5-up"] as CompareLayout[]).map((option) => (
            <button
              key={option}
              type="button"
              className={`cc-compare-toolbar-btn ${layout === option ? "is-active" : ""}`}
              onClick={() => setLayout(option)}
            >
              {option}
            </button>
          ))}
        </div>

        <section className="cc-compare-row" aria-label="Channel comparison variants" data-layout={layout}>
          {visibleAgents.map((agent) => (
            <article key={agent.id} className="cc-compare-column">
              <header>
                <h2>{agent.navLabel}</h2>
                <p>{agent.signature}</p>
              </header>
              <div className="cc-compare-frame" style={{ width: args.viewportWidth }}>
                <AgentShellChannelComparison
                  theme={agent}
                  scenario={args.scenario}
                  uiState={args.uiState}
                  dateRange={args.dateRange}
                  density={args.density}
                />
              </div>
            </article>
          ))}
        </section>

        <ChannelComparisonEvaluationPanel manifests={CHANNEL_COMPARISON_MANIFESTS} />
      </>
    </MemoryRouter>
  );
}

export function StatesMatrixView() {
  const states: ChannelComparisonUiState[] = ["populated", "loading", "empty", "error_panel", "error_global"];

  return (
    <MemoryRouter initialEntries={["/channels/compare"]}>
      <div className="cc-states-matrix">
        <table className="cc-states-matrix-table">
          <thead>
            <tr>
              <th>Agent / State</th>
              {states.map((s) => (
                <th key={s}>{s}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {AGENTS.map((agent) => (
              <tr key={agent.id}>
                <td className="cc-states-matrix-label">{agent.navLabel}</td>
                {states.map((uiState) => (
                  <td key={`${agent.id}-${uiState}`} className="cc-states-matrix-cell">
                    <div style={{ width: 400, maxHeight: 400, overflow: "hidden", transform: "scale(0.35)", transformOrigin: "top left" }}>
                      <AgentShellChannelComparison
                        theme={agent}
                        scenario="default"
                        uiState={uiState}
                        dateRange="last_30_days"
                        density={100}
                      />
                    </div>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </MemoryRouter>
  );
}
