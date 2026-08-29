import type { AuditEvent, AuditEventType, AuditFilters, ForensicActionCategory } from './types';

import { resolveAuditLogMode } from './auditLogMode';

export const FORENSIC_ACTION_CATEGORIES: ForensicActionCategory[] = [
  'approved',
  'exported',
  'resolved',
  'system_action',
];

export const FORENSIC_ACTION_CATEGORY_LABELS: Record<ForensicActionCategory, string> = {
  approved: 'Approved',
  exported: 'Exported',
  resolved: 'Resolved',
  system_action: 'System Action',
};

const CATEGORY_EVENT_TYPES: Record<ForensicActionCategory, AuditEventType[]> = {
  approved: ['policy_decision_rendered', 'proposal_reviewed'],
  exported: ['artifact_exported', 'proposal_exported'],
  resolved: ['exception_case_updated'],
  system_action: ['bayesian_fit_completed', 'dispatch_executed', 'dispatch_suppressed'],
};

export function forensicEventCategory(eventType: AuditEventType): ForensicActionCategory | undefined {
  for (const category of FORENSIC_ACTION_CATEGORIES) {
    if ((CATEGORY_EVENT_TYPES[category] as readonly AuditEventType[]).includes(eventType)) {
      return category;
    }
  }
  return undefined;
}

export function eventMatchesForensicCategories(
  eventType: AuditEventType,
  categories: ForensicActionCategory[] | undefined,
): boolean {
  if (!categories || categories.length === 0) return true;
  const eventCategory = forensicEventCategory(eventType);
  if (!eventCategory) return false;
  return categories.includes(eventCategory);
}

export function parseForensicActionCategories(value: string | null): ForensicActionCategory[] | undefined {
  if (!value) return undefined;
  const parsed = value
    .split(',')
    .map((entry) => entry.trim())
    .filter((entry): entry is ForensicActionCategory =>
      FORENSIC_ACTION_CATEGORIES.includes(entry as ForensicActionCategory),
    );
  return parsed.length > 0 ? parsed : undefined;
}

export function serializeForensicActionCategories(
  categories: ForensicActionCategory[] | undefined,
): string | undefined {
  if (!categories || categories.length === 0) return undefined;
  return categories.join(',');
}

export function getDefaultForensicDateRange(now = new Date()): { dateFrom: string; dateTo: string } {
  const end = new Date(now);
  end.setUTCHours(23, 59, 59, 999);
  const start = new Date(now);
  start.setUTCDate(start.getUTCDate() - 6);
  start.setUTCHours(0, 0, 0, 0);
  return {
    dateFrom: start.toISOString(),
    dateTo: end.toISOString(),
  };
}

export function getDefaultForensicTriageFilters(now = new Date()): AuditFilters {
  const { dateFrom, dateTo } = getDefaultForensicDateRange(now);
  return {
    logMode: 'forensic_log',
    dateFrom,
    dateTo,
  };
}

export function resolveForensicAuditFilters(filters: AuditFilters): AuditFilters {
  if (resolveAuditLogMode(filters) !== 'forensic_log') return filters;
  // An explicit event reference is globally identifying within the tenant.
  // Applying the seven-day triage window would make valid historical deep links disappear.
  if (filters.eventId) return filters;
  const { dateFrom, dateTo } = getDefaultForensicDateRange();
  return {
    ...filters,
    dateFrom: filters.dateFrom ?? dateFrom,
    dateTo: filters.dateTo ?? dateTo,
  };
}

export function actorSearchHaystack(event: AuditEvent): string {
  return [event.actorLabel, event.agentLabel].filter(Boolean).join(' ').toLowerCase();
}

export function matchesPartialRef(value: string | undefined, query: string | undefined): boolean {
  if (!query) return true;
  if (!value) return false;
  return value.toLowerCase().includes(query.toLowerCase());
}

export const FORENSIC_ACTOR_SUGGESTIONS = [
  'admin@acme.example',
  'finance@acme.example',
  'ops@acme.example',
  'viewer@acme.example',
  'Skeldir-MCP',
  'Budget Optimizer',
] as const;

export function collectForensicActorSuggestions(events: AuditEvent[]): string[] {
  const labels = new Set<string>();
  for (const event of events) {
    if (event.tier !== 'tier_b') continue;
    if (event.actorLabel) labels.add(event.actorLabel);
    if (event.agentLabel) labels.add(event.agentLabel);
  }
  return [...labels].sort((a, b) => a.localeCompare(b));
}
