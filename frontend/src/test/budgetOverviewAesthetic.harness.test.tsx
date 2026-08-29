import { describe, expect, it } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import { createMockSession, createMockTenant } from '../auth/authClient';
import { establishTenant, setBootstrapReady } from '../auth/sessionStore';
import { setCurrentUserRole } from '../governance/governanceStore';
import { resetDefaultBudgetInputClient } from '../budget/budgetInputClient';
import { resetDefaultBudgetSimulationClient } from '../budget/budgetSimulationClient';
import { resetDefaultBudgetSimulationDetailClient } from '../budget/budgetSimulationDetailClient';
import { resetBudgetProposalTestMode } from '../actions/budgetProposalClient';
import { BUDGET_DETAIL_COPY, BUDGET_SIMULATION_COPY } from '../budget/copy';
import {
  commercialPolishSabotageFixture,
  scanBudgetOverviewAesthetic,
} from '../audit/budgetOverviewAestheticScan';
import { PolicyImpactCard } from '../components/budget/PolicyImpactCard/PolicyImpactCard';
import type { BudgetSimulationResultDTO } from '../budget/budgetSimulationTypes';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

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

function renderBudgetDetail(path = '/app/budget/sim_0002?focus=policy') {
  establishTenant(createMockSession(), createMockTenant());
  setBootstrapReady();
  setCurrentUserRole('owner');
  const router = createMemoryRouter([{ path: '/app/*', element: <AppShellRoutes /> }], {
    initialEntries: [path],
  });
  return render(<RouterProvider router={router} />);
}

const SAMPLE_RESULT: BudgetSimulationResultDTO = {
  simulationId: 'sim_test_1',
  versionStamp: 'v1',
  currencyCode: 'USD',
  currentAllocation: [],
  simulatedAllocation: [],
  currentBlendedRoasBps: 310,
  currentTotalRevenueMinor: 10_500_000n,
  currentBlendedCacBps: 323,
  projectedBlendedRoasBps: 340,
  projectedTotalRevenueMinor: 11_487_000n,
  projectedBlendedCacBps: 294,
  expectedRevenueLiftBps: 940,
  blendedCacChangeBps: -710,
  spendDeltaBps: 0,
  impactAuthority: 'deterministic',
  sourceTrustEnvelopes: [],
  policyAuthority: 'approval_required',
  auditReference: 'aud_test_1',
  auditArtifactStatus: 'written',
};

