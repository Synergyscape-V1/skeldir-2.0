export const ACTION_COPY = {
  exceptionActionsHeading: 'Choose a response',
  exceptionActionsIntro:
    'Select the next supervised step. Every available action is policy-gated and requires confirmation.',
  completeReviewHeading: 'Complete review',
  completeReviewBody: 'Record that this exception has been reviewed.',
  continueInvestigationHeading: 'Continue investigation',
  continueInvestigationBody: 'Request supporting evidence or flag the current finding as disputed.',
  governedFollowUpHeading: 'Governed follow-up',
  governedFollowUpBody: 'Adjust future alert handling or open a proposal for review.',
  signatureIntegrityDisclaimer:
    'Signature verification proves artifact integrity and signing authority. It does not create financial truth.',
  policyBlocked: 'Policy authority blocks this action. No artifact or workflow mutation occurred.',
  permissionDenied: 'You do not have permission to perform this action.',
  scopeDenied: 'This object is outside your tenant scope.',
  subsystemUnsafe: 'Trust systems are degraded. External and consequence-bearing actions are unavailable.',
  replayRejected: 'This action was already submitted. No duplicate artifact was created.',
  auditWriteFailed: 'Audit record could not be written. No artifact should be treated as externally valid.',
  artifactUnavailable: 'The requested artifact is unavailable. No export was created.',
  networkError: 'Trust API read failed. No financial truth was changed.',
  timeout: 'The action timed out. Verify audit reference before retrying.',
  staleObject: 'The object changed while this action was pending. Refresh and retry.',
  partialFailure: 'The action partially completed. Do not use any artifact until audit reference is confirmed.',
  exportNoArtifact: 'Export failed. No artifact was created.',
  proposalSuccess: (proposalId: string) =>
    `Proposal ${proposalId} created for review. No spend was executed.`,
  copyJsonSuccess: 'Canonical TrustEnvelope JSON copied.',
  copyJsonOversize: 'JSON exceeds safe copy limit. Use export artifact with artifact reference.',
  clipboardDeniedReady:
    'Copy is ready. Click Copy JSON again to deliver to clipboard after granting permission.',
  verifyValid: 'Signature verified. This artifact matches the canonical payload.',
  verifyInvalid: 'Signature verification failed. Do not use this artifact externally.',
  verifySignaturePending: 'Verifying artifact against public key…',
  suppressScope:
    'Suppressing similar low-risk alerts affects only alerts matching this category and severity within tenant scope.',
  incrementalityLegend:
    'Verified revenue is commerce-backed deterministic truth. Platform claims require reconciliation.',
} as const;
