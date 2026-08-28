import { describe, expect, it } from 'vitest';
import {
  FORBIDDEN_AUDIT_STRIP_EVENT_TYPES,
  FORENSIC_AUDIT_EVENT_TYPES,
  isAllowedAuditStripEvent,
  sortAuditActivityNewestFirst,
} from '../commandCenter/auditActivityPolicy';
import {
  buildAuditLedgerDeepLink,
  formatAuditActorTitle,
  formatForensicTimestampUtc,
} from '../commandCenter/auditActivityDisplay';
import { mapAuditEventsToStripRows } from '../commandCenter/commandCenterAuditActivity';
import { COMMAND_CENTER_AUDIT_ACTIVITY } from '../commandCenter/commandCenterAuditFixtures';
import type { AuditEvent } from '../operationalAudit/types';
import { formatForensicActionLabel } from '../operationalAudit/forensicAuditDisplay';

describe('Audit activity strip policy', () => {
  it('allows only tier_b forensic consequence-bearing events', () => {
    for (const eventType of FORENSIC_AUDIT_EVENT_TYPES) {
      expect(isAllowedAuditStripEvent(eventType, 'tier_b')).toBe(true);
    }
    for (const eventType of FORBIDDEN_AUDIT_STRIP_EVENT_TYPES) {
      expect(isAllowedAuditStripEvent(eventType, 'tier_b')).toBe(false);
      expect(isAllowedAuditStripEvent(eventType, 'tier_a')).toBe(false);
    }
    expect(isAllowedAuditStripEvent('artifact_exported', 'tier_a')).toBe(false);
  });

  it('sorts strictly newest first', () => {
    const sorted = sortAuditActivityNewestFirst([
      { occurredAt: '2026-01-01T00:00:00.000Z' },
      { occurredAt: '2026-06-01T00:00:00.000Z' },
      { occurredAt: '2026-03-01T00:00:00.000Z' },
    ]);
    expect(sorted.map((r) => r.occurredAt)).toEqual([
      '2026-06-01T00:00:00.000Z',
      '2026-03-01T00:00:00.000Z',
      '2026-01-01T00:00:00.000Z',
    ]);
  });

  it('filters tier_a read noise from audit events', () => {
    const events: AuditEvent[] = [
      {
        eventId: 'noise',
        occurredAt: '2026-06-01T00:00:00.000Z',
        eventType: 'trust_api_read',
        actorLabel: 'viewer@acme.example',
        subjectLabel: 'env_1',
        tier: 'tier_a',
        signatureStatus: 'unavailable',
        artifactAvailability: 'unavailable',
      },
      {
        eventId: 'vault',
        occurredAt: '2026-06-02T00:00:00.000Z',
        eventType: 'artifact_exported',
        actorLabel: 'admin@acme.example',
        subjectLabel: 'env_te_9f2a',
        tier: 'tier_b',
        signatureStatus: 'valid',
        artifactAvailability: 'available',
        envelopeRef: 'env_te_9f2a',
      },
    ];
    const rows = mapAuditEventsToStripRows(events);
    expect(rows).toHaveLength(1);
    expect(rows[0]?.eventType).toBe('artifact_exported');
  });

  it('formats absolute UTC forensic timestamps', () => {
    expect(formatForensicTimestampUtc('2026-01-15T14:23:05.000Z')).toBe('2026-01-15 14:23:05 UTC');
  });

  it('maps forensic event types to friendly action labels', () => {
    expect(formatForensicActionLabel('artifact_exported')).toBe('Signed report exported');
    expect(formatForensicActionLabel('bayesian_fit_completed')).toBe('Confidence model recalculated');
    expect(formatForensicActionLabel('policy_decision_rendered')).toBe('Policy rule applied');
    expect(formatForensicActionLabel('exception_case_updated')).toBe('Exception case updated');
  });

  it('builds audit ledger deep links to forensic event detail', () => {
    const row = COMMAND_CENTER_AUDIT_ACTIVITY[0]!;
    const href = buildAuditLedgerDeepLink(row);
    expect(href).toBe(`/app/audit/events/${row.eventId}`);
  });

  it('actor title prefers readable display over client id', () => {
    const row = COMMAND_CENTER_AUDIT_ACTIVITY[0]!;
    expect(formatAuditActorTitle(row)).toContain(row.actorDisplay);
    expect(formatAuditActorTitle(row)).toContain(row.actorClientId);
  });
});
