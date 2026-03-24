import type { Meta } from "@storybook/react";
import {
  channelComparisonArgTypes,
  channelComparisonDefaultArgs,
  createAgentStory,
  type ChannelComparisonStoryArgs,
} from "./sharedChannelComparisonStoryFactory";

const meta: Meta<ChannelComparisonStoryArgs> = {
  title: "Channel Comparison/Agent B - Data Density and Power Users",
  args: channelComparisonDefaultArgs,
  argTypes: channelComparisonArgTypes as Meta<ChannelComparisonStoryArgs>["argTypes"],
};

export default meta;

export const Interactive = createAgentStory("B");
