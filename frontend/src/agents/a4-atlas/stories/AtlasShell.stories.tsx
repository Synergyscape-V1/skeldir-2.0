import type { Meta, StoryObj } from '@storybook/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AtlasShell } from '../shell/AtlasShell';
import { AtlasCommandCenter } from '../command-center/AtlasCommandCenter';

const meta: Meta<typeof AtlasShell> = {
  title: 'A4-Atlas/Shell',
  component: AtlasShell,
  parameters: { layout: 'fullscreen' },
  decorators: [
    (Story) => (
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<Story />}>
            <Route index element={<AtlasCommandCenter />} />
            <Route path="channels" element={<div className="p-6 text-muted-foreground">Channels stub</div>} />
            <Route path="data" element={<div className="p-6 text-muted-foreground">Data stub</div>} />
            <Route path="settings" element={<div className="p-6 text-muted-foreground">Settings stub</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    ),
  ],
};
export default meta;
type Story = StoryObj<typeof AtlasShell>;
export const Default: Story = {};
export const ChannelsRoute: Story = { decorators: [(Story) => (<MemoryRouter initialEntries={['/channels']}><Routes><Route element={<Story />}><Route path="channels" element={<div className="p-6 text-muted-foreground">Channels page stub</div>} /></Route></Routes></MemoryRouter>)] };
export const DataRoute: Story = { decorators: [(Story) => (<MemoryRouter initialEntries={['/data']}><Routes><Route element={<Story />}><Route path="data" element={<div className="p-6 text-muted-foreground">Data page stub</div>} /></Route></Routes></MemoryRouter>)] };
export const SettingsRoute: Story = { decorators: [(Story) => (<MemoryRouter initialEntries={['/settings']}><Routes><Route element={<Story />}><Route path="settings" element={<div className="p-6 text-muted-foreground">Settings page stub</div>} /></Route></Routes></MemoryRouter>)] };
