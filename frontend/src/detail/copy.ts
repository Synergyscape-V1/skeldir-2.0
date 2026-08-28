export const DETAIL_COPY = {
  incrementalityBoundary:
    'This verdict does not prove incrementality. It verifies whether the revenue claim is supported by deterministic commerce evidence and the selected attribution model.',
  modelComparisonBoundary:
    'Attribution models are deterministic heuristics. They do not prove causal lift.',
  claimEvidenceBoundary:
    'Provenance for this claim is a canonically ordered, hashable structure for signature evidence—not a human-readable step log. Worker dispatch and internal job scheduling are not part of the trust proof.',
  claimEvidenceAuditPointer:
    'Cryptographic verification (semantic truth hash, audit reference) is on the Audit tab.',
  loading: 'Loading detail…',
  longLoading: 'Still loading detail. No financial truth was changed.',
  notFound: 'This object was not found for the current tenant.',
  permissionDenied: 'You do not have permission to view this detail.',
  scopeDenied: 'Your scope does not permit this detail surface.',
  objectIdMismatch: 'Detail identity does not match the route parameter.',
  staleVersion:
    'A newer version of this object exists. Displayed detail may be stale.',
  corruptedEvidence: 'Evidence chain could not be reconstructed safely.',
  schemaInvalid: 'Detail payload failed contract validation.',
  networkError: 'Network unavailable. Detail was not updated.',
  trustApiError: 'Trust API read failed. No financial truth was changed.',
  returnToClaims: 'Return to claims ledger',
  returnToTrust: 'Return to TrustEnvelope index',
  returnToChannels: 'Return to channel overview',
  returnToBudget: 'Return to budget simulation',
  returnToExceptions: 'Return to exception queue',
  level9BlockedPrefix: 'Opens in Level 9',
  level9CopyJson: 'Copy JSON (Level 9)',
  level9ExportArtifact: 'Export artifact (Level 9)',
  level9VerifySignature: 'Verify signature (Level 9)',
  level9SubmitProposal: 'Request certification (Level 9)',
  level9Acknowledge: 'Acknowledge (Level 9)',
  level9RequestEvidence: 'Request more evidence (Level 9)',
  level9MarkDisputed: 'Mark disputed (Level 9)',
  level9Suppress: 'Suppress similar low-risk alerts (Level 9)',
  level9CreateProposal: 'Create proposal (Level 9)',
  level9BlockedReason: (action: string) =>
    `${action} is a consequence-bearing flow deferred to Level 9. No mutation occurred.`,
  jsonInvalid: 'JSON contract could not be rendered safely.',
  jsonSearchLabel: 'Search JSON',
  exportReportBlockedLabel: 'Export verified report opens in Level 9',
} as const;
