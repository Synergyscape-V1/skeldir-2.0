import type { Meta, StoryObj } from '@storybook/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { PrismShell } from '../shell/PrismShell';

const meta: Meta<typeof PrismShell> = {
  title: 'A3-Prism/Shell', component: PrismShell, parameters: { layout: 'fullscreen' },
  decorators: [(Story, ctx) => { const route = (ctx.args as Record<string, string>).route || '/';
    return (<MemoryRouter initialEntries={[route]}><Routes><Route element={<Story />}>
      <Route path="/" element={<div className="p-6 text-sm text-muted-foreground">Command Center</div>} />
      <Route path="/channels" element={<div className="p-6 text-sm text-muted-foreground">Channels</div>} />
      <Route path="/data" element={<div className="p-6 text-sm text-muted-foreground">Data</div>} />
      <Route path="/settings" element={<div className="p-6 text-sm text-muted-foreground">Settings</div>} />
    </Route></Routes></MemoryRouter>); }],
};
export default meta;
type Story = StoryObj<typeof PrismShell>;
export const CommandCenter: Story = { args: { route: '/' } as Record<string, string> };
export const ChannelsActive: Story = { args: { route: '/channels' } as Record<string, string> };
export const DataActive: Story = { args: { route: '/data' } as Record<string, string> };
export const SettingsActive: Story = { args: { route: '/settings' } as Record<string, string> };
