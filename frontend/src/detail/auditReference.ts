import { auditFiltersToSearchParams } from '../operationalAudit/parseAuditFilters';
import type { AuditLogMode } from '../operationalAudit/types';

export function buildAuditReferenceHref(
  auditReference: string,
  options?: {
    envelopeId?: string;
    claimId?: string;
    openDrawer?: boolean;
    logMode?: AuditLogMode;
  },
): string {
  const params = auditFiltersToSearchParams({
    logMode: options?.logMode,
    envelopeId: options?.envelopeId,
    claimId: options?.claimId,
    eventId: auditReference,
    openDrawer: options?.openDrawer,
  });
  return `/app/audit?${params.toString()}`;
}

export function buildTrustEnvelopeAuditReferenceHref(
  auditReference: string,
  envelopeId: string,
  options?: { openTechnicalDetails?: boolean },
): string {
  return buildAuditReferenceHref(auditReference, {
    envelopeId,
    logMode: 'forensic_log',
    openDrawer: options?.openTechnicalDetails,
  });
}

export function formatAuditReferenceLabel(auditReference: string): string {
  return auditReference;
}
