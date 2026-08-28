export type ShellNavItemId =
  | 'command-center'
  | 'revenue-claims'
  | 'trust-envelopes'
  | 'channels'
  | 'budget-simulation'
  | 'exceptions'
  | 'audit-ledger'
  | 'integrations'
  | 'settings';

export type ShellNavUnlockLevel =
  | 'level-3'
  | 'level-4'
  | 'level-5'
  | 'level-6'
  | 'level-7'
  | 'level-8'
  | 'level-9'
  | 'level-10'
  | 'level-11';

export interface ShellNavItem {
  id: ShellNavItemId;
  label: string;
  unlockLevel: ShellNavUnlockLevel;
  unlockLabel: string;
  mobilePrimary?: boolean;
  mobileMoreOnly?: boolean;
}

export type ShellRoutePanelState =
  | 'shell-landing'
  | 'route-blocked'
  | 'unknown-route'
  | 'loading'
  | 'session-missing'
  | 'tenant-missing'
  | 'permission-denied'
  | 'error';
