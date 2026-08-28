import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { createMockSession, createMockTenant, createMockUserProfile } from '../auth/authClient';
import { AUTH_COPY } from '../auth/copy';
import {
  defaultShellPath,
  resolveSafeRedirect,
  LEVEL4_PLUS_BLOCKED_ROUTES,
  LEVEL8_PLUS_BLOCKED_ROUTES,
} from '../auth/redirectGuard';
import {
  clearSession,
  establishSession,
  establishTenant,
  getAuthState,
  resetAuthStateForTests,
  setBootstrapReady,
} from '../auth/sessionStore';
import { runLevel1NegativeScopeScan } from '../audit/level1NegativeScopeScan';
import { runNegativeScopeScan } from '../audit/negativeScopeScan';
import {
  assertLevel2ComponentsExist,
  assertLevel2RoutesExist,
  assertNoDashboardInShellSource,
  assertNoHealthStripInShellSource,
  runLevel2NegativeScopeScan,
  runLevel2SabotageProbes,
} from '../audit/level2NegativeScopeScan';
import {
  runSidebarToggleIntegrityProbes,
  runSidebarToggleSabotageProbes,
} from '../audit/sidebarToggleNegativeScopeScan';
import { runTokenAudit } from '../audit/tokenAudit';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import { LoginPage } from '../app/routes/AuthRoutes';
import { AuthEntryFlow } from '../components/auth/AuthEntryFlow/AuthEntryFlow';
import { AuthenticatedAppShell } from '../components/shell/AuthenticatedAppShell/AuthenticatedAppShell';
import { ShellAccessGuard } from '../components/shell/ShellAccessGuard/ShellAccessGuard';
import { ShellFallbackPanel } from '../components/shell/ShellFallbackPanel/ShellFallbackPanel';
import { ROUTE_RECOVERY_COPY } from '../routeRecovery/copy';
import { SHELL_COPY } from '../shell/copy';
import { getNavItemById, shellNavPath } from '../shell/navigation';

