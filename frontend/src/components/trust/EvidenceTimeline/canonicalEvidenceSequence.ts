import type { EvidenceTimelineItem } from '../../../lib/types';

/** Canonical eight-step sequence for fixture testing */
export const CANONICAL_EVIDENCE_SEQUENCE: EvidenceTimelineItem[] = [
  {
    timestamp: '2026-06-01T10:00:00Z',
    eventType: 'Signed webhook received',
    source: 'Shopify',
    result: 'Received',
    evidenceRef: 'evt_webhook_001',
    status: 'info',
  },
  {
    timestamp: '2026-06-01T10:00:01Z',
    eventType: 'Signature verified',
    source: 'Shopify',
    result: 'Verified',
    evidenceRef: 'sig_001',
    status: 'success',
  },
  {
    timestamp: '2026-06-01T10:00:02Z',
    eventType: 'PII stripped',
    source: 'Privacy boundary',
    result: 'Minimized',
    evidenceRef: 'pii_001',
    status: 'success',
  },
  {
    timestamp: '2026-06-01T10:00:03Z',
    eventType: 'Commerce event persisted',
    source: 'Postgres',
    result: 'Persisted',
    evidenceRef: 'commerce_001',
    status: 'success',
  },
  {
    timestamp: '2026-06-01T10:00:04Z',
    eventType: 'Match task dispatched',
    source: 'B2.3 dispatch',
    result: 'Queued',
    evidenceRef: 'dispatch_001',
    status: 'info',
  },
  {
    timestamp: '2026-06-01T10:00:10Z',
    eventType: 'Match verdict produced',
    source: 'Match kernel',
    result: 'Verified',
    evidenceRef: 'verdict_001',
    status: 'success',
  },
  {
    timestamp: '2026-06-01T10:00:11Z',
    eventType: 'TrustEnvelope created',
    source: 'TrustEnvelopeBuilder',
    result: 'Created',
    evidenceRef: 'envelope_001',
    status: 'success',
  },
  {
    timestamp: '2026-06-01T10:00:12Z',
    eventType: 'Audit reference written',
    source: 'Trust access log',
    result: 'Logged',
    evidenceRef: 'audit_001',
    status: 'success',
  },
];
