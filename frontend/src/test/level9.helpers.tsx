import { screen, waitFor, within } from '@testing-library/react';
import type { UserEvent } from '@testing-library/user-event';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuditExportFlow } from '../actions/AuditExportFlow';
import { ClaimExportFlow } from '../actions/ClaimExportFlow';
import { expect, vi } from 'vitest';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { createMockSession, createMockTenant } from '../auth/authClient';
import { establishTenant, resetAuthStateForTests, setBootstrapReady, clearSession } from '../auth/sessionStore';
import { resetGovernanceStateForTests, setCurrentUserRole } from '../governance/governanceStore';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import { MAX_EXPORT_PREVIEW_DOM_NODES } from '../actions/bounds';
import { renderMountedTrustEnvelopeDrawer } from './level8.helpers';

export { renderMountedTrustEnvelopeDrawer };

export function seedShellAuth(role: 'owner' | 'viewer' | 'billing_only' = 'owner') {
  establishTenant(createMockSession(), createMockTenant());
  setBootstrapReady();
  setCurrentUserRole(role);
}

export function createDetailShellRouter(initialEntries: string[], initialIndex?: number) {
  return createMemoryRouter(
    [
      { path: '/app/*', element: <AppShellRoutes /> },
      { path: '/login', element: <div>Login</div> },
    ],
    { initialEntries, initialIndex },
  );
}

export function renderDetailRouter(router: ReturnType<typeof createMemoryRouter>) {
  return render(<RouterProvider router={router} />);
}

export function renderShell(initialPath: string) {
  const router = createDetailShellRouter([initialPath]);
  return { ...renderDetailRouter(router), router };
}

export function resetLevel9HarnessState() {
  resetAuthStateForTests();
  resetGovernanceStateForTests();
  clearSession();
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

export function countDomNodes(root: ParentNode = document.body): number {
  return root.querySelectorAll('*').length;
}

export async function waitForDetailLoaded(marker: string) {
  await waitFor(() => expect(document.querySelector(marker)).toBeTruthy());
}

export async function waitForOutcomeStatus(status: string) {
  await waitFor(() =>
    expect(document.querySelector(`[data-level9-outcome-status="${status}"]`)).toBeTruthy(),
  );
}

export const EXCEPTIONS_HARNESS_PATH =
  '/app/exceptions?dateFrom=2026-01-01&dateTo=2026-12-31&sortKey=createdAt&sortDirection=desc&offset=0';

export async function openExceptionDrawer(user: UserEvent) {
  renderShell(EXCEPTIONS_HARNESS_PATH);
  await waitForDetailLoaded('[data-exceptions-page]');
  await waitFor(() => expect(document.querySelector('[data-exception-detail-trigger]')).toBeTruthy());
  const trigger = document.querySelector('[data-exception-detail-trigger]') as HTMLButtonElement;
  await user.click(trigger);
  await waitForDetailLoaded('[data-exception-detail-modal]');
  await waitForDetailLoaded('[data-exception-detail-drawer]');
  await waitForDetailLoaded('[data-exception-action-controls]');
  expect(document.querySelector('[data-modal-panel]')).toBeTruthy();
  expect(document.querySelector('[data-drawer-panel]')).toBeNull();
}

export function renderMountedAuditExportFlow() {
  return render(
    <MemoryRouter>
      <AuditExportFlow policyAuthority="proposal_required" />
    </MemoryRouter>,
  );
}

export async function confirmGovernedAction(
  user: UserEvent,
  triggerName: RegExp | string,
  confirmLabel?: RegExp | string,
) {
  const trigger =
    typeof triggerName === 'string'
      ? screen.getByRole('button', { name: triggerName })
      : screen.getByRole('button', { name: triggerName });
  await user.click(trigger);
  await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeTruthy());
  const panel = document.querySelector('[data-level9-confirmation]')!;
  const dialog = panel.closest('[role="dialog"]') as HTMLElement;
  const label = confirmLabel ?? triggerName;
  const confirmName = typeof label === 'string' ? label : label;
  await user.click(within(dialog).getByRole('button', { name: confirmName }));
}