describe('CRHAID 1 — Budget Overview aesthetic remediation', () => {
  describe('Positive: Proposal Preview currency formatting + confirmation gate', () => {
    it('formats verified revenue as locale currency and opens confirmation with same amount', async () => {
      resetBudgetHarness();
      renderBudgetDetail('/app/budget/sim_0002');

      await waitFor(() => {
        expect(document.querySelector('[data-proposal-preview]')).toBeTruthy();
      });

      const revenue = document.querySelector('[data-proposal-verified-revenue]');
      expect(revenue?.getAttribute('data-proposal-revenue-format')).toBe('locale-currency');
      expect(document.querySelector('[data-proposal-revenue-display]')?.textContent).toBe('$25,000.00');
      expect(revenue?.textContent ?? '').not.toMatch(/2500000/);
      expect(screen.queryByText(/2500000\s*USD/i)).not.toBeInTheDocument();

      const submit = screen.getByRole('button', { name: /Submit proposal|Approve & Advance/i });
      expect(submit).toBeEnabled();
      fireEvent.click(submit);

      await waitFor(() => {
        expect(document.querySelector('[data-proposal-confirmation-gate]')).toBeTruthy();
      });
      expect(document.querySelector('[data-proposal-confirmation-revenue]')?.textContent).toMatch(
        /\$25,000\.00/,
      );
    });
  });

  describe('Positive: Overview shell grammar on Budget Simulation Input', () => {
    it('renders display header stack, metadata, and policy notice', async () => {
      resetBudgetHarness();
      renderBudgetPage();

      await waitFor(() => {
        expect(document.querySelector('[data-simulation-input-card]')).toBeTruthy();
      });

      expect(screen.getByRole('heading', { name: BUDGET_SIMULATION_COPY.title })).toBeInTheDocument();
      expect(document.querySelector('[data-budget-header-row]')).toBeTruthy();
      expect(document.querySelector('[data-budget-simulation-header]')).toBeTruthy();
      expect(screen.getByText(BUDGET_SIMULATION_COPY.subtitle)).toBeInTheDocument();
      expect(screen.getByText(BUDGET_SIMULATION_COPY.metadataLine)).toBeInTheDocument();
      expect(screen.getByText(BUDGET_SIMULATION_COPY.policyBoundaryNotice)).toBeInTheDocument();
      expect(document.querySelector('[data-simulation-input-card][data-budget-elevated-panel]')).toBeTruthy();
      expect(document.querySelector('[data-budget-right-column]')).toBeTruthy();
    });
  });

  describe('Positive: Overview tile structure on Budget Simulation Detail (end-user surface)', () => {
    it('renders four summary tiles, Overview header grammar, and card panel grid', async () => {
      resetBudgetHarness();
      renderBudgetDetail();

      await waitFor(() => {
        expect(document.querySelector('[data-budget-detail-loaded]')).toBeTruthy();
      });

      expect(
        screen.getByRole('heading', { name: new RegExp(`${BUDGET_DETAIL_COPY.titlePrefix} sim_0002`, 'i') }),
      ).toBeInTheDocument();
      expect(document.querySelector('[data-budget-detail-header-row]')).toBeTruthy();
      expect(screen.getByText(BUDGET_DETAIL_COPY.subtitle)).toBeInTheDocument();
      expect(screen.getByText(BUDGET_DETAIL_COPY.metadataLine)).toBeInTheDocument();

      const summary = document.querySelector('[data-budget-detail-summary-row]');
      expect(summary).toBeTruthy();
      expect(summary?.querySelectorAll('[data-summary-metric]')).toHaveLength(4);
      expect(summary?.querySelector('[data-summary-metric="verified_revenue_basis"]')).toBeTruthy();
      expect(summary?.querySelector('[data-summary-metric="policy_authority"]')).toBeTruthy();
      expect(summary?.querySelector('[data-summary-metric="confidence"]')).toBeTruthy();
      expect(summary?.querySelector('[data-summary-metric="simulation_status"]')).toBeTruthy();

      expect(document.querySelector('[data-budget-detail-panel-grid]')).toBeTruthy();
      expect(document.querySelectorAll('[data-budget-detail-panel]').length).toBeGreaterThanOrEqual(6);
      expect(document.querySelector('[data-budget-policy-authority-section]')).toBeTruthy();
    });
  });

  describe('Positive: Framework D commercial polish scan', () => {
    it('passes with zero violations on live Budget surfaces', () => {
      const violations = scanBudgetOverviewAesthetic();
      expect(violations).toEqual([]);
    });
  });

  describe('Negative: Scan catches Overview-divergent anti-patterns', () => {
    it('flags parallel elevation, zero radius, and rgba hover when reintroduced', () => {
      const panelPath = 'src/components/budget/budgetPanel.module.css';
      const violations = scanBudgetOverviewAesthetic({
        panelCss: `
.elevatedPanel {
  box-shadow: var(--sk-elevation-card);
}
.elevatedPanel:hover {
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
}
`,
        inputPageCss: `
.page {
  --sk-elevation-budget-panel: 0 1px 2px rgba(15, 23, 42, 0.06);
  gap: var(--sk-space-6);
}
`,
        inputCardCss: `.chip { border-radius: 0; }`,
        rightColumnCss: `
.submitButton:not(:disabled):hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12);
}
`,
        headerTsx: '<header>Budget</header>',
        copyTs: 'export const BUDGET_SIMULATION_COPY = { title: "Budget Simulation" }',
        cssFiles: {
          [panelPath]: commercialPolishSabotageFixture(),
        },
      });

      const rules = new Set(violations.map((v) => v.rule));
      expect(rules.has('D-no-static-panel-hover-lift')).toBe(true);
      expect(rules.has('D-overview-border-first')).toBe(true);
      expect(rules.has('D-no-parallel-elevation-system')).toBe(true);
      expect(rules.has('D-page-rhythm')).toBe(true);
      expect(rules.has('D-chip-radius')).toBe(true);
      expect(rules.has('D-cta-shadow-theater')).toBe(true);
      expect(rules.has('D-cta-hover-lift')).toBe(true);
      expect(rules.has('D-header-grammar')).toBe(true);
      expect(rules.has('D-header-metadata')).toBe(true);
      expect(rules.has('D-copy-metadata')).toBe(true);
      expect(rules.has('D-no-gradient')).toBe(true);
      expect(rules.has('D-radius-hierarchy')).toBe(true);
      expect(rules.has('D-no-hardcoded-rgba-shadow')).toBe(true);
    });
  });

  describe('Meta-negative: harness is non-vacuous', () => {
    it('sabotage fixture always produces violations', () => {
      const sabotage = commercialPolishSabotageFixture();
      expect(sabotage).toMatch(/rgba\(/);
      expect(sabotage).toMatch(/border-radius:\s*0/);
      expect(sabotage).toMatch(/linear-gradient/);

      const violations = scanBudgetOverviewAesthetic({
        cssFiles: { 'sabotage.module.css': sabotage },
        panelCss: '.elevatedPanel { box-shadow: none; }',
        inputPageCss: '.page { gap: var(--spacing-24); }',
        inputCardCss: '.chip { border-radius: var(--sk-radius-sm); }',
        rightColumnCss: '.submitButton { }',
        headerTsx:
          '<div data-budget-header-row><header className={styles.pageHeaderStack}>{BUDGET_SIMULATION_COPY.metadataLine}</header></div>',
        copyTs: 'metadataLine: "x",',
      });

      expect(violations.length).toBeGreaterThan(0);
      expect(violations.some((v) => v.rule === 'D-no-gradient')).toBe(true);
    });
  });

  describe('Positive: functional budget cards still render under new DNA', () => {
    it('PolicyImpactCard renders baseline/projected without crash', () => {
      render(<PolicyImpactCard result={SAMPLE_RESULT} />);
      expect(screen.getByText('Current ROAS')).toBeInTheDocument();
      expect(screen.getByText('Projected ROAS')).toBeInTheDocument();
    });
  });

  describe('Source proof: budgetPanel is border-first', () => {
    it('budgetPanel.module.css has no hover lift and no elevation-card', () => {
      const css = readFileSync(
        join(import.meta.dirname, '../components/budget/budgetPanel.module.css'),
        'utf8',
      );
      expect(css).not.toMatch(/elevatedPanel:hover/);
      expect(css).not.toMatch(/--sk-elevation-card/);
      expect(css).toMatch(/box-shadow:\s*none/);
      expect(css).toMatch(/--radius-card/);
      expect(css).toMatch(/--spacing-24/);
    });
  });
});
