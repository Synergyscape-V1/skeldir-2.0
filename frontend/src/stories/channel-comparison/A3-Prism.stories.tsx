/**
 * A3-PRISM — Split-Pane Comparator Channel Comparison
 *
 * Side-by-side channel panels. Each channel gets its own mini-dashboard column.
 * Features the HealthHeartbeat animated SVG pulse indicator.
 */

import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { A3PrismComparison } from '../../pages/channel-comparison/a3-prism';
import { COMPARISON_FIXTURES } from '../../pages/channel-comparison/shared';
import type { ChannelComparisonState } from '../../pages/channel-comparison/shared/types';

interface WrapperProps {
  initialState: ChannelComparisonState;
}

const Wrapper: React.FC<WrapperProps> = ({ initialState }) => (
  <div style={{ background: 'var(--background)', minHeight: '100vh' }}>
    <A3PrismComparison initialState={initialState} />
  </div>
);

const meta: Meta<typeof Wrapper> = {
  title: 'Channel Comparison/A3 Prism (Split-Pane)',
  component: Wrapper,
  parameters: {
    layout: 'fullscreen',
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
