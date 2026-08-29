import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { SessionBootstrapBoundary } from '../components/auth/SessionBootstrapBoundary/SessionBootstrapBoundary';

import { Level0SpecimenGallery } from '../dev/Level0SpecimenGallery';

import { Level1AuthSpecimens } from '../dev/Level1AuthSpecimens';

import { Level2ShellSpecimens } from '../dev/Level2ShellSpecimens';

import { Level3ActivationSpecimens } from '../dev/Level3ActivationSpecimens';
import { Level4GovernanceSpecimens } from '../dev/Level4GovernanceSpecimens';
import { Level5OperationalAuditSpecimens } from '../dev/Level5OperationalAuditSpecimens';
import { Level6TrustGenerationSpecimens } from '../dev/Level6TrustGenerationSpecimens';
import { Level7LedgerSpecimens } from '../dev/Level7LedgerSpecimens';
import { Level8LedgerSpecimens } from '../dev/Level8LedgerSpecimens';
import { Level10CommandCenterSpecimens } from '../dev/Level10CommandCenterSpecimens';
import { Level11LaunchParitySpecimens } from '../dev/Level11LaunchParitySpecimens';

import {

  AuthInvitePage,

  LoginPage,

  SessionReadyPage,

  SignupPage,

  WorkspaceCreatedPage,

} from './routes/AuthRoutes';

import { AppShellRoutes, IntegrationsAliasRedirect, OnboardingAliasRedirect, ShellAliasRedirect } from './routes/ShellRoutes';
import {
  BillingSettingsAliasRedirect,
  PolicySettingsAliasRedirect,
  TeamSettingsAliasRedirect,
} from './routes/GovernanceAliases';
import { PublicRouteNotFoundPage } from '../routeRecovery/PublicRouteNotFoundPage';
import { AuditAliasRedirect, DiagnosticsAliasRedirect } from './routes/OperationalAuditAliases';
import {
  BenchmarksAliasRedirect,
  BudgetAliasRedirect,
  ChannelsAliasRedirect,
  ClaimsAliasRedirect,
  ExceptionsAliasRedirect,
  TrustAliasRedirect,
} from './routes/LedgerAliases';



export function App() {

  return (

    <BrowserRouter>

      <SessionBootstrapBoundary>

        <Routes>

          <Route path="/" element={<Navigate to="/login" replace />} />

          <Route path="/login" element={<LoginPage />} />

          <Route path="/signup" element={<SignupPage />} />

          <Route path="/auth" element={<AuthInvitePage />} />

          <Route path="/entry/session-ready" element={<SessionReadyPage />} />

          <Route path="/entry/workspace-created" element={<WorkspaceCreatedPage />} />

          <Route path="/app/*" element={<AppShellRoutes />} />

          <Route path="/onboarding/*" element={<OnboardingAliasRedirect />} />

          <Route path="/integrations/*" element={<IntegrationsAliasRedirect />} />

          <Route path="/settings/team/*" element={<TeamSettingsAliasRedirect />} />
          <Route path="/settings/policy/*" element={<PolicySettingsAliasRedirect />} />
          <Route path="/settings/billing/*" element={<BillingSettingsAliasRedirect />} />
          <Route path="/audit/*" element={<AuditAliasRedirect />} />
          <Route path="/diagnostics/*" element={<DiagnosticsAliasRedirect />} />
          <Route path="/claims/*" element={<ClaimsAliasRedirect />} />
          <Route path="/trust/*" element={<TrustAliasRedirect />} />
          <Route path="/channels/*" element={<ChannelsAliasRedirect />} />
          <Route path="/benchmarks/*" element={<BenchmarksAliasRedirect />} />
          <Route path="/budget/*" element={<BudgetAliasRedirect />} />
          <Route path="/exceptions/*" element={<ExceptionsAliasRedirect />} />

          <Route path="/shell/*" element={<ShellAliasRedirect />} />

          <Route path="/dev/specimens" element={<Level0SpecimenGallery />} />

          <Route path="/dev/auth-specimens" element={<Level1AuthSpecimens />} />

          <Route path="/dev/shell-specimens" element={<Level2ShellSpecimens />} />

          <Route path="/dev/level3-specimens" element={<Level3ActivationSpecimens />} />

          <Route path="/dev/level4-specimens" element={<Level4GovernanceSpecimens />} />
          <Route path="/dev/level5-specimens" element={<Level5OperationalAuditSpecimens />} />
          <Route path="/dev/level6-specimens" element={<Level6TrustGenerationSpecimens />} />
          <Route path="/dev/level7-specimens" element={<Level7LedgerSpecimens />} />
          <Route path="/dev/level8-specimens" element={<Level8LedgerSpecimens />} />
          <Route path="/dev/level10-specimens" element={<Level10CommandCenterSpecimens />} />
          <Route path="/dev/level11-specimens" element={<Level11LaunchParitySpecimens />} />

          <Route path="*" element={<PublicRouteNotFoundPage />} />

        </Routes>

      </SessionBootstrapBoundary>

    </BrowserRouter>

  );

}

