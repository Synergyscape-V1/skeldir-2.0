import { describe, expect, it } from 'vitest';
import {
  assessForensicChainIntegrity,
  findAdjacentForensicEvents,
} from '../operationalAudit/forensicChainIntegrity';
import type { AuditEvent } from '../operationalAudit/types';

const forensicEvents: AuditEvent[] = [
  {
    eventId: 'evt_new',
    occurredAt: '2026-06-02T00:00:00.000Z',
    eventType: 'artifact_exported',
    actorLabel: 'admin@acme.example',
    subjectLabel: 'env_1',
    tier: 'tier_b',
    signatureStatus: 'valid',
    artifactAvailability: 'available',
    artifactHash: 'hash_new',
    previousArtifactHash: 'hash_prev',
  },
  {
    eventId: 'evt_prev',
    occurredAt: '2026-06-01T00:00:00.000Z',
    eventType: 'policy_decision_rendered',
    actorLabel: 'finance@acme.example',
    subjectLabel: 'env_2',
    tier: 'tier_b',
    signatureStatus: 'valid',
    artifactAvailability: 'available',
    artifactHash: 'hash_prev',
  },
];

describe('forensic chain integrity', () => {
  it('finds chronologically adjacent forensic events', () => {
    const adjacent = findAdjacentForensicEvents(forensicEvents, 'evt_new');
    expect(adjacent.previous?.eventId).toBe('evt_prev');
  });

  it('marks intact chain when previous link matches prior artifact hash', () => {
    const assessment = assessForensicChainIntegrity(
      {
        eventId: 'evt_new',
        eventType: 'artifact_exported',
        actorLabel: 'admin@acme.example',
        subjectLabel: 'env_1',
        occurredAt: '2026-06-02T00:00:00.000Z',
        tier: 'tier_b',
        signatureStatus: 'valid',
        availability: 'available',
        previousArtifactHash: 'hash_prev',
        artifactHash: 'hash_new',
      },
      forensicEvents[1],
    );
    expect(assessment.verdict).toBe('intact');
  });

  it('marks broken chain when previous link mismatches prior artifact hash', () => {
    const assessment = assessForensicChainIntegrity(
      {
        eventId: 'evt_new',
        eventType: 'artifact_exported',
        actorLabel: 'admin@acme.example',
        subjectLabel: 'env_1',
        occurredAt: '2026-06-02T00:00:00.000Z',
        tier: 'tier_b',
        signatureStatus: 'valid',
        availability: 'available',
        previousArtifactHash: 'hash_tampered',
        artifactHash: 'hash_new',
      },
      forensicEvents[1],
    );
    expect(assessment.verdict).toBe('broken');
  });
});
