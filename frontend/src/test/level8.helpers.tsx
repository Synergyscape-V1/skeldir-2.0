import { render } from '@testing-library/react';
import { createMemoryRouter, MemoryRouter, RouterProvider } from 'react-router-dom';
import { useRef } from 'react';
import { vi } from 'vitest';
import { createMockSession, createMockTenant } from '../auth/authClient';
import { establishTenant, setBootstrapReady } from '../auth/sessionStore';
import { setCurrentUserRole } from '../governance/governanceStore';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import { TrustEnvelopeOperatorDrawer } from '../components/trust/TrustEnvelopeOperatorView/TrustEnvelopeOperatorDrawer';

export function seedShellAuth(role: 'owner' | 'viewer' | 'billing_only' = 'owner') {
  establishTenant(createMockSession(), createMockTenant());
  setBootstrapReady();
  setCurrentUserRole(role);
}

export function createDetailShellRouter(initialEntries: string[], initialIndex?: number) {
  return createMemoryRouter(
    [{ path: '/app/*', element: <AppShellRoutes /> }],
    { initialEntries, initialIndex },
  );
}

export function renderDetailRouter(router: ReturnType<typeof createMemoryRouter>) {
  return render(<RouterProvider router={router} />);
}

export function routerSearch(router: ReturnType<typeof createMemoryRouter>) {
  return router.state.location.search;
}

function MountedTrustEnvelopeDrawer({ envelopeId }: { envelopeId: string }) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  return (
    <>
      <button type="button" ref={triggerRef}>
        Open trust record
      </button>
      <TrustEnvelopeOperatorDrawer
        envelopeId={envelopeId}
        open
        onClose={() => undefined}
        triggerRef={triggerRef}
      />
    </>
  );
}

export function renderMountedTrustEnvelopeDrawer(envelopeId = 'env_0001') {
  return render(
    <MemoryRouter>
      <MountedTrustEnvelopeDrawer envelopeId={envelopeId} />
    </MemoryRouter>,
  );
}

export function setMobileViewport375() {
  Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 375 });
  Object.defineProperty(window, 'innerHeight', { writable: true, configurable: true, value: 812 });
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes('max-width: 767px'),
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
  vi.restoreAllMocks();
}
