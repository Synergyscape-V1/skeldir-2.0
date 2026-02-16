/**
 * D3.1 Navigation SSOT — Single Source of Truth
 * 
 * This config drives ALL navigation renderers (sidebar, mobile menu, future header links).
 * DO NOT add nav items inline elsewhere — update this config only.
 * 
 * Canonical mapping (approved icon associations):
 * - Command Center → LayoutDashboard
 * - Channels → Layers
 * - Data → Database
 * - Budget → PiggyBank
 * - Investigations → Search
 * - Settings → Settings
 */

import {
  LayoutDashboard,
  Layers,
  Database,
  PiggyBank,
  Search,
  Settings,
  type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  /** Display label */
  label: string
  /** Route path */
  path: string
  /** Lucide icon component */
  icon: LucideIcon
  /** Optional: disable nav item */
  disabled?: boolean
}

/**
 * Primary navigation items — 6 items as specified by D3.1
 * Order matters: this is the visual order in the sidebar
 */
export const NAV_ITEMS: NavItem[] = [
  {
    label: 'Command Center',
    path: '/',
    icon: LayoutDashboard,
  },
  {
    label: 'Channels',
    path: '/channels/compare',
    icon: Layers,
  },
  {
    label: 'Data',
    path: '/data',
    icon: Database,
  },
  {
    label: 'Budget',
    path: '/budget',
    icon: PiggyBank,
  },
  {
    label: 'Investigations',
    path: '/investigations',
    icon: Search,
  },
  {
    label: 'Settings',
    path: '/settings',
    icon: Settings,
  },
]
