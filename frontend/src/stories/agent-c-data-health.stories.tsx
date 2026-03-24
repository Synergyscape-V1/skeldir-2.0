import type { Meta } from "@storybook/react";
import { AgentShellDataHealth } from "../comparison/AgentShellDataHealth";
import { AGENTS } from "../comparison/agents";
import {
  dataHealthArgTypes,
  dataHealthDefaultArgs,
  type DataHealthStoryArgs,
} from "./sharedDataHealthStoryFactory";

const theme = AGENTS.find((candidate) => candidate.id === "C");
if (!theme) {
  throw new Error("Missing theme for agent C");
}

const meta: Meta<DataHealthStoryArgs> = {
  title: "Data Health/Agent C - Metric Forensics Board",
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
