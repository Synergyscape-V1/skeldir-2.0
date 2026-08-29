import type { AuditFilters, AuditLogMode, AuditTier } from './types';

export const AUDIT_LOG_MODE_ACCESS: AuditLogMode = 'access_history';
export const AUDIT_LOG_MODE_FORENSIC: AuditLogMode = 'forensic_log';

export function resolveAuditLogMode(filters: AuditFilters): AuditLogMode {
  if (filters.logMode) return filters.logMode;
  if (filters.tier && filters.tier !== 'all') {
    const fromTier = tierToAuditLogMode(filters.tier);
    if (fromTier) return fromTier;
  }
  return AUDIT_LOG_MODE_ACCESS;
}

export function auditLogModeToTier(mode: AuditLogMode): AuditTier {
  return mode === AUDIT_LOG_MODE_FORENSIC ? 'tier_b' : 'tier_a';
}

export function tierToAuditLogMode(tier: AuditTier): AuditLogMode | undefined {
  if (tier === 'tier_a') return AUDIT_LOG_MODE_ACCESS;
  if (tier === 'tier_b') return AUDIT_LOG_MODE_FORENSIC;
  return undefined;
}

export function parseAuditLogMode(value: string | null | undefined): AuditLogMode | undefined {
  if (value === 'access' || value === 'access_history') return AUDIT_LOG_MODE_ACCESS;
  if (value === 'forensic' || value === 'forensic_log') return AUDIT_LOG_MODE_FORENSIC;
  return undefined;
}

export function auditLogModeToParam(mode: AuditLogMode): string {
  return mode === AUDIT_LOG_MODE_FORENSIC ? 'forensic' : 'access';
}
