import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  createMockSession,
  createMockTenant,
  resetDefaultAuthClient,
} from '../auth/authClient';
import { establishTenant, resetAuthStateForTests, setBootstrapReady } from '../auth/sessionStore';
import { AuthenticatedAppShell } from '../components/shell/AuthenticatedAppShell/AuthenticatedAppShell';
import { ShellAccessGuard } from '../components/shell/ShellAccessGuard/ShellAccessGuard';
import { ShellFallbackPanel } from '../components/shell/ShellFallbackPanel/ShellFallbackPanel';
import { getNavItemById } from '../shell/navigation';
import { PageSurface } from '../components/layout/PageSurface/PageSurface';
import { Typography } from '../components/layout/Typography/Typography';
import { ShellBrand } from '../components/shell/ShellBrand/ShellBrand';
import { TopHeader } from '../components/shell/TopHeader/TopHeader';
import { SidebarNavigation } from '../components/shell/SidebarNavigation/SidebarNavigation';
import { MobileBottomNavigation } from '../components/shell/MobileBottomNavigation/MobileBottomNavigation';
import styles from '../app/authPages.module.css';

function SeedAuth({ fixture }: { fixture: string }) {
  useEffect(() => {
    resetAuthStateForTests();
    resetDefaultAuthClient();
    if (fixture.includes('session-missing') || fixture.includes('tenant-missing')) {
      setBootstrapReady();
      return;
    }
    establishTenant(createMockSession(), createMockTenant());
    setBootstrapReady();
  }, [fixture]);
  return null;
}

function ShellSpecimenBody({ fixture }: { fixture: string }) {
  if (fixture === 'session-missing-guard') {
    return (
      <ShellAccessGuard forceState="session-missing">
        <div>Should not render</div>
      </ShellAccessGuard>
    );
  }
  if (fixture === 'tenant-missing-guard') {
    return (
      <ShellAccessGuard forceState="tenant-missing">
        <div>Should not render</div>
      </ShellAccessGuard>
    );
  }
  if (fixture === 'shell-loading') {
    return (
      <ShellAccessGuard forceState="loading">
        <div>Should not render</div>
      </ShellAccessGuard>
    );
  }
  if (fixture === 'blocked-command-center') {
    return <ShellFallbackPanel state="route-blocked" navItem={getNavItemById('command-center')} />;
  }
  if (fixture === 'blocked-claims') {
    return <ShellFallbackPanel state="route-blocked" navItem={getNavItemById('revenue-claims')} />;
  }
  if (fixture === 'blocked-integrations') {
    return <ShellFallbackPanel state="route-blocked" navItem={getNavItemById('integrations')} />;
  }
  if (fixture === 'unknown-route') {
    return <ShellFallbackPanel state="unknown-route" />;
  }
  if (fixture === 'sidebar-blocked-item') {
    return <SidebarNavigation activeNavId="revenue-claims" />;
  }
  if (fixture === 'mobile-more-open') {
    return <MobileBottomNavigation moreSheetOpen activeNavId="more" />;
  }
  if (fixture === 'mobile-bottom-nav') {
    return <MobileBottomNavigation activeNavId="channels" />;
  }

  return (
    <ShellAccessGuard>
      <Routes>
        <Route
          element={
            <AuthenticatedAppShell pageTitle="Skeldir" moreSheetOpen={fixture === 'mobile-more-open'} />
          }
        >
          <Route index element={<ShellFallbackPanel state="shell-landing" />} />
        </Route>
      </Routes>
    </ShellAccessGuard>
  );
}

export function Level2ShellSpecimens() {
  const [searchParams] = useSearchParams();
  const fixture = searchParams.get('fixture') ?? 'shell-default';

  return (
    <PageSurface>
      <SeedAuth fixture={fixture} />
      <div className={styles.page} data-specimen-root="level2-shell" style={{ alignItems: 'stretch' }}>
        <div style={{ width: '100%' }} data-specimen={fixture}>
          {fixture === 'header-only' ? (
            <TopHeader
              interfaceName="Overview"
              sidebarCollapsed={false}
              onSidebarToggle={() => undefined}
              chatOpen={false}
              onChatToggle={() => undefined}
            />
          ) : fixture === 'brand-only' ? (
            <ShellBrand />
          ) : (
            <>
              <Typography variant="h1" style={{ marginBottom: 'var(--sk-space-4)' }}>
                Level 2 Shell Specimens
              </Typography>
              <ShellSpecimenBody fixture={fixture} />
            </>
          )}
        </div>
      </div>
    </PageSurface>
  );
}

export function Level2ShellSpecimenRouter() {
  return (
    <MemoryRouter initialEntries={['/dev/shell-specimens']}>
      <Routes>
        <Route path="/dev/shell-specimens" element={<Level2ShellSpecimens />} />
      </Routes>
    </MemoryRouter>
  );
}