function renderShell(initialPath = '/app') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/app/*" element={<AppShellRoutes />} />
        <Route path="/login" element={<div>Login page</div>} />
        <Route path="/signup" element={<AuthEntryFlow dataRoute="/signup" />} />
      </Routes>
    </MemoryRouter>,
  );
}

function seedShellAuth() {
  establishTenant(createMockSession(), createMockTenant(), createMockUserProfile());
  setBootstrapReady();
}

describe('Level 2 Harness — Scope and regression', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    clearSession();
  });

  it('Level 0 negative scope still passes', () => {
    expect(runNegativeScopeScan().violations).toEqual([]);
  });

  it('Level 1 negative scope still passes', () => {
    expect(runLevel1NegativeScopeScan().violations).toEqual([]);
  });

  it('Level 2 negative scope passes', () => {
    expect(runLevel2NegativeScopeScan().violations).toEqual([]);
  });

  it('Level 2 routes and components exist', () => {
    expect(assertLevel2RoutesExist()).toEqual({ ok: true, missing: [] });
    expect(assertLevel2ComponentsExist()).toEqual({ ok: true, missing: [] });
  });

  it('token audit passes including shell surfaces', () => {
    expect(runTokenAudit().violations).toEqual([]);
  });
});

describe('Level 2 Harness — Shell access guard', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    clearSession();
  });

  it('positive: shell renders with session and tenant', async () => {
    seedShellAuth();
    renderShell();
    expect(screen.getByRole('navigation', { name: SHELL_COPY.sidebarLabel })).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { level: 1, name: /Overview|App frame ready/ }),
      ).toBeInTheDocument(),
    );
  });

  it('negative: no session redirects away from shell', () => {
    setBootstrapReady();
    renderShell();
    expect(screen.getByText('Login page')).toBeInTheDocument();
  });

  it('negative: session without tenant redirects to workspace creation', async () => {
    establishSession(createMockSession());
    setBootstrapReady();
    renderShell();
    await waitFor(() => {
      expect(document.querySelector('[data-create-organization-modal]')).toBeTruthy();
    });
    expect(screen.getByText(AUTH_COPY.createOrganizationTitle)).toBeInTheDocument();
  });

  it('negative: loading state does not render shell navigation', () => {
    resetAuthStateForTests();
    render(
      <MemoryRouter>
        <ShellAccessGuard forceState="loading">
          <div>Protected shell</div>
        </ShellAccessGuard>
      </MemoryRouter>,
    );
    expect(screen.queryByText('Protected shell')).not.toBeInTheDocument();
    expect(screen.queryByText(SHELL_COPY.shellLoading)).not.toBeInTheDocument();
    expect(document.querySelector('[data-timed-loading]')).toBeTruthy();
  });
});

describe('Level 2 Harness — Navigation and blocked routes', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    seedShellAuth();
  });

  it('positive: /app renders Overview at Level 10', async () => {
    renderShell();
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1, name: 'Overview' })).toBeInTheDocument(),
    );
    expect(document.querySelector('[data-priority-queue-open]')).toBeTruthy();
    expect(screen.getByText(/blocking your budget/i)).toBeInTheDocument();
  });

  it('positive: Overview nav routes to /app aggregate surface', async () => {
    const user = userEvent.setup();
    renderShell('/app/claims');
    const overviewLinks = screen.getAllByRole('link', { name: /^Overview$/i });
    await user.click(overviewLinks[0]!);
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1, name: 'Overview' })).toBeInTheDocument(),
    );
  });

  it('positive: revenue claims nav routes to Level 7 ledger', async () => {
    renderShell(shellNavPath('revenue-claims'));
    await waitFor(() => {
      expect(document.querySelector('[data-claims-ledger-page]')).toBeInTheDocument();
    });
  });

  it('negative: unknown authenticated shell route shows recovery panel', () => {
    renderShell('/app/unknown/path');
    expect(screen.getByText(ROUTE_RECOVERY_COPY.notFoundTitle)).toBeInTheDocument();
    expect(document.querySelector('[data-route-recovery-panel]')).toBeTruthy();
  });
});

describe('Level 2 Harness — Layout landmarks', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    seedShellAuth();
  });

  it('positive: shell exposes skip link and main landmark', () => {
    renderShell();
    expect(screen.getByRole('link', { name: SHELL_COPY.skipToContent })).toBeInTheDocument();
    expect(screen.getByRole('main')).toBeInTheDocument();
  });

  it('positive: header shows tenant welcome on Overview', () => {
    renderShell();
    const welcome = SHELL_COPY.welcomeBack('Acme RevOps');
    expect(screen.getByRole('status', { name: welcome })).toHaveTextContent(welcome);
    expect(document.querySelector('[data-interface-welcome="true"]')).toBeTruthy();
  });

  it('positive: header exposes desktop sidebar toggle', () => {
    renderShell();
    const toggle = document.querySelector('[data-sidebar-toggle]');
    expect(toggle).toBeTruthy();
    expect(toggle?.querySelector('[data-sidebar-toggle-icon="close"]')).toBeTruthy();
  });

  it('positive: header exposes workspace assistant toggle', () => {
    renderShell();
    const toggle = document.querySelector('[data-chat-toggle]');
    expect(toggle).toBeTruthy();
    expect(toggle).toHaveAttribute('aria-controls', 'shell-chat-panel');
    expect(toggle?.querySelector('[data-chat-toggle-icon="open"]')).toBeTruthy();
  });

  it('positive: workspace assistant panel opens from header toggle', async () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 1900 });
    const user = userEvent.setup();
    renderShell();
    await user.click(document.querySelector('[data-chat-toggle]') as HTMLElement);
    expect(document.querySelector('[data-shell-chat-panel]')).toBeTruthy();
    expect(screen.getByRole('heading', { name: SHELL_COPY.chatPanelTitle })).toBeInTheDocument();
    expect(document.querySelector('[data-chat-panel-resize-handle]')).toBeTruthy();
    expect(screen.getByRole('tablist', { name: SHELL_COPY.chatTabsLabel })).toBeInTheDocument();
  });

  it('positive: workspace assistant overlays main content on laptop viewports', async () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 1280 });
    const user = userEvent.setup();
    renderShell();
    const shell = document.querySelector('[data-authenticated-app-shell]');
    await user.click(document.querySelector('[data-chat-toggle]') as HTMLElement);
    expect(shell).toHaveAttribute('data-shell-chat-open', 'true');
    expect(shell).toHaveAttribute('data-shell-chat-layout', 'overlay');
    expect(document.querySelector('[data-shell-chat-column]')).toBeTruthy();
    expect(document.querySelector('[data-shell-chat-backdrop]')).toBeTruthy();
    expect(document.querySelector('[data-chat-panel-resize-handle]')).toBeNull();
  });

  it('positive: workspace assistant docks beside content on wide viewports', async () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 1900 });
    const user = userEvent.setup();
    renderShell();
    const shell = document.querySelector('[data-authenticated-app-shell]');
    await user.click(document.querySelector('[data-chat-toggle]') as HTMLElement);
    expect(shell).toHaveAttribute('data-shell-chat-open', 'true');
    expect(shell).toHaveAttribute('data-shell-chat-layout', 'docked');
  });

  it('positive: workspace assistant supports multiple agent tabs', async () => {
    const user = userEvent.setup();
    renderShell();
    await user.click(document.querySelector('[data-chat-toggle]') as HTMLElement);
    await user.click(screen.getByRole('button', { name: SHELL_COPY.chatNewSession }));
    expect(screen.getAllByRole('tab')).toHaveLength(2);
    await user.click(screen.getAllByRole('tab')[0]);
    expect(document.querySelector('[data-chat-active-session]')).toBeTruthy();
  });

  it('positive: sidebar toggle integrity probes pass', () => {
    const failed = runSidebarToggleIntegrityProbes().filter((probe) => !probe.ok);
    expect(failed).toEqual([]);
  });

  it('negative: sidebar toggle sabotage probes stay armed', () => {
    const triggered = runSidebarToggleSabotageProbes().filter((probe) => probe.triggered);
    expect(triggered).toEqual([]);
  });

  it('positive: sidebar brand exposes notification control', () => {
    renderShell();
    expect(document.querySelector('[data-shell-brand] [data-notification-bell]')).toBeTruthy();
  });

  it('positive: mobile bottom navigation exists in DOM', () => {
    renderShell();
    expect(screen.getByRole('navigation', { name: SHELL_COPY.bottomNavLabel })).toBeInTheDocument();
  });

  it('positive: sidebar account shows initials and email', () => {
    renderShell();
    expect(document.querySelector('[data-shell-sidebar-account]')).toBeTruthy();
    expect(screen.getByText('engineering@skeldir.com')).toBeInTheDocument();
    expect(screen.getByLabelText(SHELL_COPY.accountInitialsLabel('AO'))).toHaveTextContent('AO');
  });

  it('positive: sidebar account menu exposes logout', async () => {
    const user = userEvent.setup();
    renderShell();
    await user.click(screen.getByRole('button', { name: SHELL_COPY.accountMenuLabel }));
    expect(screen.getByRole('menuitem', { name: SHELL_COPY.accountMenuLogout })).toBeInTheDocument();
  });

  it('positive: logout clears session and returns to sign-in identity modal', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/app']}>
        <Routes>
          <Route path="/app/*" element={<AppShellRoutes />} />
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await user.click(screen.getByRole('button', { name: SHELL_COPY.accountMenuLabel }));
    await user.click(screen.getByRole('menuitem', { name: SHELL_COPY.accountMenuLogout }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: AUTH_COPY.identityWelcomeTitle })).toBeInTheDocument();
    });
    expect(getAuthState().session).toBeNull();
    expect(document.querySelector('[data-shell-sidebar-account]')).toBeNull();
  });
});

describe('Level 2 Harness — Redirect guard Level 2 integration', () => {
  it('allows /app when session and tenant exist', () => {
    expect(resolveSafeRedirect('/app', { hasSession: true, hasTenant: true }, defaultShellPath())).toEqual({
      ok: true,
      path: '/app',
    });
  });

  it('blocks /app without tenant', () => {
    expect(resolveSafeRedirect('/app', { hasSession: true, hasTenant: false }, defaultShellPath()).ok).toBe(false);
  });

  it('allows Level 3 onboarding route with session and tenant', () => {
    expect(resolveSafeRedirect('/onboarding', { hasSession: true, hasTenant: true }, defaultShellPath())).toEqual({
      ok: true,
      path: '/app/onboarding',
    });
  });

  it('allows product /claims route at Level 7', () => {
    expect(resolveSafeRedirect('/claims', { hasSession: true, hasTenant: true }, defaultShellPath())).toEqual({
      ok: true,
      path: '/app/claims',
    });
  });
});

describe('Level 2 Harness — No health or dashboard semantics', () => {
  it('source scan finds no health strip terms', () => {
    expect(assertNoHealthStripInShellSource()).toBe(true);
  });

  it('source scan finds no dashboard aggregate terms', () => {
    expect(assertNoDashboardInShellSource()).toBe(true);
  });

  it('shell landing panel explicitly denies Overview semantics', () => {
    render(<ShellFallbackPanel state="shell-landing" />);
    expect(screen.getByText(/not the Overview/i)).toBeInTheDocument();
  });
});

describe('Level 2 Harness — Sabotage controls', () => {
  it('meta-negative: sabotage probes detect injected health strip', () => {
    const sabotaged = 'export function Bad() { return "All systems operational"; }';
    const results = runLevel2SabotageProbes(sabotaged);
    expect(results.find((r) => r.name === 'health-strip')?.pass).toBe(true);
  });

  it('meta-negative: sabotage probes detect injected claims route', () => {
    const sabotaged = '<Route path="/claims" element={<Claims />} />';
    const results = runLevel2SabotageProbes(sabotaged);
    expect(results.find((r) => r.name === 'claims-route')?.pass).toBe(true);
  });

  it('meta-negative: clean shell source passes sabotage probes', () => {
    const clean = 'AuthenticatedAppShell SidebarNavigation ShellBrand TopHeader';
    const results = runLevel2SabotageProbes(clean);
    const violationProbes = results.filter((r) => r.name !== 'clean-shell');
    expect(violationProbes.every((r) => r.detected === false)).toBe(true);
    expect(results.find((r) => r.name === 'clean-shell')?.pass).toBe(true);
  });

  it('meta-negative: Level 4 routes remain in blocklist', () => {
    expect(LEVEL4_PLUS_BLOCKED_ROUTES).not.toContain('/onboarding');
  });

  it('LEVEL8_PLUS_BLOCKED_ROUTES is empty after Level 11', () => {
    expect(LEVEL8_PLUS_BLOCKED_ROUTES).toEqual([]);
  });
});

describe('Level 2 Harness — Handoff integration copy', () => {
  it('auth copy no longer claims shell unavailable', () => {
    expect(AUTH_COPY.handoffSessionBody).not.toMatch(/not yet available/i);
    expect(AUTH_COPY.enterAppFrame).toBeTruthy();
  });

  it('blocked nav item references future level not fake content', () => {
    const item = getNavItemById('command-center');
    expect(item.unlockLabel).toMatch(/Level 10/);
  });
});
