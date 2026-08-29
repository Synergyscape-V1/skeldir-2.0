import type { AuditArtifact, AuditEvent } from './types';

export type ForensicChainVerdict = 'intact' | 'broken' | 'unavailable';

export interface ForensicChainAssessment {
  verdict: ForensicChainVerdict;
  previousEventId?: string;
  nextEventId?: string;
  previousArtifactHash?: string;
  currentPreviousLinkHash?: string;
  detail?: string;
}

function sortForensicEventsNewestFirst(events: AuditEvent[]): AuditEvent[] {
  return [...events].sort((a, b) => {
    const timeCmp = b.occurredAt.localeCompare(a.occurredAt);
    if (timeCmp !== 0) return timeCmp;
    return b.eventId.localeCompare(a.eventId);
  });
}

export function findAdjacentForensicEvents(
  events: AuditEvent[],
  eventId: string,
): { current?: AuditEvent; previous?: AuditEvent; next?: AuditEvent } {
  const forensic = sortForensicEventsNewestFirst(events.filter((event) => event.tier === 'tier_b'));
  const index = forensic.findIndex((event) => event.eventId === eventId);
  if (index < 0) return {};
  return {
    current: forensic[index],
    previous: forensic[index - 1],
    next: forensic[index + 1],
  };
}

export function assessForensicChainIntegrity(
  artifact: AuditArtifact | undefined,
  previousEvent?: AuditEvent,
): ForensicChainAssessment {
  if (!artifact) {
    return { verdict: 'unavailable', detail: 'Artifact metadata unavailable for chain verification.' };
  }

  const previousArtifactHash = previousEvent?.artifactHash;
  const currentPreviousLinkHash = artifact.previousArtifactHash ?? artifact.previousStateHash;

  if (!currentPreviousLinkHash) {
    return {
      verdict: 'unavailable',
      previousEventId: previousEvent?.eventId,
      detail: 'No previous-link hash supplied for this forensic record.',
    };
  }

  if (!previousEvent) {
    return {
      verdict: 'intact',
      currentPreviousLinkHash,
      detail: 'Genesis forensic record — no prior event in the loaded timeline window.',
    };
  }

  if (!previousArtifactHash) {
    return {
      verdict: 'unavailable',
      previousEventId: previousEvent.eventId,
      currentPreviousLinkHash,
      detail: 'Prior event artifact hash unavailable for comparison.',
    };
  }

  const intact = currentPreviousLinkHash === previousArtifactHash;
  return {
    verdict: intact ? 'intact' : 'broken',
    previousEventId: previousEvent.eventId,
    previousArtifactHash,
    currentPreviousLinkHash,
    detail: intact
      ? 'previous_artifact_hash matches the prior row artifact_hash in chronological order.'
      : 'previous_artifact_hash does not match the prior row artifact_hash — tamper or gap detected.',
  };
}
