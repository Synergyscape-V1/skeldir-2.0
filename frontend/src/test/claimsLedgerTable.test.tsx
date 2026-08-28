import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { formatClaimTimeUtcDate, formatClaimTimeUtcLines } from '../claims/claimsLedgerDisplay';
import { baseClaimRow } from '../claims/claimsClient';
import {
  CLAIMS_LEDGER_COLUMNS,
  ClaimsLedgerTable,
} from '../components/claims/ClaimsLedgerTable/ClaimsLedgerTable';

describe('ClaimsLedgerTable architecture', () => {
  it('formats claim time as UTC date for table columns', () => {
    expect(formatClaimTimeUtcDate('2026-07-02T18:00:00.000Z')).toBe('Jul 2, 2026');
    expect(formatClaimTimeUtcLines('2026-07-02T18:00:00.000Z')).toEqual({
      dateLine: 'Jul 2, 2026,',
      timeLine: '6:00 PM UTC',
    });
  });

  it('exposes target column headers in narrative order', () => {
    expect(CLAIMS_LEDGER_COLUMNS.map((column) => column.header)).toEqual([
      'Claim time',
      'Claim source (platform)',
      'Campaign class',
      'Commerce rail',
      'Claimed revenue',
      'Verified revenue',
      'Difference',
      'Match verdict',
      'Attribution model',
      'Confidence',
      'Policy authority',
      'Audit',
    ]);
  });

  it('rejected verdict stays error-toned even when difference is within tolerance', () => {
    const row = {
      ...baseClaimRow(4),
      discrepancyClass: 'within_tolerance' as const,
      matchVerdict: 'rejected' as const,
    };
    const { container } = render(
      <MemoryRouter>
        <ClaimsLedgerTable rows={[row]} pagination={{ totalCount: 1, offset: 0, pageSize: 10, hasMore: false }} />
      </MemoryRouter>,
    );
    expect(container.querySelector('[data-difference-cell="within_tolerance"]')).toBeTruthy();
    expect(container.querySelector('[data-match-verdict="rejected"][data-match-verdict-tone="rejected"]')).toBeTruthy();
    expect(container.querySelector('[data-match-verdict-tone="within_tolerance"]')).toBeNull();
  });

  it('match verdict uses verdict register so it never echoes the difference band', () => {
    const aligned = {
      ...baseClaimRow(0),
      discrepancyClass: 'within_tolerance' as const,
      matchVerdict: 'within_tolerance' as const,
    };
    const { container } = render(
      <MemoryRouter>
        <ClaimsLedgerTable rows={[aligned]} pagination={{ totalCount: 1, offset: 0, pageSize: 10, hasMore: false }} />
      </MemoryRouter>,
    );
    const differenceBadge = container.querySelector(
      '[data-discrepancy-badge="within_tolerance"][data-status-text]',
    );
    const matchVerdict = container.querySelector(
      '[data-match-verdict="within_tolerance"][data-status-text]',
    );
    expect(differenceBadge?.textContent?.trim()).toBe('Within tolerance');
    expect(matchVerdict?.textContent?.trim()).toBe('Matched');
    expect(matchVerdict?.textContent?.trim()).not.toBe(differenceBadge?.textContent?.trim());
  });

  it('tones match verdict pill color to difference severity', () => {
    const aligned = {
      ...baseClaimRow(1),
      claimTime: '2026-07-02T18:00:00.000Z',
      discrepancyClass: 'within_tolerance' as const,
      matchVerdict: 'within_tolerance' as const,
    };
    const { container: alignedTable } = render(
      <MemoryRouter>
        <ClaimsLedgerTable rows={[aligned]} pagination={{ totalCount: 1, offset: 0, pageSize: 10, hasMore: false }} />
      </MemoryRouter>,
    );
    expect(alignedTable.querySelector('[data-difference-cell="within_tolerance"]')).toBeTruthy();
    expect(alignedTable.querySelector('[data-match-verdict-tone="within_tolerance"]')).toBeTruthy();
  });

  it('renders compact operator-facing cells without backend debug tokens', () => {
    const row = {
      ...baseClaimRow(2),
      claimTime: '2026-07-02T18:00:00.000Z',
      discrepancyClass: 'flagged' as const,
      matchVerdict: 'flagged' as const,
    };
    render(
      <MemoryRouter>
        <ClaimsLedgerTable rows={[row]} pagination={{ totalCount: 1, offset: 0, pageSize: 10, hasMore: false }} />
      </MemoryRouter>,
    );

    expect(screen.getByRole('columnheader', { name: 'Difference' })).toBeInTheDocument();
    expect(screen.queryByText(/Discrepancy \(backend\)/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/minor/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/bps/i)).not.toBeInTheDocument();
    const table = screen.getByRole('table', { name: /Forensic line-item ledger/i });
    expect(within(table).getByText('Jul 2, 2026')).toBeInTheDocument();
    expect(within(table).queryByText(/PM UTC$/)).not.toBeInTheDocument();
    expect(within(table).getByText('TikTok Ads')).toBeInTheDocument();
    const logo = table.querySelector('[data-channel-logo="tiktok_ads"]') as HTMLElement | null;
    const name = table.querySelector('[data-claim-platform-name]') as HTMLElement | null;
    expect(logo).toBeTruthy();
    expect(name).toBeTruthy();
    expect(screen.queryByRole('columnheader', { name: /^Channel$/i })).not.toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Campaign class' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Commerce rail' })).toBeInTheDocument();
    if (logo && name && logo.offsetHeight > 0 && name.offsetHeight > 0) {
      expect(logo.offsetHeight).toBeGreaterThan(name.offsetHeight);
    }
    expect(within(table).getByText('time-decay')).toBeInTheDocument();
    expect(within(table).getByRole('link', { name: /Open claim record for claim_0003/i })).toBeInTheDocument();
    expect(table.querySelector('[data-match-verdict="flagged"]')).toBeTruthy();
    expect(table.querySelector('[data-match-verdict-tone="flagged"]')).toBeTruthy();
    expect(table.querySelector('[data-difference-cell="flagged"]')).toBeTruthy();
    expect(table.querySelector('[data-discrepancy-percent]')?.textContent).toMatch(
      /^\d+\.\d{2}% of claim$/,
    );
    expect(table.querySelector('[data-discrepancy-indicator]')?.getAttribute('aria-label')).toMatch(
      /of claimed revenue/,
    );
    expect(table.querySelector('[data-discrepancy-badge="flagged"]')).toBeTruthy();
  });

  it('does not mount full DataUnavailablePanel inside confidence column', () => {
    const row = {
      ...baseClaimRow(4),
      confidence: {
        status: 'unavailable' as const,
        reason: 'cold_start_insufficient_data',
      },
    };
    render(
      <MemoryRouter>
        <ClaimsLedgerTable rows={[row]} pagination={{ totalCount: 1, offset: 0, pageSize: 10, hasMore: false }} />
      </MemoryRouter>,
    );

    const table = screen.getByRole('table', { name: /Forensic line-item ledger/i });
    expect(within(table).getByText('Cold start')).toBeInTheDocument();
    expect(table.querySelector('[data-claims-confidence-disposition="cold_start"]')).toBeTruthy();
    expect(table.querySelector('[data-claims-confidence-cell][title]')).toBeTruthy();
    expect(table.querySelector('[data-bayesian-status]')).toBeNull();
    expect(document.querySelector('[role="region"][aria-label^="Unavailable data"]')).toBeNull();
  });

  it('audit Open label stays single-line inside the audit column', () => {
    const row = baseClaimRow(2);
    const { container } = render(
      <MemoryRouter>
        <ClaimsLedgerTable rows={[row]} pagination={{ totalCount: 1, offset: 0, pageSize: 10, hasMore: false }} />
      </MemoryRouter>,
    );
    const open = container.querySelector('[data-audit-open-affordance="navigate"]') as HTMLElement | null;
    expect(open).toBeTruthy();
    expect(open?.textContent).toBe('Open');
    const supervisoryCss = readFileSync(
      join(process.cwd(), 'src', 'styles', 'supervisoryTable.module.css'),
      'utf8',
    );
    const tableCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'layout', 'Table', 'Table.module.css'),
      'utf8',
    );
    expect(supervisoryCss).toMatch(/\.openButton \{[\s\S]*?white-space:\s*nowrap/);
    expect(tableCss).toMatch(/\[data-audit-open-affordance='navigate'\][\s\S]*?white-space:\s*nowrap/);
  });
});
