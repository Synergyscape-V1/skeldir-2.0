import { Navigate, Route, Routes, useParams } from 'react-router-dom';
import {
  OnboardingCompletePage,
  OnboardingIndexRedirect,
  OnboardingWizard,
} from '../../components/onboarding/OnboardingWizard/OnboardingWizard';
import { AuthenticatedAppShell } from '../../components/shell/AuthenticatedAppShell/AuthenticatedAppShell';
import { ShellAccessGuard } from '../../components/shell/ShellAccessGuard/ShellAccessGuard';
import { ShellFallbackPanel } from '../../components/shell/ShellFallbackPanel/ShellFallbackPanel';
import { getNavItemById, SHELL_NAV_ITEMS } from '../../shell/navigation';
import { IntegrationsPage } from './ActivationRoutes';
import {
  BillingSettingsRoute,
  PolicySettingsRoute,
  TeamSettingsRoute,
} from './GovernanceRoutes';
import { AuditLedgerRoute, OperationalDiagnosticsRoute } from './OperationalAuditRoutes';
import { LEVEL7_LEDGER_ROUTES } from './LedgerRoutes';
import { CommandCenterPage } from '../../components/commandCenter/CommandCenterPage/CommandCenterPage';

function ShellBlockedNavPage() {
  const { navId } = useParams<{ navId: string }>();
  const known = SHELL_NAV_ITEMS.some((item) => item.id === navId);
  if (!navId || !known) {
    return <ShellFallbackPanel state="unknown-route" />;
  }
  const navItem = getNavItemById(navId as (typeof SHELL_NAV_ITEMS)[number]['id']);
  return <ShellFallbackPanel state="route-blocked" navItem={navItem} />;
}

function ShellUnknownPage() {
  return <ShellFallbackPanel state="unknown-route" />;
}

export function AppShellRoutes() {
  return (
    <ShellAccessGuard>
      <Routes>
        <Route element={<AuthenticatedAppShell />}>
          <Route index element={<CommandCenterPage />} />
          <Route path="onboarding" element={<OnboardingIndexRedirect />} />
          <Route path="onboarding/step/:step" element={<OnboardingWizard />} />
          <Route path="onboarding/complete" element={<OnboardingCompletePage />} />
          <Route path="integrations" element={<IntegrationsPage />} />
          <Route path="settings/team" element={<TeamSettingsRoute />} />
          <Route path="settings/policy" element={<PolicySettingsRoute />} />
          <Route path="settings/billing" element={<BillingSettingsRoute />} />
          <Route path="audit/*" element={<AuditLedgerRoute />} />
          <Route path="diagnostics" element={<OperationalDiagnosticsRoute />} />
          {LEVEL7_LEDGER_ROUTES}
          <Route path="benchmarks/*" element={<Navigate to="/app/channels" replace />} />
          <Route path="nav/:navId" element={<ShellBlockedNavPage />} />
          <Route path="*" element={<ShellUnknownPage />} />
        </Route>
      </Routes>
    </ShellAccessGuard>
  );
}

export function ShellAliasRedirect() {
  return <Navigate to="/app" replace />;
}

export function OnboardingAliasRedirect() {
  return <Navigate to="/app/onboarding/step/1" replace />;
}

export function IntegrationsAliasRedirect() {
  return <Navigate to="/app/integrations" replace />;
}
