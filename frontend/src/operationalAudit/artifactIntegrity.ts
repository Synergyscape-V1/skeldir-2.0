import type { AuditArtifactOutcome } from './types';

/** JSON preview is permitted only when artifact integrity is fully safe */
export function canRenderArtifactJsonPreview(outcome: AuditArtifactOutcome): boolean {
  return outcome.kind === 'artifact_loaded';
}

export function detectInvalidSignatureJsonLeak(
  invalidSignatureAlertVisible: boolean,
  jsonPreviewVisible: boolean,
): boolean {
  return invalidSignatureAlertVisible && jsonPreviewVisible;
}
