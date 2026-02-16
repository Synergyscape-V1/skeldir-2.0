/**
 * A1-SENTINEL Command Center — Storybook Stories
 *
 * 4 mandatory state stories: loading, empty, error, ready
 * Uses deterministic fixtures from shared-types.
 */

import type { Meta, StoryObj } from '@storybook/react';
import { MemoryRouter } from 'react-router-dom';
import { SentinelCommandCenter } from '../command-center/SentinelCommandCenter';
import { FIXTURES } from '../types';

const meta: Meta<typeof SentinelCommandCenter> = {
  title: 'A1-Sentinel/CommandCenter',
  component: SentinelCommandCenter,
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <MemoryRouter>
        <div className="max-w-6xl mx-auto">
          <Story />
        </div>
      </MemoryRouter>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof SentinelCommandCenter>;

export const Ready: Story = {
  args: {
    initialState: FIXTURES.ready,
  },
};

export const Loading: Story = {
  args: {
    initialState: FIXTURES.loading,
  },
};

export const EmptyNoData: Story = {
  args: {
    initialState: FIXTURES.empty,
  },
};

export const EmptyBuildingModel: Story = {
  args: {
    initialState: FIXTURES.emptyBuildingModel,
  },
};

export const Error: Story = {
  args: {
    initialState: FIXTURES.error,
  },
};
