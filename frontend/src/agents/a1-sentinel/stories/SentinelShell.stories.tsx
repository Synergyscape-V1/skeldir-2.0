/**
 * A1-SENTINEL Shell — Storybook Stories
 *
 * 4 route states demonstrating active-state highlighting
 * and responsive behavior of the top-nav command bar layout.
 */

import type { Meta, StoryObj } from '@storybook/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { SentinelShell } from '../shell/SentinelShell';

const meta: Meta<typeof SentinelShell> = {
  title: 'A1-Sentinel/Shell',
  component: SentinelShell,
  parameters: {
    layout: 'fullscreen',
  },
  decorators: [
    (Story, context) => {
      const route = (context.args as Record<string, string>).route || '/';
      return (
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route element={<Story />}>
              <Route path="/" element={<div className="p-4 text-sm text-muted-foreground">Command Center content</div>} />
              <Route path="/channels" element={<div className="p-4 text-sm text-muted-foreground">Channels content</div>} />
              <Route path="/data" element={<div className="p-4 text-sm text-muted-foreground">Data content</div>} />
              <Route path="/budget" element={<div className="p-4 text-sm text-muted-foreground">Budget content</div>} />
              <Route path="/investigations" element={<div className="p-4 text-sm text-muted-foreground">Investigations content</div>} />
              <Route path="/settings" element={<div className="p-4 text-sm text-muted-foreground">Settings content</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      );
    },
  ],
};

export default meta;
type Story = StoryObj<typeof SentinelShell>;

export const CommandCenter: Story = {
  args: { route: '/' } as Record<string, string>,
};

export const ChannelsActive: Story = {
  args: { route: '/channels' } as Record<string, string>,
};

export const DataActive: Story = {
  args: { route: '/data' } as Record<string, string>,
};

export const SettingsActive: Story = {
  args: { route: '/settings' } as Record<string, string>,
};
