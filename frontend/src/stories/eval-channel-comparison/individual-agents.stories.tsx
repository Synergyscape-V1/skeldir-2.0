import React from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";
import { AGENTS } from "../../comparison/agents";
import { AgentShellChannelComparison } from "../../comparison/AgentShellChannelComparison";
import type { DateRangeValue } from "../../types/channel";
import type { ChannelComparisonUiState, ComparisonScenario } from "../../types/comparison";
import { CHANNEL_COMPARISON_MANIFESTS } from "../../channel-comparison/core/manifests";

type Args = {
  scenario: ComparisonScenario;
  uiState: ChannelComparisonUiState;
  dateRange: DateRangeValue;
  density: 90 | 100;
  viewportWidth: 375 | 768 | 1440;
};

const meta: Meta<Args> = {
  title: "Individual Agents",
  args: {
    scenario: "default",
    uiState: "populated",
    dateRange: "last_30_days",
    density: 100,
    viewportWidth: 1440,
  },
  argTypes: {
    scenario: { control: { type: "radio" }, options: ["default", "no_winner", "three_channels", "four_channels", "empty"] },
    uiState: { control: { type: "radio" }, options: ["populated", "loading", "error_panel", "error_global", "empty"] },
    dateRange: { control: { type: "radio" }, options: ["last_7_days", "last_30_days", "last_60_days", "last_90_days"] },
    density: { control: { type: "inline-radio" }, options: [100, 90] },
    viewportWidth: { control: { type: "inline-radio" }, options: [1440, 768, 375] },
  },
};

export default meta;

function AgentStory({ agentId, args }: { agentId: "A" | "B" | "C" | "D" | "E"; args: Args }) {
  const theme = AGENTS.find((a) => a.id === agentId)!;
  const manifest = CHANNEL_COMPARISON_MANIFESTS.find((m) => m.agentId === agentId);
  return (
    <div className="story-shell-wrap">
      <MemoryRouter initialEntries={["/channels/compare"]}>
        <div style={{ marginBottom: 16, padding: "12px 16px", background: "#f9fafb", borderRadius: 8, border: "1px solid #e5e7eb" }}>
          <strong style={{ fontSize: 13 }}>Hypothesis:</strong>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: "#6b7280" }}>{manifest?.hypothesis}</p>
        </div>
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
  );
}

export const AgentA_ClarityFirst: StoryObj<Args> = {
  name: "Agent A — Clarity First",
  render: (args) => <AgentStory agentId="A" args={args} />,
};

export const AgentB_DataDensity: StoryObj<Args> = {
  name: "Agent B — Data Density",
  render: (args) => <AgentStory agentId="B" args={args} />,
};

export const AgentC_ConfidenceHero: StoryObj<Args> = {
  name: "Agent C — Confidence Hero",
  render: (args) => <AgentStory agentId="C" args={args} />,
};

export const AgentD_ActionForward: StoryObj<Args> = {
  name: "Agent D — Action-Forward",
  render: (args) => <AgentStory agentId="D" args={args} />,
};

export const AgentE_CanonicalFidelity: StoryObj<Args> = {
  name: "Agent E — Canonical Fidelity",
  render: (args) => <AgentStory agentId="E" args={args} />,
};
