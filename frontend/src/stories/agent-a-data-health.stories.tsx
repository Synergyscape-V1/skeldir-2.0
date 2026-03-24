import type { Meta } from "@storybook/react";
import { AgentShellDataHealth } from "../comparison/AgentShellDataHealth";
import { AGENTS } from "../comparison/agents";
import {
  dataHealthArgTypes,
  dataHealthDefaultArgs,
  type DataHealthStoryArgs,
} from "./sharedDataHealthStoryFactory";

const theme = AGENTS.find((candidate) => candidate.id === "A");
if (!theme) {
  throw new Error("Missing theme for agent A");
}

const meta: Meta<DataHealthStoryArgs> = {
  title: "Data Health/Agent A - Triage Command Deck",
  args: dataHealthDefaultArgs,
  argTypes: dataHealthArgTypes as Meta<DataHealthStoryArgs>["argTypes"],
};

export default meta;

export const Interactive = {
  render: (args: DataHealthStoryArgs) => (
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
