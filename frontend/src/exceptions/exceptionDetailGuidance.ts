import type { ExceptionCategory, ExceptionQueueRowDTO, ExceptionSeverity } from '../ledger/types';
import type { ExceptionDetailDTO } from '../detail/types';

/** Queue severity → detail DTO severity (detail contract uses low|medium|high|critical). */
export function mapQueueSeverityToDetailSeverity(
  severity: ExceptionSeverity,
): ExceptionDetailDTO['severity'] {
  switch (severity) {
    case 'critical':
      return 'critical';
    case 'warning':
      return 'medium';
    case 'info':
      return 'low';
    default:
      return 'medium';
  }
}

/**
 * Category-specific review steps. Generic attribution/discrepancy guidance must not
 * appear on integration, policy, signature, agent, or benchmark exceptions.
 */
export const EXCEPTION_CATEGORY_NEXT_REVIEW: Record<ExceptionCategory, readonly string[]> = {
  discrepancy_review: [
    'Inspect claim evidence timeline against commerce events',
    'Compare platform-claimed vs verified revenue in minor units',
    'Wait for additional commerce events if coverage is sparse',
  ],
  policy_approval_required: [
    'Confirm the simulation is ready and Finance Approver was notified',
    'Await certification — this gate cannot be self-cleared',
    'Nudge Finance Approver if certification is overdue',
  ],
  signature_verification_failure: [
    'Open the audit reference and verify artifact and signature hashes',
    'Confirm signature verification status before trusting the export',
    'Do not treat an unverified signature as financial truth',
  ],
  benchmark_source_transition: [
    'Confirm this is a benchmark source transition, not market movement',
    'Review evidence class and coverage class before acting',
    'Keep raw benchmark separate from decision-safe context',
  ],
  agent_access_denied: [
    'Review agent scopes against the denied operation',
    'Ensure reserved scopes remain disabled',
    'Re-issue credentials only with allowed read scopes',
  ],
  integration_repair_needed: [
    'Open integration health for the affected connector',
    'Repair or re-authenticate the commerce or claim source',
    'Re-check ingress only after connector verification succeeds',
  ],
};

export function recommendedNextReviewForCategory(category: ExceptionCategory): string[] {
  return [...EXCEPTION_CATEGORY_NEXT_REVIEW[category]];
}

export function buildExceptionDetailFromQueueRow(
  row: ExceptionQueueRowDTO,
  tenantId: string,
): ExceptionDetailDTO {
  return {
    exceptionId: row.exceptionId,
    tenantId,
    category: row.category,
    severity: mapQueueSeverityToDetailSeverity(row.severity),
    affectedObject: row.affectedObjectLabel || row.subject,
    createdAt: row.createdAt,
    reviewState: row.status,
    policyAuthority: row.policyAuthority,
    evidenceSummary: row.summary,
    auditReference: row.auditReference,
    recommendedNextReview: recommendedNextReviewForCategory(row.category),
    versionStamp: `v_${row.exceptionId}_1`,
  };
}
