import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { createMockSession, createMockTenant } from '../auth/authClient';
import { establishTenant, resetAuthStateForTests, setBootstrapReady } from '../auth/sessionStore';
import { resetGovernanceStateForTests, setCurrentUserRole } from '../governance/governanceStore';
import { CLAIMS_LEDGER_PAGE_COPY } from '../claims/copy';
import {
  createClaimsLedgerClient,
  resetClaimsListDelayForTests,
  resetDefaultClaimsLedgerClient,
  resetSyntheticClaimsDataset,
  setDefaultClaimsLedgerClient,
} from '../claims/claimsClient';
import { parseClaimsFilters } from '../claims/parseClaimsFilters';
import { ClaimsLedgerPageHeader } from '../components/claims/ClaimsLedgerPage/ClaimsLedgerPageHeader';
import {
  createClaimsShellRouter,
  renderClaimsRouter,
  waitForClaimsTableRows,
} from './level7.helpers';

function seedClaimsShellAuth(role: 'owner' | 'viewer' | 'billing_only' = 'owner') {
  establishTenant(createMockSession(), createMockTenant());
  setBootstrapReady();
  setCurrentUserRole(role);
  resetDefaultClaimsLedgerClient();
  setDefaultClaimsLedgerClient(createClaimsLedgerClient());
}

describe('Claims ledger page header', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    resetClaimsListDelayForTests();
    resetSyntheticClaimsDataset();
    seedClaimsShellAuth('owner');
  });

  it('renders mockup title, subtitle, and export CTA without debug query leak', () => {
    render(
      <MemoryRouter>
        <ClaimsLedgerPageHeader filters={parseClaimsFilters('')} />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { level: 1, name: CLAIMS_LEDGER_PAGE_COPY.title })).toBeInTheDocument();
    expect(screen.getByText(CLAIMS_LEDGER_PAGE_COPY.subtitle)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: CLAIMS_LEDGER_PAGE_COPY.exportAction })).toBeInTheDocument();
    expect(document.querySelector('[data-claims-ledger-header-row]')).toBeTruthy();
    expect(document.querySelector('[data-claims-ledger-header-actions]')).toBeTruthy();
    expect(screen.queryByText(/^Query:/i)).not.toBeInTheDocument();
  });

  it('keeps query metadata on the page surface only after ledger load', async () => {
    const router = createClaimsShellRouter(['/app/claims?claimSource=meta_ads']);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();

    const page = document.querySelector('[data-claims-ledger-page]') as HTMLElement | null;
    expect(page).toBeTruthy();
    expect(page?.getAttribute('data-query-id')).toBeTruthy();
    expect(screen.queryByText(/^Query:/i)).not.toBeInTheDocument();
    const header = document.querySelector('[data-claims-ledger-header]');
    expect(header).toBeTruthy();
    expect(within(header as HTMLElement).queryByText(/Revenue Claims Ledger/i)).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1, name: CLAIMS_LEDGER_PAGE_COPY.title })).toBeInTheDocument();
    });
    expect(document.querySelector('[data-shell-route-container] h2')).toBeNull();
    const headerRow = document.querySelector('[data-claims-ledger-header-row]') as HTMLElement | null;
    expect(headerRow).toBeTruthy();
    expect(page?.firstElementChild).toBe(headerRow);
  });

  it('shares command center compact main padding-top shell rule', () => {
    const shellCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'shell', 'AuthenticatedAppShell', 'AuthenticatedAppShell.module.css'),
      'utf8',
    );
    expect(shellCss).toMatch(
      /main:has\(\[data-claims-ledger-page\]\)[\s\S]*padding-top:\s*var\(--sk-space-2\)/,
    );
    expect(shellCss).toMatch(
      /main:has\(\[data-command-center-page\]\)[\s\S]*padding-top:\s*var\(--sk-space-2\)/,
    );
  });
});
