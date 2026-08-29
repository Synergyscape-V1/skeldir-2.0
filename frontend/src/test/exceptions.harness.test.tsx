import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { ExceptionsQueuePage } from '../components/exceptions/ExceptionsQueuePage/ExceptionsQueuePage';
import { resetDefaultExceptionsClient } from '../exceptions/exceptionsClient';
import { exceptionsDefaultFilters, exceptionsFiltersToSearchParams } from '../exceptions/exceptionsQueryState';
import { seedShellAuth } from './level9.helpers';

function renderExceptions(initialPath?: string) {
  const defaults = exceptionsFiltersToSearchParams(exceptionsDefaultFilters());
  const path = initialPath ?? `/app/exceptions?${defaults.toString()}`;
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/app/exceptions" element={<ExceptionsQueuePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Exceptions interface remediation harness', () => {
  beforeEach(() => {
    seedShellAuth('owner');
    resetDefaultExceptionsClient();
  });

  it('renders page header, summary tiles, category tabs, filters, and nine-column table', async () => {
    renderExceptions();
    await waitFor(() => expect(document.querySelector('[data-exceptions-page]')).toBeInTheDocument());

    expect(screen.getByRole('heading', { level: 1, name: /^Exceptions$/i })).toBeInTheDocument();
    expect(
      screen.getByText('Human-meaningful trust exceptions routed for review.'),
    ).toBeInTheDocument();

    expect(document.querySelector('[data-exceptions-summary-row]')).toBeTruthy();
    expect(document.querySelector('[data-exceptions-header-row]')).toBeTruthy();
    expect(document.querySelector('[data-page-interface-header]')).toBeTruthy();
    expect(document.querySelector('[data-exceptions-table] [class*="tableWrapDense"]')).toBeTruthy();

    const page = document.querySelector('[data-exceptions-page]') as HTMLElement | null;
    expect(page).toBeTruthy();
    expect(page?.firstElementChild).toBe(document.querySelector('[data-exceptions-header-row]'));
    expect(page?.children[1]).toBe(document.querySelector('[data-exceptions-summary-row]'));
    expect(screen.getByText('Open exceptions')).toBeInTheDocument();
    expect(screen.getByText('Pending certifications')).toBeInTheDocument();
    expect(screen.getByText('Signature failures')).toBeInTheDocument();
    expect(screen.getByText('Integration repairs needed')).toBeInTheDocument();

    expect(document.querySelector('[data-exceptions-category-tabs]')).toBeTruthy();
    expect(document.querySelector('[data-exception-category-tab="all"]')).toBeTruthy();
    expect(document.querySelector('[data-exception-category-tab="discrepancy_review"]')).toBeTruthy();

    expect(document.querySelector('[data-exceptions-filters]')).toBeTruthy();
    expect(screen.getByLabelText(/Date range/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Category$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Severity$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Status$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Policy authority/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Source object/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Search exception summary/i)).toBeInTheDocument();

    expect(screen.getByRole('columnheader', { name: /Severity/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Category/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Exception summary/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Affected object/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Policy authority/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Last audit event/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Created \/ age/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /^Status$/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /^Action$/i })).toBeInTheDocument();
  });

  it('renders canonical first-page rows with text-only status labels and primary review actions', async () => {
    renderExceptions();
    const table = await waitFor(() => {
      const node = document.querySelector('[data-exceptions-table]') as HTMLElement | null;
      expect(node).toBeTruthy();
      return node!;
    });

    expect(
      within(table).getByText('Spend reallocation exceeds tenant approval threshold.'),
    ).toBeInTheDocument();
    expect(within(table).getByText('Evidence bundle signature mismatch on attribution export.')).toBeInTheDocument();
    expect(within(table).getByText('Meta Ads token expired for channel sync.')).toBeInTheDocument();
    expect(table.querySelector('[data-exception-severity="critical"]')).toBeTruthy();
    expect(table.querySelector('[data-exception-severity="warning"]')).toBeTruthy();
    const criticalSeverity = table.querySelector('[data-exception-severity="critical"]');
    expect(criticalSeverity).toHaveAttribute('data-status-text', 'true');
    expect(criticalSeverity?.className).toMatch(/_labelError_/);
    expect(criticalSeverity?.className).not.toMatch(/_chip_/);
    expect(table.querySelectorAll('[data-status-text]').length).toBeGreaterThanOrEqual(6);
    expect(within(table).getAllByRole('button', { name: /^Review /i }).length).toBeGreaterThan(0);
    expect(within(table).getByRole('button', { name: /^Open Meta Ads token expired/i })).toBeInTheDocument();
    expect(screen.queryByText(/^exc_0001$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/match_discrepancy/i)).not.toBeInTheDocument();
  });

  it('shares filter chip DNA with benchmarks active filter chips', () => {
    const exceptionsFiltersCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'exceptions', 'ExceptionsFilters', 'ExceptionsFilters.module.css'),
      'utf8',
    );
    const benchmarksFiltersCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'benchmarks', 'BenchmarksFilters', 'BenchmarksFilters.module.css'),
      'utf8',
    );
    const categoryTabsCss = readFileSync(
      join(
        process.cwd(),
        'src',
        'components',
        'exceptions',
        'ExceptionsCategoryTabs',
        'ExceptionsCategoryTabs.module.css',
      ),
      'utf8',
    );

    expect(exceptionsFiltersCss).toMatch(/\.chip\s*\{[\s\S]*composes:\s*chip from/);
    expect(benchmarksFiltersCss).toMatch(/\.chip\s*\{[\s\S]*composes:\s*chip from/);
    expect(categoryTabsCss).toMatch(/composes:\s*chips from/);
  });

  it('shares supervisory table DNA with trust envelope index', () => {
    const exceptionsTableCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'exceptions', 'ExceptionsTable', 'ExceptionsTable.module.css'),
      'utf8',
    );
    const trustTableCss = readFileSync(
      join(
        process.cwd(),
        'src',
        'components',
        'trustIndex',
        'TrustEnvelopeIndexTable',
        'TrustEnvelopeIndexTable.module.css',
      ),
      'utf8',
    );

    expect(exceptionsTableCss).toMatch(/\.tableCard\s*\{[\s\S]*tableCard from/);
    expect(exceptionsTableCss).toMatch(/\.tableWrapDense\s*\{[\s\S]*tableWrapDense from/);
    expect(exceptionsTableCss).toMatch(/\.overflowMenu\s*\{[\s\S]*overflowMenu from/);
    expect(exceptionsTableCss).toMatch(/@media \(max-width: 767px\)/);
    expect(trustTableCss).toMatch(/\.tableWrapDense\s*\{[\s\S]*tableWrapDense from/);
  });

  it('shows pagination footer and category tab filtering', async () => {
    const user = userEvent.setup();
    renderExceptions();
    await waitFor(() => expect(screen.getByText(/Showing 1 to 6 of \d+ exceptions/i)).toBeInTheDocument());

    expect(screen.getByRole('button', { name: /Next page/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Previous page/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Page 1/i })).not.toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: /Signature verification failure/i }));
    await waitFor(() => expect(screen.getByText(/Showing 1 to \d+ of \d+ exceptions/i)).toBeInTheDocument());
  });

  it('shares tile-page vertical rhythm with channels and trust index', () => {
    const exceptionsPageCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'exceptions', 'ExceptionsQueuePage', 'ExceptionsQueuePage.module.css'),
      'utf8',
    );
    const channelsPageCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'channels', 'ChannelsOverviewPage', 'ChannelsOverviewPage.module.css'),
      'utf8',
    );
    const trustPageCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'trustIndex', 'TrustEnvelopeIndexPage', 'TrustEnvelopeIndexPage.module.css'),
      'utf8',
    );

    expect(exceptionsPageCss).toMatch(/\.page\s*\{[\s\S]*gap:\s*var\(--spacing-24\)/);
    expect(channelsPageCss).toMatch(/\.page\s*\{[\s\S]*gap:\s*var\(--spacing-24\)/);
    expect(trustPageCss).toMatch(/\.page\s*\{[\s\S]*gap:\s*var\(--spacing-24\)/);
    expect(exceptionsPageCss).toMatch(/\.headerRow\s*\{[\s\S]*pageHeaderRow/);
    expect(exceptionsPageCss).toMatch(/\.pageHeaderStack\s*\{[\s\S]*pageHeaderStack/);
  });

  it('opens exception detail modal from review action', async () => {
    const user = userEvent.setup();
    renderExceptions();
    const table = await waitFor(() => {
      const node = document.querySelector('[data-exceptions-table]') as HTMLElement | null;
      expect(node).toBeTruthy();
      return node!;
    });
    await user.click(
      within(table).getByRole('button', {
        name: /Review Spend reallocation exceeds tenant approval threshold/i,
      }),
    );
    await waitFor(() => expect(document.querySelector('[data-exception-detail-modal]')).toBeInTheDocument());
    expect(document.querySelector('[data-exception-detail-drawer]')).toBeInTheDocument();
    expect(document.querySelector('[data-modal-panel]')).toBeTruthy();
    expect(document.querySelector('[data-drawer-panel]')).toBeNull();
    expect(document.querySelector('[data-exception-detail-issue]')).toBeTruthy();
    const titleRef = document.querySelector('[data-exception-detail-title-ref]');
    expect(titleRef).toBeTruthy();
    expect(titleRef?.textContent).toMatch(/^#\d+/);
  });
});
