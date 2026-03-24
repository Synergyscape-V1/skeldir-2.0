import React from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { ChannelComparisonEvaluationPanel } from "../../channel-comparison/evaluation/ChannelComparisonEvaluationPanel";
import { CHANNEL_COMPARISON_MANIFESTS } from "../../channel-comparison/core/manifests";

const meta: Meta = {
  title: "Evaluation Panel",
  parameters: {
    docs: {
      description: {
        component:
          "Standalone evaluation scaffold: hypothesis display, validation gate results, and operator annotation textareas (localStorage-persisted) per variant.",
      },
    },
  },
};

export default meta;

export const Panel: StoryObj = {
  name: "Evaluation Scaffold",
  render: () => <ChannelComparisonEvaluationPanel manifests={CHANNEL_COMPARISON_MANIFESTS} />,
};
