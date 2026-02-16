/**
 * DA-1 COCKPIT — Storybook Stories
 *
 * Full-page stories combining HorizontalNavShell + ChannelDetailPage.
 * Demonstrates all 4 states: Ready, Loading, Empty, Error.
 */

import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { MemoryRouter } from 'react-router-dom';
import { HorizontalNavShell } from '../../explorations/channel-detail/da-1/HorizontalNavShell';
import { ChannelDetailPage } from '../../explorations/channel-detail/da-1/ChannelDetailPage';
import type { ChannelDetailState } from '../../explorations/channel-detail/shared/types';
import { MOCK_STATES } from '../../explorations/channel-detail/shared/mock-data';

/* ── Full Page Wrapper ─────────────────────────────────────────── */

interface FullPageProps {
  state: ChannelDetailState;
}

const FullPage: React.FC<FullPageProps> = ({ state }) => (
  <div style={{ background: '#0A0E1A', minHeight: '100vh' }}>
    <HorizontalNavShell activeRoute="/channels" />
    <ChannelDetailPage state={state} />
  </div>
);

/* ── Meta ───────────────────────────────────────────────────────── */

const meta: Meta<typeof FullPage> = {
  title: 'Channel Detail Explorations/DA1 Cockpit',
  component: FullPage,
  decorators: [
    (Story) => (
      <MemoryRouter initialEntries={['/channels/facebook']}>
        <Story />
      </MemoryRouter>
    ),
  ],
  parameters: {
    layout: 'fullscreen',
    backgrounds: {
      default: 'dark',
      values: [{ name: 'dark', value: '#0A0E1A' }],
    },
  },
};

export default meta;

type Story = StoryObj<typeof FullPage>;

/* ── Stories ────────────────────────────────────────────────────── */

export const Ready: Story = {
  args: {
    state: MOCK_STATES.ready,
  },
};

export const ReadyMediumConfidence: Story = {
  args: {
    state: MOCK_STATES.readyMedium,
  },
};

export const Loading: Story = {
  args: {
    state: MOCK_STATES.loading,
  },
};

export const EmptyNoData: Story = {
  args: {
    state: MOCK_STATES.emptyNoData,
  },
};

export const EmptyBuildingModel: Story = {
  args: {
    state: MOCK_STATES.emptyBuilding,
  },
};

export const EmptyFiltered: Story = {
  args: {
    state: MOCK_STATES.emptyFiltered,
  },
};

export const EmptyLocked: Story = {
  args: {
    state: MOCK_STATES.emptyLocked,
  },
};

export const Error: Story = {
  args: {
    state: MOCK_STATES.error,
  },
};

export const ErrorNonRetryable: Story = {
  args: {
    state: MOCK_STATES.errorNonRetryable,
  },
};
