import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router-dom';
import { useEffect, useRef } from 'react';
import { createMockSession, createMockTenant } from '../auth/authClient';
import { establishTenant, resetAuthStateForTests, setBootstrapReady } from '../auth/sessionStore';
import {
  createOperationalAuditClient,
  createMockOperationalAuditTransport,
  resetDefaultOperationalAuditClient,
  setDefaultOperationalAuditClient,
} from '../operationalAudit/operationalAuditClient';
import { resetGovernanceStateForTests, setCurrentUserRole } from '../governance/governanceStore';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import { PageSurface } from '../components/layout/PageSurface/PageSurface';
import { AuditLedgerPage } from '../components/audit/AuditLedgerPage/AuditLedgerPage';
import { OperationalDiagnosticsPage } from '../components/operational/OperationalDiagnosticsPage/OperationalDiagnosticsPage';
import { AuditArtifactDrawer } from '../components/audit/AuditArtifactDrawer/AuditArtifactDrawer';
import { PermissionDeniedPanel } from '../components/governance/PermissionDeniedPanel/PermissionDeniedPanel';
import { Skeleton } from '../components/layout/Skeleton/Skeleton';
import type { SystemHealthState } from '../operationalAudit/types';
import styles from '../app/authPages.module.css';

function SeedFixture({ fixture }: { fixture: string }) {
  useEffect(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    resetDefaultOperationalAuditClient();

    const role = fixture.includes('permission-denied') ? 'billing_only' : 'owner';
    if (!fixture.includes('loading')) {
      establishTenant(createMockSession(), createMockTenant());
      setBootstrapReady();
      setCurrentUserRole(role);
    }

    let healthState: SystemHealthState = 'operational';
    if (fixture.includes('health-degraded')) healthState = 'confidence_degraded';
    if (fixture.includes('health-paused')) healthState = 'api_paused';
    if (fixture.includes('health-integration')) healthState = 'integration_attention';
    if (fixture.includes('health-unknown')) healthState = 'unknown';
    if (fixture.includes('health-failed')) healthState = 'fetch_failed';

    setDefaultOperationalAuditClient(
      createOperationalAuditClient(
        createMockOperationalAuditTransport({
          currentUserRole: role,
          healthState,
          denyAudit: fixture.includes('audit-permission-denied'),
          denyDiagnostics: fixture.includes('diagnostics-permission-denied'),
          denyArtifact: fixture.includes('artifact-access-denied'),
          delayMs: fixture.includes('loading') ? 60_000 : undefined,
          auditEvents: fixture.includes('audit-empty') ? [] : undefined,
          diagnostics: fixture.includes('diagnostics-empty')
            ? {
                summary: {
                  taskFailures: 0,
                  integrationIssues: 0,
                  confidenceDelayed: 0,
                  trustApiPaused: false,
                },
                dlqEvents: [],
              }
            : undefined,
        }),
      ),
    );
  }, [fixture]);

  return null;
}

function ArtifactDrawerFixture({ eventId }: { eventId: string }) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  return (
    <>
      <button ref={triggerRef} type="button">
        trigger
      </button>
      <AuditArtifactDrawer eventId={eventId} open triggerRef={triggerRef} onClose={() => undefined} />
    </>
  );
}

function SpecimenRouter() {
  const [params] = useSearchParams();
  const fixture = params.get('fixture') ?? 'audit-default';

  return (
    <>
      <SeedFixture fixture={fixture} />
      {fixture.startsWith('shell-') ? (
        <MemoryRouter
          initialEntries={[
            fixture.includes('diagnostics') ? '/app/diagnostics' : '/app/audit?filter=system_health',
          ]}
        >
          <Routes>
            <Route path="/app/*" element={<AppShellRoutes />} />
          </Routes>
        </MemoryRouter>
      ) : (
        <PageSurface>
          {(fixture === 'audit-default' || fixture === 'audit-empty') && <AuditLedgerPage />}
          {fixture === 'audit-loading' && <Skeleton rows={4} variant="row" />}
          {fixture === 'audit-permission-denied' && <PermissionDeniedPanel />}
          {(fixture === 'diagnostics-default' || fixture === 'diagnostics-empty') && (
            <OperationalDiagnosticsPage />
          )}
          {fixture === 'diagnostics-permission-denied' && <PermissionDeniedPanel />}
          {fixture === 'artifact-drawer-default' && <ArtifactDrawerFixture eventId="aud_001" />}
          {fixture === 'artifact-unavailable' && <ArtifactDrawerFixture eventId="aud_004" />}
          {fixture === 'artifact-corrupted' && <ArtifactDrawerFixture eventId="aud_003" />}
          {fixture === 'artifact-access-denied' && <ArtifactDrawerFixture eventId="aud_001" />}
        </PageSurface>
      )}
    </>
  );
}

export function Level5OperationalAuditSpecimens() {
  const search = typeof window !== 'undefined' ? window.location.search : '';
  return (
    <div className={styles.page} data-level5-specimens>
      <MemoryRouter initialEntries={[`/dev/level5-specimens${search || '?fixture=audit-default'}`]}>
        <Routes>
          <Route path="/dev/level5-specimens" element={<SpecimenRouter />} />
        </Routes>
      </MemoryRouter>
    </div>
  );
}
