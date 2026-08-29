import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import { createMockSession, createMockTenant } from '../auth/authClient';
import { establishTenant, setBootstrapReady } from '../auth/sessionStore';
import { setCurrentUserRole } from '../governance/governanceStore';
import { resetDefaultBudgetInputClient } from '../budget/budgetInputClient';
import { resetDefaultBudgetSimulationClient } from '../budget/budgetSimulationClient';
import { resetDefaultBudgetSimulationDetailClient } from '../budget/budgetSimulationDetailClient';
import { resetBudgetProposalTestMode } from '../actions/budgetProposalClient';
import { BUDGET_SIMULATION_COPY } from '../budget/copy';

function resetBudgetHarness() {
  resetDefaultBudgetInputClient();
  resetDefaultBudgetSimulationClient();
  resetDefaultBudgetSimulationDetailClient();
  resetBudgetProposalTestMode();
}

function renderBudgetPage() {
  establishTenant(createMockSession(), createMockTenant());
  setBootstrapReady();
  setCurrentUserRole('owner');
  const router = createMemoryRouter([{ path: '/app/*', element: <AppShellRoutes /> }], {
    initialEntries: ['/app/budget'],
  });
  return render(<RouterProvider router={router} />);
}

describe('Budget Simulation page harness', () => {
  beforeEach(() => {
    resetBudgetHarness();
  });

  it('renders spec header, disclaimer, five-field form, readiness, and authority panel', async () => {
    renderBudgetPage();

    await waitFor(() => {
      expect(document.querySelector('[data-simulation-input-card]')).toBeTruthy();
    });

    expect(screen.getByRole('heading', { name: BUDGET_SIMULATION_COPY.title })).toBeInTheDocument();
    expect(screen.getByText(BUDGET_SIMULATION_COPY.subtitle)).toBeInTheDocument();
    expect(screen.getByText(BUDGET_SIMULATION_COPY.metadataLine)).toBeInTheDocument();
    expect(screen.getByText(BUDGET_SIMULATION_COPY.policyBoundaryNotice)).toBeInTheDocument();
    expect(document.querySelector('[data-budget-header-row]')).toBeTruthy();
    expect(screen.getByLabelText(/Date range/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Spend constraint/i)).toBeInTheDocument();
    expect(screen.queryByText('Required', { exact: true })).not.toBeInTheDocument();
    expect(screen.getByDisplayValue('$125,000.00')).toBeInTheDocument();
    expect(screen.getByLabelText(/Objective/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Required minimum verified revenue window/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Paid Search/i })).toBeInTheDocument();
    expect(document.querySelector('[data-input-authority-panel]')).toBeTruthy();
    expect(screen.getByRole('status', { name: BUDGET_SIMULATION_COPY.inputAuthority.title })).toBeInTheDocument();
    expect(screen.getByText(BUDGET_SIMULATION_COPY.inputAuthority.eligible)).toBeInTheDocument();
    expect(screen.getByText('Deterministic evidence present')).toBeInTheDocument();
    expect(screen.queryByText(/proposal preview/i)).not.toBeInTheDocument();
    expect(document.querySelector('[data-budget-right-column]')).toBeTruthy();
    expect(screen.getByRole('button', { name: BUDGET_SIMULATION_COPY.generate.label })).toBeInTheDocument();

    const readiness = document.querySelector('[data-sufficiency-gate-summary]');
    expect(readiness?.textContent).not.toMatch(/Passed\s*·\s*Passed/);
    expect(readiness?.textContent).not.toMatch(/Available\s*·\s*Available/);
    expect(readiness?.getAttribute('data-budget-inset-panel')).toBe('true');
    expect(readiness?.getAttribute('data-budget-elevated-panel')).toBeNull();

    const inputCard = document.querySelector('[data-simulation-input-card]');
    const generateButton = document.querySelector('[data-generate-simulation-button]');
    expect(inputCard?.contains(generateButton ?? null)).toBe(false);
    expect(document.querySelector('[data-simulation-input-card][data-budget-elevated-panel]')).toBeTruthy();

    const mainColumn = document.querySelector('[data-shell-main-column]');
    const contentRail = document.querySelector('[data-page-content-rail]');
    if (mainColumn && contentRail) {
      const mainColumnRect = mainColumn.getBoundingClientRect();
      const railRect = contentRail.getBoundingClientRect();
      const leftInset = railRect.left - mainColumnRect.left;
      const rightInset = mainColumnRect.right - railRect.right;
      expect(Math.abs(leftInset - rightInset)).toBeLessThanOrEqual(2);
    }
  });

  it('positive control: generate reveals result region, impact, envelopes, and submit', async () => {
    renderBudgetPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: BUDGET_SIMULATION_COPY.generate.label })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole('button', { name: BUDGET_SIMULATION_COPY.generate.label }));

    await waitFor(() => {
      expect(document.querySelector('[data-simulation-result-region]')).toBeTruthy();
    });

    expect(screen.getByText(BUDGET_SIMULATION_COPY.allocation.current)).toBeInTheDocument();
    expect(screen.getByText(BUDGET_SIMULATION_COPY.allocation.simulated)).toBeInTheDocument();
    expect(screen.getByText(BUDGET_SIMULATION_COPY.expectedImpact.title)).toBeInTheDocument();
    expect(screen.getByText(BUDGET_SIMULATION_COPY.sourceEnvelopes.caption)).toBeInTheDocument();
    expect(document.querySelector('[data-policy-authority-card]')).toBeTruthy();
    expect(document.querySelector('[data-audit-artifact-status-card]')).toBeTruthy();

    const rightColumn = document.querySelector('[data-budget-right-column]');
    expect(rightColumn?.querySelector('[data-input-authority-panel]')).toBeTruthy();
    expect(rightColumn?.querySelector('[data-policy-authority-card]')).toBeTruthy();
    expect(rightColumn?.querySelector('[data-audit-artifact-status-card]')).toBeTruthy();
    expect(rightColumn?.querySelector('[data-submit-proposal-button]')).toBeTruthy();

    expect(
      screen.getByRole('button', { name: BUDGET_SIMULATION_COPY.submit.label }),
    ).toBeInTheDocument();
    expect(screen.getByText(BUDGET_SIMULATION_COPY.submit.caption)).toBeInTheDocument();
    expect(screen.getByText(BUDGET_SIMULATION_COPY.toast.generateSuccess)).toBeInTheDocument();

    expect(document.querySelector('[data-allocation-comparison-card]')).toBeTruthy();
    expect(document.querySelectorAll('[data-allocation-panel]')).toHaveLength(0);
    expect(document.querySelectorAll('[data-allocation-column]')).toHaveLength(2);
    expect(document.querySelector('[data-expected-impact-panel][data-budget-elevated-panel]')).toBeTruthy();
    expect(document.querySelector('[data-source-trust-envelopes-table][data-budget-elevated-panel]')).toBeTruthy();

    const elevatedInRight = document.querySelectorAll('[data-budget-right-column] [data-budget-elevated-panel]');
    expect(elevatedInRight.length).toBeGreaterThanOrEqual(3);
  });

  it('negative control: removing channels below minimum blocks generate', async () => {
    renderBudgetPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Paid Search/i })).toBeInTheDocument();
    });

    for (const label of ['Paid Search', 'Paid Social', 'Affiliate']) {
      fireEvent.click(screen.getByRole('button', { name: new RegExp(label, 'i') }));
    }

    expect(screen.getByRole('button', { name: BUDGET_SIMULATION_COPY.generate.label })).toBeDisabled();
    expect(document.querySelector('[data-blocked-sparse-data-panel]')).toBeTruthy();
  });

  it('meta-negative: stale banner disables submit after input change post-generate', async () => {
    renderBudgetPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: BUDGET_SIMULATION_COPY.generate.label })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole('button', { name: BUDGET_SIMULATION_COPY.generate.label }));

    await waitFor(() => {
      expect(document.querySelector('[data-simulation-result-region]')).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText(/Objective/i), {
      target: { value: 'maximize_within_constraint' },
    });

    expect(screen.getByText(BUDGET_SIMULATION_COPY.staleBanner)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: BUDGET_SIMULATION_COPY.submit.label })).toBeDisabled();
  });
});
