import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router-dom';
import { useEffect } from 'react';
import { createMockSession, createMockTenant } from '../auth/authClient';
import { establishTenant, resetAuthStateForTests, setBootstrapReady } from '../auth/sessionStore';
import {
  createGovernanceClient,
  createMockGovernanceTransport,
  resetDefaultGovernanceClient,
  setDefaultGovernanceClient,
} from '../governance/governanceClient';
import { resetGovernanceStateForTests, setCurrentUserRole } from '../governance/governanceStore';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import { PageSurface } from '../components/layout/PageSurface/PageSurface';
import { TeamSettingsPage } from '../components/governance/TeamSettingsPage/TeamSettingsPage';
import { PolicySettingsPage } from '../components/governance/PolicySettingsPage/PolicySettingsPage';
import { PolicyInvalidAuthorityBanner } from '../components/governance/PolicySettings/PolicySettingsComponents';
import { PolicyAuthorityPill } from '../components/trust/PolicyAuthorityPill/PolicyAuthorityPill';
import { Skeleton } from '../components/layout/Skeleton/Skeleton';
import { PermissionDeniedPanel } from '../components/governance/PermissionDeniedPanel/PermissionDeniedPanel';
import styles from '../app/authPages.module.css';

function SeedFixture({ fixture }: { fixture: string }) {
  useEffect(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    resetDefaultGovernanceClient();

    const role = fixture.includes('permission-denied') ? 'viewer' : 'owner';
    if (!fixture.includes('loading')) {
      establishTenant(createMockSession(), createMockTenant());
      setBootstrapReady();
      setCurrentUserRole(role);
    }

    setDefaultGovernanceClient(
      createGovernanceClient(
        createMockGovernanceTransport({
          currentUserRole: role,
          delayMs: fixture.includes('loading') ? 60_000 : undefined,
          denyPermissions: fixture.includes('permission-denied'),
        }),
      ),
    );
  }, [fixture]);

  return null;
}

function SpecimenRouter() {
  const [params] = useSearchParams();
  const fixture = params.get('fixture') ?? 'team-default';

  return (
  <>
    <SeedFixture fixture={fixture} />
    {fixture.startsWith('shell-') ? (
      <MemoryRouter
        initialEntries={[
          `/app/${fixture
            .replace('shell-', '')
            .replace('team', 'settings/team')
            .replace('policy', 'settings/policy')}`,
        ]}
      >
        <Routes>
          <Route path="/app/*" element={<AppShellRoutes />} />
        </Routes>
      </MemoryRouter>
    ) : (
      <PageSurface>
        {fixture === 'team-default' && <TeamSettingsPage />}
        {fixture === 'team-loading' && <Skeleton rows={4} variant="row" />}
        {fixture === 'team-permission-denied' && <PermissionDeniedPanel />}
        {fixture === 'policy-default' && <PolicySettingsPage />}
        {fixture === 'policy-blocked' && (
          <div>
            <PolicyAuthorityPill state="blocked" />
          </div>
        )}
        {fixture === 'policy-invalid-auto' && <PolicyInvalidAuthorityBanner />}
      </PageSurface>
    )}
  </>
  );
}

export function Level4GovernanceSpecimens() {
  return (
    <div className={styles.page} data-level4-specimens>
      <MemoryRouter initialEntries={['/dev/level4-specimens']}>
        <Routes>
          <Route path="/dev/level4-specimens" element={<SpecimenRouter />} />
        </Routes>
      </MemoryRouter>
    </div>
  );
}
