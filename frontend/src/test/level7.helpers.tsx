import { render, screen, waitFor, within } from '@testing-library/react';
import { createMemoryRouter, RouterProvider, type Router } from 'react-router-dom';
import { expect, vi } from 'vitest';
import { AppShellRoutes } from '../app/routes/ShellRoutes';

export function setMobileViewport375(): void {
  Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 375 });
  Object.defineProperty(window, 'innerHeight', { writable: true, configurable: true, value: 812 });
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: /max-width:\s*767px/.test(query),
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

export function resetViewport(): void {
  Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 1024 });
  Object.defineProperty(window, 'innerHeight', { writable: true, configurable: true, value: 768 });
  vi.restoreAllMocks();
}

export function createClaimsShellRouter(initialEntries: string[], initialIndex = 0): Router {
  return createMemoryRouter(
    [
      { path: '/app/*', element: <AppShellRoutes /> },
      { path: '/login', element: <div>Login page</div> },
    ],
    { initialEntries, initialIndex },
  );
}

export function renderClaimsRouter(router: Router) {
  return render(<RouterProvider router={router} />);
}

export function routerSearch(router: Router): string {
  return router.state.location.search;
}

function claimsFilterRegion() {
  return within(screen.getByLabelText('Claims ledger filters'));
}

export function claimsFilterComboboxes() {
  return claimsFilterRegion().getAllByRole('combobox');
}

export function claimsClaimSourceFilter() {
  return claimsFilterRegion().getByLabelText(/^Claim source \(platform\)$/i);
}

export function claimsCampaignClassFilter() {
  return claimsFilterRegion().getByLabelText(/^Campaign class$/i);
}

export function claimsCommerceRailFilter() {
  return claimsFilterRegion().getByLabelText(/^Commerce rail$/i);
}

export function claimsVerificationStatusFilter() {
  return claimsFilterRegion().getByLabelText(/^Verification status$/i);
}

export function claimsSortFilter() {
  return claimsFilterRegion().getByLabelText(/^Sort by$/i);
}

export async function waitForClaimsTableRows() {
  await waitFor(() => expect(document.querySelector('[data-claims-ledger-page]')).toBeInTheDocument());
  await waitFor(() => expect(document.querySelector('[data-claims-ledger-table] tbody tr')).toBeTruthy());
}
