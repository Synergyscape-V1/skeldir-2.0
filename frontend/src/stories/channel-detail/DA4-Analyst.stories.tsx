import type { Meta, StoryObj } from '@storybook/react';
import { MemoryRouter } from 'react-router-dom';
import { HorizontalNavShell } from '../../explorations/channel-detail/da-4/HorizontalNavShell';
import { ChannelDetailPage } from '../../explorations/channel-detail/da-4/ChannelDetailPage';
import { MOCK_STATES } from '../../explorations/channel-detail/shared/mock-data';

const FullPage = ({ state }: any) => (
  <div style={{ background: '#0A0E1A', minHeight: '100vh' }}>
    <HorizontalNavShell activeRoute="/channels" />
    <ChannelDetailPage state={state} />
  </div>
);

const meta: Meta<typeof FullPage> = {
  title: 'Channel Detail Explorations/DA4 Analyst',
  component: FullPage,
  decorators: [
    (Story) => (
      <MemoryRouter initialEntries={['/channels/facebook']}>
        <Story />
      </MemoryRouter>
    ),
  ],
  parameters: { layout: 'fullscreen' },
};

export default meta;
type Story = StoryObj<typeof FullPage>;

export const Ready: Story = { args: { state: MOCK_STATES.ready } };
export const Loading: Story = { args: { state: MOCK_STATES.loading } };
export const Empty: Story = { args: { state: MOCK_STATES.emptyNoData } };
export const Error: Story = { args: { state: MOCK_STATES.error } };
