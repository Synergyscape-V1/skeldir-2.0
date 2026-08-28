import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CommandCenterPage } from '../components/commandCenter/CommandCenterPage/CommandCenterPage';
import { expect, vi } from 'vitest';
import { createMemoryRouter } from 'react-router-dom';
import { createMockSession, createMockTenant } from '../auth/authClient';
import {
  establishSession,
  establishTenant,
  resetAuthStateForTests,
  setBootstrapReady,
  clearSession,
} from '../auth/sessionStore';
import { resetGovernanceStateForTests, setCurrentUserRole } from '../governance/governanceStore';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import {
  resetDefaultCommandCenterClient,
  resetCommandCenterTestMode,
  setCommandCenterTestMode,
  setCommandCenterDelayForTests,
  setCommandCenterSubstrateOverridesForTests,
} from '../commandCenter/commandCenterClient';
import { resetDefaultRevenueSnapshotClient } from '../commandCenter/revenueSnapshotClient';
import { resetTriageQueueSession } from '../commandCenter/triageQueueStore';
import { resetSyntheticClaimsDataset } from '../claims/claimsClient';
import { COMMAND_CENTER_COPY } from '../commandCenter/copy';
import { renderDetailRouter } from './level9.helpers';

export function seedShellAuth(role: 'owner' | 'viewer' | 'billing_only' = 'owner') {
  establishTenant(createMockSession(), createMockTenant());
  setBootstrapReady();
  setCurrentUserRole(role);
}

export function seedShellAuthWithoutTenant(role: 'owner' | 'viewer' | 'billing_only' = 'owner') {
  establishSession(createMockSession(), null);
  setBootstrapReady();
  setCurrentUserRole(role);
}

export function setDesktopViewport1280() {
  Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 1280 });
  Object.defineProperty(window, 'innerHeight', { writable: true, configurable: true, value: 800 });
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes('min-width: 1024px') || query.includes('min-width: 1280px'),
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

export function setDesktopViewport1440() {
  Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 1440 });
  Object.defineProperty(window, 'innerHeight', { writable: true, configurable: true, value: 900 });
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches:
      query.includes('min-width: 1024px') ||
      query.includes('min-width: 1280px') ||
      query.includes('min-width: 1440px'),
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

export function resetViewport() {
  Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 1024 });
  Object.defineProperty(window, 'innerHeight', { writable: true, configurable: true, value: 768 });
  window.matchMedia = vi.fn().mockImplementation(() => ({
    matches: false,
    media: '',
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

export function renderCommandCenter(initialPath = '/app') {
  const router = createMemoryRouter(
    [
      { path: '/app/*', element: <AppShellRoutes /> },
      { path: '/login', element: <div>Login</div> },
    ],
    { initialEntries: [initialPath] },
  );
  return { ...renderDetailRouter(router), router };
}

export function renderCommandCenterPageOnly() {
  return render(
    <MemoryRouter>
      <CommandCenterPage />
    </MemoryRouter>,
  );
}

export function resetLevel10HarnessState() {
  resetAuthStateForTests();
  resetGovernanceStateForTests();
  resetSyntheticClaimsDataset();
  resetDefaultCommandCenterClient();
  resetDefaultRevenueSnapshotClient();
  resetCommandCenterTestMode();
  setCommandCenterSubstrateOverridesForTests(null);
  setCommandCenterDelayForTests(0);
  resetTriageQueueSession();
  clearSession();
}

export async function waitForCommandCenterLoaded() {
  await waitFor(() =>
    expect(document.querySelector('[data-command-center-loaded="true"]')).toBeTruthy(),
  );
}

export async function waitForCommandCenterMarker(marker: string) {
  await waitFor(() => expect(document.querySelector(marker)).toBeTruthy());
}

export { screen, waitFor };
