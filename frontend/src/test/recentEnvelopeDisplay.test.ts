import { describe, expect, it } from 'vitest';
import { COMMAND_CENTER_RECENT_ENVELOPES } from '../commandCenter/commandCenterEnvelopeFixtures';
import {
  buildRecentEnvelopeFeed,
  mapTrustIndexRowToRecentEnvelope,
  resolveRecentEnvelopeDrillDown,
  sortRecentEnvelopesChronological,
} from '../commandCenter/recentEnvelopeDisplay';
import { MAX_RECENT_ENVELOPES } from '../commandCenter/recentEnvelopesConstants';
import type { RecentEnvelopeRow } from '../commandCenter/types';
import type { TrustEnvelopeIndexRowDTO } from '../ledger/types';

describe('recentEnvelopeDisplay', () => {
  it('maps subject reference from subjectRef — never label/detail substitutes', () => {
    const mapped = mapTrustIndexRowToRecentEnvelope({
      envelopeId: 'env_0101',
      subjectRef: 'ord_8f9a2c1d4e7b3a61',
      subjectLabel: 'Stripe North-East',
      subjectDetail: 'Meta Ads Campaign',
      matchVerdict: 'matched_confirmed',
      verifiedRevenueMinor: 1n,
      currencyCode: 'USD',
      discrepancyRateBps: 0,
      policyAuthority: 'blocked',
      claimTime: new Date().toISOString(),
      generationTimestamp: new Date().toISOString(),
      auditReference: 'audit_x',
    } as TrustEnvelopeIndexRowDTO);
    expect(mapped.subjectRef).toBe('ord_8f9a2c1d4e7b3a61');
    expect(mapped.subjectRef).not.toContain('...');
  });
  it('fixture envelope IDs satisfy trust detail route contract', () => {
    for (const row of COMMAND_CENTER_RECENT_ENVELOPES) {
      expect(row.envelopeId).toMatch(/^env_\d{4}$/);
    }
  });

  it('sorts chronologically newest first without severity reordering', () => {
    const shuffled = [...COMMAND_CENTER_RECENT_ENVELOPES].reverse();
    const sorted = sortRecentEnvelopesChronological(shuffled);
    for (let i = 1; i < sorted.length; i += 1) {
      expect(Date.parse(sorted[i - 1]!.createdAt)).toBeGreaterThanOrEqual(Date.parse(sorted[i]!.createdAt));
    }
    expect(sorted[0]?.envelopeId).not.toBe(
      [...shuffled].sort((a, b) => (b.discrepancyRateBps ?? 0) - (a.discrepancyRateBps ?? 0))[0]?.envelopeId,
    );
  });

  it('caps feed at backend max without hard-coded frontend slice of five', () => {
    expect(MAX_RECENT_ENVELOPES).toBe(25);
    const many: RecentEnvelopeRow[] = Array.from({ length: 30 }, (_, index) => ({
      ...COMMAND_CENTER_RECENT_ENVELOPES[0]!,
      envelopeId: `env_bulk_${index}`,
      createdAt: new Date(Date.now() - index * 60_000).toISOString(),
    }));
    const feed = buildRecentEnvelopeFeed(many, { window: '24h' });
    expect(feed).toHaveLength(25);
  });

  it('snapshot table shows five rows per page in the card', async () => {
    const { RECENT_ENVELOPES_SNAPSHOT_ROW_COUNT } = await import('../commandCenter/recentEnvelopesConstants');
    expect(RECENT_ENVELOPES_SNAPSHOT_ROW_COUNT).toBe(5);
  });

  it('deep-links money mismatch rows to evidence focus', () => {
    const row = COMMAND_CENTER_RECENT_ENVELOPES.find((entry) => entry.matchVerdict === 'unmatched');
    expect(row).toBeTruthy();
    const drillDown = resolveRecentEnvelopeDrillDown(row!);
    expect(drillDown.href).toContain('trustFocus=evidence');
    expect(drillDown.focus).toBe('evidence');
  });

  it('deep-links approval-required policy to policy focus', () => {
    const row: RecentEnvelopeRow = {
      ...COMMAND_CENTER_RECENT_ENVELOPES[0]!,
      matchVerdict: 'matched_confirmed',
      discrepancyRateBps: 40,
      policyAuthority: 'approval_required',
      trustSignal: null,
    };
    const drillDown = resolveRecentEnvelopeDrillDown(row);
    expect(drillDown.href).toContain('trustFocus=policy');
    expect(drillDown.focus).toBe('policy');
  });

  it('deep-links estimator transition to confidence focus', () => {
    const row: RecentEnvelopeRow = {
      ...COMMAND_CENTER_RECENT_ENVELOPES[0]!,
      matchVerdict: 'matched_confirmed',
      discrepancyRateBps: 40,
      policyAuthority: 'blocked',
      trustSignal: 'estimator_transition',
    };
    const drillDown = resolveRecentEnvelopeDrillDown(row);
    expect(drillDown.href).toContain('trustFocus=confidence');
    expect(drillDown.focus).toBe('confidence');
  });
});
