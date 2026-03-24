import React from "react";
import type { Meta, StoryObj } from "@storybook/react";
import {
  CompareAllChannelComparisonView,
  channelComparisonArgTypes,
  channelComparisonDefaultArgs,
  type ChannelComparisonStoryArgs,
} from "../sharedChannelComparisonStoryFactory";

const meta: Meta<ChannelComparisonStoryArgs> = {
  title: "Side-by-Side Comparison",
  args: channelComparisonDefaultArgs,
  argTypes: channelComparisonArgTypes as Meta<ChannelComparisonStoryArgs>["argTypes"],
  parameters: {
    docs: {
      description: {
        component:
          "Primary decision surface: all five channel comparison variants rendered side-by-side with synchronized controls and evaluation scaffold.",
      },
    },
  },
};

export default meta;

export const AllVariants: StoryObj<ChannelComparisonStoryArgs> = {
  name: "All 5 Variants",
  render: (args) => <CompareAllChannelComparisonView {...args} />,
};
