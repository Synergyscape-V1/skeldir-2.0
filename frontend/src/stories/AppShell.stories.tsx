/**
 * D3.1 AppShell Story — Runtime Proof Harness
 * 
 * Validates:
 * - 6 nav items from SSOT render correctly
 * - Active-route highlighting via NavLink
 * - Header affordances (Logo, Help, Profile, Hamburger)
 * - Responsive behavior at 1024/1280/1440
 * - Semantic structure (header, aside, main)
 * 
 * Manual validation targets:
 * - Desktop (≥1440): Fixed sidebar, all nav items visible
 * - 1280: Fixed sidebar
 * - 1024: Fixed sidebar
 * - <1024: Collapsible sidebar, hamburger visible
 */

import type { Meta, StoryObj } from '@storybook/react-vite'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import AppShell from '@/components/AppShell'

// Stub components for each route
function CommandCenterStub() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Command Center</h1>
      <p className="text-muted-foreground">Root route (/) - Main dashboard</p>
    </div>
  )
}

function ChannelsStub() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Channels</h1>
      <p className="text-muted-foreground">/channels route</p>
    </div>
  )
}

function DataStub() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Data</h1>
      <p className="text-muted-foreground">/data route</p>
    </div>
  )
}

function BudgetStub() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Budget</h1>
      <p className="text-muted-foreground">/budget route</p>
    </div>
  )
}

function InvestigationsStub() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Investigations</h1>
      <p className="text-muted-foreground">/investigations route</p>
    </div>
  )
}

function SettingsStub() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Settings</h1>
      <p className="text-muted-foreground">/settings route</p>
    </div>
  )
}

function HelpStub() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Help</h1>
      <p className="text-muted-foreground">/help route (header link)</p>
    </div>
  )
}

const meta: Meta = {
  title: 'Shell/AppShell',
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component:
          'D3.1 Application Shell with 6-item SSOT navigation, React Router NavLink ' +
          'for active-route highlighting, and responsive sidebar (fixed ≥1024, collapsible <1024).',
      },
    },
  },
  tags: ['autodocs'],
}

export default meta

type Story = StoryObj

/**
 * Default story — Command Center route (/)
 * Validate: 6 nav items render, first item is active (highlighted)
 */
export const CommandCenter: Story = {
  render: () => (
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<CommandCenterStub />} />
          <Route path="channels" element={<ChannelsStub />} />
          <Route path="data" element={<DataStub />} />
          <Route path="budget" element={<BudgetStub />} />
          <Route path="investigations" element={<InvestigationsStub />} />
          <Route path="settings" element={<SettingsStub />} />
          <Route path="help" element={<HelpStub />} />
        </Route>
      </Routes>
    </MemoryRouter>
  ),
}

/**
 * Channels route active
 * Validate: Second nav item is active/highlighted
 */
export const ChannelsActive: Story = {
  render: () => (
    <MemoryRouter initialEntries={['/channels']}>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<CommandCenterStub />} />
          <Route path="channels" element={<ChannelsStub />} />
          <Route path="data" element={<DataStub />} />
          <Route path="budget" element={<BudgetStub />} />
          <Route path="investigations" element={<InvestigationsStub />} />
          <Route path="settings" element={<SettingsStub />} />
          <Route path="help" element={<HelpStub />} />
        </Route>
      </Routes>
    </MemoryRouter>
  ),
}

/**
 * Data route active
 * Validate: Third nav item is active/highlighted
 */
export const DataActive: Story = {
  render: () => (
    <MemoryRouter initialEntries={['/data']}>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<CommandCenterStub />} />
          <Route path="channels" element={<ChannelsStub />} />
          <Route path="data" element={<DataStub />} />
          <Route path="budget" element={<BudgetStub />} />
          <Route path="investigations" element={<InvestigationsStub />} />
          <Route path="settings" element={<SettingsStub />} />
          <Route path="help" element={<HelpStub />} />
        </Route>
      </Routes>
    </MemoryRouter>
  ),
}

/**
 * Settings route active (last nav item)
 * Validate: Sixth nav item is active/highlighted
 */
export const SettingsActive: Story = {
  render: () => (
    <MemoryRouter initialEntries={['/settings']}>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<CommandCenterStub />} />
          <Route path="channels" element={<ChannelsStub />} />
          <Route path="data" element={<DataStub />} />
          <Route path="budget" element={<BudgetStub />} />
          <Route path="investigations" element={<InvestigationsStub />} />
          <Route path="settings" element={<SettingsStub />} />
          <Route path="help" element={<HelpStub />} />
        </Route>
      </Routes>
    </MemoryRouter>
  ),
}
