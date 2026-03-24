import type { Meta, StoryObj } from "@storybook/react";
import {
  CompareAllDataHealthView,
  dataHealthArgTypes,
  dataHealthDefaultArgs,
  type DataHealthStoryArgs,
} from "./sharedDataHealthStoryFactory";

const meta: Meta<DataHealthStoryArgs> = {
  title: "Data Health/Compare All",
  args: dataHealthDefaultArgs,
  argTypes: dataHealthArgTypes as Meta<DataHealthStoryArgs>["argTypes"],
  parameters: {
    docs: {
      description: {
        component: "Purpose-built view to compare all five isolated implementations side-by-side with synchronized controls.",
      },
    },
  },
};

export default meta;

export const Overview: StoryObj<DataHealthStoryArgs> = {
  render: (args) => <CompareAllDataHealthView {...args} />,
};
