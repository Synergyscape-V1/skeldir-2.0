import type { AuditFilters, AuditLogMode } from './types';
import {
  getDefaultForensicDateRange,
  getDefaultForensicTriageFilters,
  serializeForensicActionCategories,
} from './forensicBusinessTriage';
import { resolveAuditLogMode } from './auditLogMode';

function forensicDefaultsEqual(a: AuditFilters, b: AuditFilters): boolean {
  const left = getDefaultForensicDateRange();
  return (
    a.dateFrom === (b.dateFrom ?? left.dateFrom) &&
    a.dateTo === (b.dateTo ?? left.dateTo) &&
    serializeForensicActionCategories(a.actionCategories) ===
      serializeForensicActionCategories(b.actionCategories) &&
    !a.actor &&
    !a.claimId &&
    !a.envelopeId &&
    !a.eventId &&
    !a.eventType
  );
}

export function normalizeAuditFilterCriteria(filters: AuditFilters): AuditFilters {
  const logMode = resolveAuditLogMode(filters);
  const normalized: AuditFilters = { logMode };

  if (logMode === 'access_history') {
    if (filters.systemHealth) {
      normalized.systemHealth = true;
    }
    if (filters.actor) normalized.actor = filters.actor;
    if (filters.agent) normalized.agent = filters.agent;
    if (filters.envelopeId) normalized.envelopeId = filters.envelopeId;
    if (filters.endpoint) normalized.endpoint = filters.endpoint;
    if (filters.httpStatusCode && filters.httpStatusCode !== 'all') {
      normalized.httpStatusCode = filters.httpStatusCode;
    }
  } else {
    if (filters.actionCategories && filters.actionCategories.length > 0) {
      normalized.actionCategories = [...filters.actionCategories].sort();
    }
    if (filters.actor) normalized.actor = filters.actor;
    if (filters.envelopeId) normalized.envelopeId = filters.envelopeId;
    if (filters.claimId) normalized.claimId = filters.claimId;
    if (filters.eventId) normalized.eventId = filters.eventId;
    if (filters.eventType && filters.eventType !== 'all') normalized.eventType = filters.eventType;
  }

  if (filters.dateFrom) normalized.dateFrom = filters.dateFrom;
  if (filters.dateTo) normalized.dateTo = filters.dateTo;

  return normalized;
}

export function hasActiveAuditFilters(filters: AuditFilters): boolean {
  const logMode = resolveAuditLogMode(filters);
  if (logMode === 'forensic_log') {
    const normalized = normalizeAuditFilterCriteria(filters);
    const defaults = getDefaultForensicTriageFilters();
    if (forensicDefaultsEqual(normalized, defaults)) return false;
    return Object.keys(normalized).length > 1;
  }
  return Object.keys(normalizeAuditFilterCriteria(filters)).length > 1;
}

export function auditFilterCriteriaEqual(a: AuditFilters, b: AuditFilters): boolean {
  const left = normalizeAuditFilterCriteria(a);
  const right = normalizeAuditFilterCriteria(b);
  const keys = new Set([...Object.keys(left), ...Object.keys(right)]);

  for (const key of keys) {
    const leftValue = left[key as keyof AuditFilters];
    const rightValue = right[key as keyof AuditFilters];
    if (Array.isArray(leftValue) && Array.isArray(rightValue)) {
      if (leftValue.join(',') !== rightValue.join(',')) return false;
      continue;
    }
    if (leftValue !== rightValue) {
      return false;
    }
  }

  return true;
}

export const EMPTY_AUDIT_FILTERS: AuditFilters = {};

export { getDefaultForensicTriageFilters };

export function filtersForLogModeChange(
  current: AuditFilters,
  nextMode: AuditLogMode,
): AuditFilters {
  if (nextMode === 'forensic_log') {
    return getDefaultForensicTriageFilters();
  }
  return normalizeAuditFilterCriteria({ ...current, logMode: nextMode });
}
