import type { AuditActivityRow } from './types';

/** Absolute UTC timestamp for chain-of-custody (e.g. 2026-01-15 14:23:05 UTC). */
export { formatForensicTimestampUtc } from '../operationalAudit/forensicExecutiveDisplay';

export function formatAuditActorLabel(row: AuditActivityRow): string {
  if (row.actorKind === 'agent') {
    return `Agent: ${row.actorDisplay}`;
  }
  return row.actorDisplay;
}

/** Hover/focus title: readable actor plus forensic client id (never substitute id for email). */
export function formatAuditActorTitle(row: AuditActivityRow): string {
  const label = formatAuditActorLabel(row);
  if (!row.actorClientId || row.actorClientId === row.actorDisplay) return label;
  return `${label} · ${row.actorClientId}`;
}

export function buildAuditLedgerDeepLink(row: AuditActivityRow): string {
  return `/app/audit/events/${row.eventId}`;
}
