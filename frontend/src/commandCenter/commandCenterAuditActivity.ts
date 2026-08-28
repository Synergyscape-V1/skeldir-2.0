import { getDefaultOperationalAuditClient } from '../operationalAudit/operationalAuditClient';
import type { AuditEvent } from '../operationalAudit/types';
import {
  AUDIT_ACTIVITY_STRIP_SIZE,
  isAllowedAuditStripEvent,
  sortAuditActivityNewestFirst,
} from './auditActivityPolicy';
import { COMMAND_CENTER_AUDIT_ACTIVITY } from './commandCenterAuditFixtures';
import type { AuditActivityRow } from './types';

function mapAuditEventToRow(event: AuditEvent): AuditActivityRow | null {
  if (!isAllowedAuditStripEvent(event.eventType, event.tier)) {
    return null;
  }

  const actorKind = event.agentLabel ? ('agent' as const) : ('user' as const);
  const actorDisplay = event.agentLabel ?? event.actorLabel;
  const actorClientId = event.actorClientId ?? event.agentLabel ?? event.actorLabel;

  return {
    eventId: event.eventId,
    eventType: event.eventType as AuditActivityRow['eventType'],
    occurredAt: event.occurredAt,
    tier: 'tier_b',
    actorKind,
    actorDisplay,
    actorClientId,
    targetRef: event.envelopeRef ?? event.subjectLabel,
    envelopeId: event.envelopeRef,
  };
}

export function mapAuditEventsToStripRows(events: AuditEvent[]): AuditActivityRow[] {
  return sortAuditActivityNewestFirst(
    events.map(mapAuditEventToRow).filter((row): row is AuditActivityRow => row !== null),
  ).slice(0, AUDIT_ACTIVITY_STRIP_SIZE);
}

export async function fetchAuditActivityStrip(
  tenantId: string,
  signal?: AbortSignal,
): Promise<AuditActivityRow[]> {
  const outcome = await getDefaultOperationalAuditClient().listAuditEvents(
    tenantId,
    { tier: 'tier_b', pageSize: 50, offset: 0 },
    signal,
  );

  if (outcome.kind === 'audit_loaded') {
    const rows = mapAuditEventsToStripRows(outcome.events);
    if (rows.length > 0) {
      return rows;
    }
  }

  return COMMAND_CENTER_AUDIT_ACTIVITY.slice(0, AUDIT_ACTIVITY_STRIP_SIZE);
}