export async function openClaimDetailAuditTab(_user: UserEvent) {
  if (!document.querySelector('[data-claim-export-flow]')) {
    renderMountedClaimExportFlow();
  }
  await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
}

export function renderMountedClaimExportFlow(
  claimId = 'claim_0001',
  versionStamp = 'v_claim_0001_1',
  policyAuthority: 'blocked' | 'simulation_only' | 'proposal_required' | 'approval_required' | 'auto_executable_within_policy' = 'proposal_required',
) {
  return render(
    <MemoryRouter>
      <ClaimExportFlow
        claimId={claimId}
        versionStamp={versionStamp}
        policyAuthority={policyAuthority}
      />
    </MemoryRouter>,
  );
}

export function createClaimExportNavRouter(initialEntries: string[], initialIndex?: number) {
  return createMemoryRouter(
    [
      {
        path: '/export',
        element: (
          <ClaimExportFlow
            claimId="claim_0001"
            versionStamp="v_claim_0001_1"
            policyAuthority="proposal_required"
          />
        ),
      },
      { path: '/other', element: <div data-other-page>Other</div> },
    ],
    { initialEntries, initialIndex },
  );
}

export async function executeClaimExportSuccess(user: UserEvent) {
  renderMountedClaimExportFlow();
  await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
  await confirmGovernedAction(user, /Export verified report/i, /Export verified report/i);
  await waitForOutcomeStatus('success');
}

export async function executeBudgetProposalSuccess(user: UserEvent) {
  renderShell('/app/budget/sim_0001');
  await waitForDetailLoaded('[data-budget-detail-loaded]');
  await confirmGovernedAction(user, /Submit proposal/i, /Submit proposal/i);
  await waitForOutcomeStatus('success');
}

export async function executeAuditExportSuccess(user: UserEvent) {
  renderMountedAuditExportFlow();
  await waitFor(() => expect(document.querySelector('[data-audit-export-flow]')).toBeTruthy());
  await waitFor(() => expect(document.querySelector('[data-audit-reconstruction-preview]')).toBeTruthy());
  await confirmGovernedAction(user, /Export audit reconstruction/i, /Export audit reconstruction/i);
  await waitForOutcomeStatus('success');
}

export async function executeTrustExportArtifactSuccess(user: UserEvent) {
  renderMountedTrustEnvelopeDrawer('env_0001');
  await waitFor(() => expect(document.querySelector('[data-trust-envelope-operator-view]')).toBeTruthy());
  await user.click(screen.getByRole('button', { name: /Export report/i }));
  await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeTruthy());
  const panel = document.querySelector('[data-level9-confirmation]')!;
  const dialog = panel.closest('[role="dialog"]') as HTMLElement;
  await user.click(within(dialog).getByRole('button', { name: /Export report/i }));
  await waitForOutcomeStatus('success');
}

export async function executeExceptionActionSuccess(
  user: UserEvent,
  actionLabel: RegExp | string,
) {
  await openExceptionDrawer(user);
  const label = typeof actionLabel === 'string' ? actionLabel : actionLabel;
  await confirmGovernedAction(user, label, label);
  await waitForOutcomeStatus('success');
}

export function assertPreviewDomBounded(selector: string) {
  const preview = document.querySelector(selector);
  expect(preview).toBeTruthy();
  if (preview) {
    expect(countDomNodes(preview)).toBeLessThanOrEqual(MAX_EXPORT_PREVIEW_DOM_NODES);
  }
}

export function assertNoFalseSuccessIdentifiers() {
  expect(screen.queryByText(/^Artifact: artifact_/)).toBeNull();
  expect(screen.queryByText(/^Proposal: prop_/)).toBeNull();
}
