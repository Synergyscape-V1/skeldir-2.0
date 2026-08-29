import type { AuditFilters, AuditEventType, AuditLogMode, AuditTier, SignatureStatus } from './types';
import { FORENSIC_AUDIT_EVENT_TYPES } from '../commandCenter/auditActivityPolicy';
import {
  AUDIT_LOG_MODE_ACCESS,
  auditLogModeToParam,
  parseAuditLogMode,
  resolveAuditLogMode,
  tierToAuditLogMode,
} from './auditLogMode';
import {
  parseForensicActionCategories,
  resolveForensicAuditFilters,
  serializeForensicActionCategories,
} from './forensicBusinessTriage';

export type { AuditFilters };
export { resolveAuditLogMode };

const EVENT_TYPES: AuditEventType[] = [
  ...FORENSIC_AUDIT_EVENT_TYPES,
  'trust_access',
  'trust_api_read',
  'simulation_read',
  'system_health',
  'integration_event',
  'task_failure',
  'policy_read',
  'artifact_read',
  'unknown',
];

const TIERS: AuditTier[] = ['tier_a', 'tier_b', 'unknown'];
const SIGNATURES: SignatureStatus[] = ['valid', 'invalid', 'unavailable', 'unknown'];

function parseEnum<T extends string>(value: string | null, allowed: T[]): T | undefined {
  if (!value) return undefined;
  return allowed.includes(value as T) ? (value as T) : undefined;
}

export function parseAuditFilters(search: string): AuditFilters {
  const params = new URLSearchParams(search.startsWith('?') ? search : `?${search}`);
  const filters: AuditFilters = {};

  const logMode = parseAuditLogMode(params.get('log'));
  if (logMode) filters.logMode = logMode;

  if (params.get('filter') === 'system_health') {
    filters.systemHealth = true;
    filters.eventType = 'system_health';
    filters.logMode = filters.logMode ?? AUDIT_LOG_MODE_ACCESS;
  }

  const eventType = parseEnum(params.get('eventType'), EVENT_TYPES);
  if (eventType) filters.eventType = eventType;

  const tier = parseEnum(params.get('tier'), TIERS);
  if (tier) filters.tier = tier;

  const signatureStatus = parseEnum(params.get('signatureStatus'), SIGNATURES);
  if (signatureStatus) filters.signatureStatus = signatureStatus;

  const actor = params.get('actor');
  if (actor) filters.actor = actor;

  const agent = params.get('agent');
  if (agent) filters.agent = agent;

  const envelopeId = params.get('envelopeId');
  if (envelopeId) filters.envelopeId = envelopeId;

  const endpoint = params.get('endpoint');
  if (endpoint) filters.endpoint = endpoint;

  const httpStatusCode = params.get('httpStatusCode');
  if (httpStatusCode && httpStatusCode !== 'all') {
    const parsed = Number.parseInt(httpStatusCode, 10);
    if (!Number.isNaN(parsed)) filters.httpStatusCode = parsed;
  }

  const eventId = params.get('eventId') ?? params.get('event_id');
  if (eventId) filters.eventId = eventId;

  const claimId = params.get('claimId');
  if (claimId) filters.claimId = claimId;

  const actionCategories = parseForensicActionCategories(params.get('actionCategories'));
  if (actionCategories) filters.actionCategories = actionCategories;

  if (params.get('openDrawer') === 'true') {
    filters.openDrawer = true;
  }

  const dateFrom = params.get('dateFrom');
  if (dateFrom) filters.dateFrom = dateFrom;

  const dateTo = params.get('dateTo');
  if (dateTo) filters.dateTo = dateTo;

  const cursor = params.get('cursor');
  if (cursor) filters.cursor = cursor;

  const offset = params.get('offset');
  if (offset) {
    const parsed = Number.parseInt(offset, 10);
    if (!Number.isNaN(parsed) && parsed >= 0) filters.offset = parsed;
  }

  const pageSize = params.get('pageSize');
  if (pageSize) {
    const parsed = Number.parseInt(pageSize, 10);
    if (!Number.isNaN(parsed) && parsed > 0) filters.pageSize = parsed;
  }

  if (!filters.logMode && filters.tier && filters.tier !== 'all') {
    const fromTier = tierToAuditLogMode(filters.tier);
    if (fromTier) filters.logMode = fromTier;
  }

  return filters;
}

export function auditFiltersToSearchParams(filters: AuditFilters): URLSearchParams {
  const params = new URLSearchParams();
  const logMode = resolveAuditLogMode(filters);
  params.set('log', auditLogModeToParam(logMode));

  if (filters.systemHealth) params.set('filter', 'system_health');
  if (filters.eventType && filters.eventType !== 'all') params.set('eventType', filters.eventType);
  const actionCategories = serializeForensicActionCategories(filters.actionCategories);
  if (actionCategories) params.set('actionCategories', actionCategories);
  if (filters.signatureStatus && filters.signatureStatus !== 'all')
    params.set('signatureStatus', filters.signatureStatus);
  if (filters.actor) params.set('actor', filters.actor);
  if (filters.agent) params.set('agent', filters.agent);
  if (filters.envelopeId) params.set('envelopeId', filters.envelopeId);
  if (filters.endpoint) params.set('endpoint', filters.endpoint);
  if (filters.httpStatusCode && filters.httpStatusCode !== 'all') {
    params.set('httpStatusCode', String(filters.httpStatusCode));
  }
  if (filters.eventId) params.set('eventId', filters.eventId);
  if (filters.claimId) params.set('claimId', filters.claimId);
  if (filters.openDrawer) params.set('openDrawer', 'true');
  if (filters.dateFrom) params.set('dateFrom', filters.dateFrom);
  if (filters.dateTo) params.set('dateTo', filters.dateTo);
  if (filters.cursor) params.set('cursor', filters.cursor);
  if (filters.pageSize) params.set('pageSize', String(filters.pageSize));
  return params;
}

export function stripModeIncompatibleAuditFilters(
  filters: AuditFilters,
  logMode: AuditLogMode,
): AuditFilters {
  const next: AuditFilters = { ...filters, logMode };
  delete next.tier;
  delete next.cursor;
  delete next.offset;

  if (logMode === 'access_history') {
    delete next.eventType;
    delete next.claimId;
    delete next.signatureStatus;
    delete next.openDrawer;
    if (next.systemHealth) {
      next.eventType = 'system_health';
    }
  } else {
    delete next.agent;
    delete next.endpoint;
    delete next.httpStatusCode;
    delete next.systemHealth;
    delete next.signatureStatus;
  }

  return logMode === 'forensic_log' ? resolveForensicAuditFilters(next) : next;
}
