import { SHELL_COPY } from './copy';
import type { ShellNavItem, ShellNavItemId, ShellNavUnlockLevel } from './types';

export const SHELL_NAV_ITEMS: readonly ShellNavItem[] = [
  {
    id: 'command-center',
    label: 'Overview',
    unlockLevel: 'level-10',
    unlockLabel: 'Overview (Level 10)',
    mobilePrimary: true,
  },
  {
    id: 'revenue-claims',
    label: 'Revenue Claims',
    unlockLevel: 'level-7',
    unlockLabel: 'Revenue Claims Ledger (Level 7)',
    mobilePrimary: true,
  },
  {
    id: 'trust-envelopes',
    label: 'TrustEnvelopes',
    unlockLevel: 'level-7',
    unlockLabel: 'TrustEnvelope List (Level 7)',
  },
  {
    id: 'channels',
    label: 'Channels',
    unlockLevel: 'level-7',
    unlockLabel: 'Channels (Level 7)',
    mobilePrimary: true,
  },
  {
    id: 'budget-simulation',
    label: 'Budget Simulation',
    unlockLevel: 'level-7',
    unlockLabel: 'Budget Simulation (Level 7)',
  },
  {
    id: 'exceptions',
    label: 'Exceptions',
    unlockLevel: 'level-7',
    unlockLabel: 'Exception Queue (Level 7)',
  },
  {
    id: 'audit-ledger',
    label: 'Audit Ledger',
    unlockLevel: 'level-5',
    unlockLabel: 'Audit Ledger (Level 5)',
    mobilePrimary: true,
  },
  {
    id: 'integrations',
    label: 'Integrations',
    unlockLevel: 'level-3',
    unlockLabel: 'Integrations (Level 3)',
  },
  {
    id: 'settings',
    label: 'Settings',
    unlockLevel: 'level-4',
    unlockLabel: 'Team and Policy Settings (Level 4)',
    mobileMoreOnly: true,
  },
] as const;

/** Subtle sidebar separators after day-to-day vs operational vs admin/configuration groups. */
export const SHELL_NAV_SECTION_DIVIDERS_AFTER: readonly ShellNavItemId[] = [
  'channels',
  'audit-ledger',
];

export const MOBILE_PRIMARY_NAV_IDS: ShellNavItemId[] = [
  'command-center',
  'revenue-claims',
  'channels',
  'audit-ledger',
];

export function getNavItemById(id: ShellNavItemId): ShellNavItem {
  const item = SHELL_NAV_ITEMS.find((entry) => entry.id === id);
  if (!item) {
    throw new Error(`Unknown shell nav item: ${id}`);
  }
  return item;
}

export function shellNavPath(id: ShellNavItemId): string {
  if (id === 'integrations') return '/app/integrations';
  if (id === 'settings') return '/app/settings/team';
  if (id === 'audit-ledger') return '/app/audit';
  if (id === 'revenue-claims') return '/app/claims';
  if (id === 'trust-envelopes') return '/app/trust';
  if (id === 'channels') return '/app/channels';
  if (id === 'budget-simulation') return '/app/budget';
  if (id === 'exceptions') return '/app/exceptions';
  if (id === 'command-center') return '/app';
  return `/app/nav/${id}`;
}

export function shellOnboardingPath(): string {
  return '/app/onboarding/step/1';
}

export function isNavUnlocked(unlockLevel: ShellNavUnlockLevel): boolean {
  return (
    unlockLevel === 'level-3' ||
    unlockLevel === 'level-4' ||
    unlockLevel === 'level-5' ||
    unlockLevel === 'level-7' ||
    unlockLevel === 'level-10'
  );
}

export function parseShellNavPath(pathname: string): ShellNavItemId | null {
  if (pathname === '/app' || pathname === '/app/') return 'command-center';
  if (pathname.startsWith('/app/integrations')) return 'integrations';
  if (pathname.startsWith('/app/settings')) return 'settings';
  if (pathname.startsWith('/app/audit')) return 'audit-ledger';
  if (pathname.startsWith('/app/diagnostics')) return 'audit-ledger';
  if (pathname.startsWith('/app/claims')) return 'revenue-claims';
  if (pathname.startsWith('/app/trust')) return 'trust-envelopes';
  if (pathname.startsWith('/app/channels')) return 'channels';
  if (pathname.startsWith('/app/budget')) return 'budget-simulation';
  if (pathname.startsWith('/app/exceptions')) return 'exceptions';
  const match = pathname.match(/^\/app\/nav\/([\w-]+)$/);
  if (!match?.[1]) return null;
  const id = match[1] as ShellNavItemId;
  return SHELL_NAV_ITEMS.some((item) => item.id === id) ? id : null;
}

/** Active shell interface label for the header. */
export function resolveInterfaceName(pathname: string): string {
  if (pathname.startsWith('/app/onboarding')) return 'Onboarding';
  const navId = parseShellNavPath(pathname);
  if (navId) return getNavItemById(navId).label;
  return getNavItemById('command-center').label;
}

export function isOverviewPath(pathname: string): boolean {
  return pathname === '/app' || pathname === '/app/';
}

/** Header location label — tenant welcome on Overview, interface name elsewhere. */
export function resolveHeaderLocationLabel(pathname: string, workspaceName?: string | null): string {
  const tenant = workspaceName?.trim();
  if (isOverviewPath(pathname) && tenant) {
    return SHELL_COPY.welcomeBack(tenant);
  }
  return resolveInterfaceName(pathname);
}
