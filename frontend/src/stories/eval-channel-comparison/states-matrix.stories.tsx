import React from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { StatesMatrixView } from "../sharedChannelComparisonStoryFactory";

const meta: Meta = {
  title: "States Matrix",
  parameters: {
    docs: {
      description: {
        component:
          "5 variants × 5 states (25 cells) rendered at thumbnail scale for rapid QA verification.",
      },
    },
  },
};

export default meta;

export const Matrix: StoryObj = {
  name: "5×5 States Matrix",
  render: () => <StatesMatrixView />,
};
