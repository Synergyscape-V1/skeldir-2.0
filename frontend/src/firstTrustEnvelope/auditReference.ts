export {
  buildAuditReferenceHref,
  buildTrustEnvelopeAuditReferenceHref,
  formatAuditReferenceLabel,
} from '../detail/auditReference';

/** @deprecated Use buildAuditReferenceHref from detail/auditReference */
export function buildAuditReferenceLabel(auditEventId: string): string {
  return `Audit event ${auditEventId}`;
}
