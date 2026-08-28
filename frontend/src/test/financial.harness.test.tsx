import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import { ClaimComparisonCard } from '../components/financial/ClaimComparisonCard/ClaimComparisonCard';
import { FinancialValue } from '../components/financial/FinancialValue/FinancialValue';
import {
  CANONICAL_EVIDENCE_SEQUENCE,
  EvidenceTimeline,
} from '../components/trust/EvidenceTimeline/EvidenceTimeline';
import { DataUnavailablePanel } from '../components/trust/DataUnavailablePanel/DataUnavailablePanel';
import { AuditReferenceLink } from '../components/audit/AuditReferenceLink/AuditReferenceLink';
import { MemoryRouter } from 'react-router-dom';
import { parseMoneyMinor, subtractMoneyMinor, formatMoneyMinorDisplay } from '../lib/money';
import { assertTokenCssAlignment } from '../tokens';

const MAX_SAFE_CLAIMED = '900719925474099300';
const MAX_SAFE_VERIFIED = '900719925474099100';
const MAX_SAFE_DIFF = '200';

describe('Level 0 — Financial Determinism', () => {
  it('positive: valid bigint renders with authority', () => {
    render(<FinancialValue amountMinor={128420n} currencyCode="USD" authority="deterministic" label="Verified revenue" />);
    expect(screen.getByRole('group', { name: 'Verified revenue' })).toBeInTheDocument();
    expect(screen.getByRole('status', { name: /Source authority: deterministic/i })).toBeInTheDocument();
  });

  it('display format uses dollar prefix without ISO code or cents', () => {
    expect(formatMoneyMinorDisplay(12_842_000n, 'USD')).toBe('$128,420');
    expect(formatMoneyMinorDisplay(10_000n, 'USD')).toBe('$100');
    expect(formatMoneyMinorDisplay(1_000_000n, 'USD')).toBe('$10,000');
    expect(formatMoneyMinorDisplay(12_842_000n, 'USD')).not.toContain('USD');
  });

  it('negative: Number input rejected', () => {
    render(<FinancialValue amountMinor={1284.2 as unknown as bigint} currencyCode="USD" authority="deterministic" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Number input is forbidden');
  });

  it('negative: decimal string rejected', () => {
    render(<FinancialValue amountMinor="12.34" currencyCode="USD" authority="deterministic" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Formatted or decimal');
  });

  it('negative: unknown authority rejected', () => {
    render(<FinancialValue amountMinor="100" currencyCode="USD" authority="causal" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Invalid authority state');
  });

  it('positive: large integer comparison exact diff', () => {
    const claimed = parseMoneyMinor(MAX_SAFE_CLAIMED);
    const verified = parseMoneyMinor(MAX_SAFE_VERIFIED);
    expect(claimed.ok && verified.ok).toBe(true);
    if (claimed.ok && verified.ok) {
      expect(subtractMoneyMinor(claimed.value, verified.value).toString()).toBe(MAX_SAFE_DIFF);
    }

    render(
      <ClaimComparisonCard
        claimedRevenueMinor={MAX_SAFE_CLAIMED}
        verifiedRevenueMinor={MAX_SAFE_VERIFIED}
        currencyCode="USD"
        backendDifferenceMinor={MAX_SAFE_DIFF}
      />,
    );

    expect(screen.getByText(MAX_SAFE_DIFF)).toBeInTheDocument();
  });

  it('negative: backend difference mismatch renders error', () => {
    render(
      <ClaimComparisonCard
        claimedRevenueMinor="1000"
        verifiedRevenueMinor="800"
        currencyCode="USD"
        backendDifferenceMinor="100"
      />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Backend difference mismatch');
  });
});

describe('Level 0 — AuditReferenceLink operator traceability', () => {
  it('renders opaque audit reference linking to audit ledger', () => {
    render(
      <MemoryRouter>
        <AuditReferenceLink auditReference="aud_9f2a" claimId="claim_0001" />
      </MemoryRouter>,
    );
    const link = screen.getByRole('link', { name: /Open audit ledger for aud_9f2a/i });
    expect(link).toHaveAttribute('href', '/app/audit?log=access&eventId=aud_9f2a&claimId=claim_0001');
  });
});

describe('Level 0 — EvidenceTimeline reconstruction', () => {
  it('rejects shuffled timeline at render', () => {
    render(<EvidenceTimeline items={[...CANONICAL_EVIDENCE_SEQUENCE].reverse()} />);
    expect(screen.getByRole('alert')).toHaveTextContent('not reconstructable');
  });
});

describe('Level 0 — blocked_simulation variant', () => {
  it('renders blocked simulation copy', () => {
    render(<DataUnavailablePanel variant="blocked_simulation" reason="LP_INPUT_MATRIX_UNDERDETERMINED" />);
    expect(screen.getByText(/Simulation unavailable/i)).toBeInTheDocument();
  });
});

describe('Level 0 — Token CSS alignment', () => {
  it('TS registry aligns with tokens.css', () => {
    const css = readFileSync(resolve(process.cwd(), 'src/tokens/tokens.css'), 'utf8');
    expect(() => assertTokenCssAlignment(css)).not.toThrow();
  });
});
