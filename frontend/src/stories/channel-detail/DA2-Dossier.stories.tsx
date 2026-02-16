/**
 * DA-2 DOSSIER -- Storybook Stories
 *
 * Full-page stories for the intelligence dossier channel detail view.
 * Covers all 4 state variants: ready, loading, empty, error.
 */
import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { MemoryRouter } from 'react-router-dom';
import { HorizontalNavShell } from '../../explorations/channel-detail/da-2/HorizontalNavShell';
import { ChannelDetailPage } from '../../explorations/channel-detail/da-2/ChannelDetailPage';
import { MOCK_STATES } from '../../explorations/channel-detail/shared/mock-data';
import type { ChannelDetailState } from '../../explorations/channel-detail/shared/types';

/* ── Full Page wrapper ───────────────────────────────────── */
interface FullPageProps {
  state: ChannelDetailState;
}

const FullPage: React.FC<FullPageProps> = ({ state }) => (
  <div style={{ background: '#0A0E1A', minHeight: '100vh' }}>
    <HorizontalNavShell activeRoute="/channels" breadcrumb={['Channels', 'Facebook Ads']} />
    <ChannelDetailPage state={state} />
  </div>
);

/* ── Meta ─────────────────────────────────────────────────── */
const meta: Meta<typeof FullPage> = {
  title: 'Channel Detail Explorations/DA2 Dossier',
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
  },
};

export default meta;
type Story = StoryObj<typeof FullPage>;

/* ── Stories ──────────────────────────────────────────────── */

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

export const EmptyFeatureLocked: Story = {
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
