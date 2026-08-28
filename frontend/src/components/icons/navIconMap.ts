import type { ShellNavItemId } from '../../shell/types';
import homeIcon from '../../assets/icons/nav/home.svg';
import revenueClaimsIcon from '../../assets/icons/nav/revenue-claims.svg';
import trustEnvelopeIcon from '../../assets/icons/nav/trust-envelope.svg';
import channelsIcon from '../../assets/icons/nav/channels.svg';
import budgetSimulationIcon from '../../assets/icons/nav/budget-simulation.svg';
import exceptionsIcon from '../../assets/icons/nav/exceptions.svg';
import auditLedgerIcon from '../../assets/icons/nav/audit-ledger.svg';
import integrationsIcon from '../../assets/icons/nav/integrations.svg';
import settingsIcon from '../../assets/icons/nav/settings.svg';

export const NAV_ICON_SRC: Record<ShellNavItemId | 'command-center', string> = {
  'command-center': homeIcon,
  'revenue-claims': revenueClaimsIcon,
  'trust-envelopes': trustEnvelopeIcon,
  channels: channelsIcon,
  'budget-simulation': budgetSimulationIcon,
  exceptions: exceptionsIcon,
  'audit-ledger': auditLedgerIcon,
  integrations: integrationsIcon,
  settings: settingsIcon,
};
