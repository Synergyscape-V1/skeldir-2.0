/**
 * A6-VICTOR — Reference-Faithful Channel Comparison
 *
 * Light SaaS dashboard matching the provided reference image:
 * - Green recommendation banner
 * - Three channel hero cards with large ROAS numbers
 * - ROAS confidence ranges horizontal bar chart
 * - "Why this matters" / "Why this recommendation" side panels
 * - Detailed comparison table at bottom
 */

import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { A6VictorComparison } from '../../pages/channel-comparison/a6-victor';
import { COMPARISON_FIXTURES } from '../../pages/channel-comparison/shared';
import type { ChannelComparisonState } from '../../pages/channel-comparison/shared/types';

interface WrapperProps {
  initialState: ChannelComparisonState;
}

const Wrapper: React.FC<WrapperProps> = ({ initialState }) => (
  <A6VictorComparison initialState={initialState} />
);

const meta: Meta<typeof Wrapper> = {
  title: 'Channel Comparison/A6 Victor (Reference)',
  component: Wrapper,
  parameters: {
    layout: 'fullscreen',
    backgrounds: {
      default: 'light',
      values: [{ name: 'light', value: '#f9fafb' }],
    },
  },
};

export default meta;

type Story = StoryObj<typeof Wrapper>;

export const Ready: Story = {
  args: { initialState: COMPARISON_FIXTURES.ready },
};

export const Loading: Story = {
  args: { initialState: COMPARISON_FIXTURES.loading },
};

export const EmptyNoData: Story = {
  args: { initialState: COMPARISON_FIXTURES.emptyNoData },
};

export const EmptyBuildingModel: Story = {
  args: { initialState: COMPARISON_FIXTURES.emptyBuildingModel },
};

export const EmptyInsufficientSelection: Story = {
  args: { initialState: COMPARISON_FIXTURES.emptyInsufficientSelection },
};

export const EmptyNoResults: Story = {
  args: { initialState: COMPARISON_FIXTURES.emptyNoResults },
};

export const Error: Story = {
  args: { initialState: COMPARISON_FIXTURES.error },
};
