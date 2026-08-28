import { render, screen, within } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { runFinancialScan } from '../audit/financialScan';
import { runNegativeScopeScan } from '../audit/negativeScopeScan';
import { runTokenAudit } from '../audit/tokenAudit';
import { AuthorityBadge } from '../components/trust/AuthorityBadge/AuthorityBadge';
import { PolicyAuthorityPill } from '../components/trust/PolicyAuthorityPill/PolicyAuthorityPill';
import { Card } from '../components/layout/Card/Card';
import { Table } from '../components/layout/Table/Table';
import { Level0SpecimenGallery } from '../dev/Level0SpecimenGallery';
import { ERROR_COPY } from '../lib/copy';
import { AUTHORITY_CLASSES, POLICY_AUTHORITY_STATES } from '../lib/types';
import { assertTokenRegistryComplete, COLOR_TOKENS, SPACING_TOKENS, assertTokenCssAlignment } from '../tokens';

expect.extend(toHaveNoViolations);

const TOKENS_CSS = readFileSync(resolve(process.cwd(), 'src/tokens/tokens.css'), 'utf8');

describe('Level 0 Harness — Audits (TS modules)', () => {
  it('token audit passes', () => {
    expect(runTokenAudit().violations).toEqual([]);
  });

  it('negative scope scan passes', () => {
    expect(runNegativeScopeScan().violations).toEqual([]);
  });

  it('financial scan passes', () => {
    expect(runFinancialScan().violations).toEqual([]);
  });

  it('token registry complete', () => {
    expect(() => assertTokenRegistryComplete()).not.toThrow();
    expect(COLOR_TOKENS.length).toBe(26);
    expect(SPACING_TOKENS).toEqual([4, 8, 12, 16, 24, 32, 48, 64]);
    expect(() => assertTokenCssAlignment(TOKENS_CSS)).not.toThrow();
  });
});

describe('Level 0 Harness — AuthorityBadge', () => {
  it('renders all authority classes', () => {
    for (const authority of AUTHORITY_CLASSES) {
      const { unmount } = render(<AuthorityBadge authority={authority} size="default" showIcon />);
      if (authority === 'probabilistic') {
        // Probabilistic is canonically TrustChip (role=status) — never the default button chrome.
        expect(screen.getByRole('status', { name: /probabilistic/i })).toHaveAttribute(
          'data-trust-chip',
          'true',
        );
      } else {
        expect(screen.getByRole('button', { name: new RegExp(authority, 'i') })).toBeInTheDocument();
      }
      unmount();
    }
  });

  it('unknown authority fails closed', () => {
    render(<AuthorityBadge authority="causal" />);
    expect(screen.getByRole('alert')).toHaveTextContent(ERROR_COPY.invalidAuthorityState);
  });
});

describe('Level 0 Harness — PolicyAuthorityPill', () => {
  it('auto conflict under design_partner fails closed', () => {
    render(<PolicyAuthorityPill state="auto_executable_within_policy" tenantPolicyMode="design_partner" />);
    expect(screen.getByRole('alert')).toHaveTextContent(ERROR_COPY.invalidPolicyState);
  });

  it('unknown policy state fails closed', () => {
    render(<PolicyAuthorityPill state="execute_anyway" />);
    expect(screen.getByRole('alert')).toHaveTextContent(ERROR_COPY.invalidAuthorityState);
  });

  it('renders all valid policy states', () => {
    for (const state of POLICY_AUTHORITY_STATES) {
      const { unmount } = render(
        state === 'auto_executable_within_policy' ? (
          <PolicyAuthorityPill state={state} tenantPolicyMode="full" />
        ) : (
          <PolicyAuthorityPill state={state} />
        ),
      );
      expect(screen.getByRole('status')).toBeInTheDocument();
      unmount();
    }
  });
});

describe('Level 0 Harness — Loading states', () => {
  it('loading under 2s shows skeleton without progress copy', () => {
    const { container } = render(<Card state="loading_under_2s" title="T" />);
    expect(container.querySelector('[aria-busy="true"]')).toBeInTheDocument();
    expect(screen.queryByText('Still loading verified trust state…')).not.toBeInTheDocument();
  });

  it('loading over 2s shows progress copy', () => {
    render(<Card state="loading_over_2s" title="T" progressCopy="Still loading verified trust state…" />);
    expect(screen.getByText('Still loading verified trust state…')).toBeInTheDocument();
  });

  it('loading over 8s without retry errors', () => {
    render(<Card state="loading_over_8s" title="T" />);
    expect(screen.getByRole('alert')).toHaveTextContent('onRetry');
  });

  it('loading over 8s with retry renders retry button', () => {
    render(<Card state="loading_over_8s" title="T" onRetry={() => undefined} />);
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  });
});

describe('Level 0 Harness — Table states', () => {
  const columns = [{ key: 'name', header: 'Claim', render: (row: { name: string }) => row.name }];

  it('renders populated rows', () => {
    render(
      <Table
        caption="Claims"
        columns={columns}
        rows={[{ name: 'Revenue delta' }]}
        getRowKey={(row) => row.name}
      />,
    );
    expect(screen.getByRole('table', { name: 'Claims' })).toBeInTheDocument();
    expect(screen.getByText('Revenue delta')).toBeInTheDocument();
  });

  it('renders filtered empty state', () => {
    render(
      <Table
        caption="Claims"
        columns={columns}
        state="filtered_empty"
        emptyTitle="No matches"
        onClearFilters={() => undefined}
        getRowKey={(row) => row.name}
      />,
    );
    expect(screen.getByText('No matches')).toBeInTheDocument();
  });

  it('renders permission denied state', () => {
    render(<Table caption="Claims" columns={columns} state="permission_denied" getRowKey={() => 'x'} />);
    expect(screen.getByRole('alert')).toHaveTextContent('permission');
  });
});

describe('Level 0 Harness — Public API exports', () => {
  it('exports financial primitives from index', async () => {
    const api = await import('../index');
    expect(api.FinancialValue).toBeDefined();
    expect(api.ClaimComparisonCard).toBeDefined();
    expect(api.parseMoneyMinor).toBeDefined();
  });
});

describe('Level 0 Harness — Specimen gallery accessibility', () => {
  it('has no axe violations on specimen gallery', async () => {
    const { container } = render(<Level0SpecimenGallery />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
