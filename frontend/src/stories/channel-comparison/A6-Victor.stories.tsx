/**
 * A6-VICTOR — Reference-Faithful Channel Comparison
 *
 * Light SaaS dashboard matching the canonical reference image:
 * - Blue recommendation banner with action buttons
 * - Three bento-box platform cards with hero ROAS numbers
 * - ROAS confidence ranges horizontal bar chart
 * - "Why this matters" / "Why this recommendation" side panels
 * - Detailed comparison table at bottom
 */

import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { A6VictorComparison } from '../../pages/channel-comparison/a6-victor';
import { VICTOR_FIXTURES } from '../../pages/channel-comparison/a6-victor/victor-fixtures';
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
  args: { initialState: VICTOR_FIXTURES.ready },
};

export const Loading: Story = {
  args: { initialState: VICTOR_FIXTURES.loading },
};

export const EmptyNoData: Story = {
  args: { initialState: VICTOR_FIXTURES.emptyNoData },
};

export const EmptyBuildingModel: Story = {
  args: { initialState: VICTOR_FIXTURES.emptyBuildingModel },
};

export const EmptyInsufficientSelection: Story = {
  args: { initialState: VICTOR_FIXTURES.emptyInsufficientSelection },
};

export const EmptyNoResults: Story = {
  args: { initialState: VICTOR_FIXTURES.emptyNoResults },
};

export const Error: Story = {
  args: { initialState: VICTOR_FIXTURES.error },
};
