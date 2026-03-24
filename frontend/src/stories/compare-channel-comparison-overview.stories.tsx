import type { Meta, StoryObj } from "@storybook/react";
import {
  CompareAllChannelComparisonView,
  channelComparisonArgTypes,
  channelComparisonDefaultArgs,
  type ChannelComparisonStoryArgs,
} from "./sharedChannelComparisonStoryFactory";

const meta: Meta<ChannelComparisonStoryArgs> = {
  title: "Channel Comparison/Compare All",
  args: channelComparisonDefaultArgs,
  argTypes: channelComparisonArgTypes as Meta<ChannelComparisonStoryArgs>["argTypes"],
  parameters: {
    docs: {
      description: {
        component:
          "Primary decision surface for five independent channel comparison hypotheses with synchronized controls and embedded evaluation scaffold.",
      },
    },
  },
};

export default meta;

export const Overview: StoryObj<ChannelComparisonStoryArgs> = {
  render: (args) => <CompareAllChannelComparisonView {...args} />,
};
