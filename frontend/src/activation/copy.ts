export const ACTIVATION_COPY = {
  onboardingTitle: 'Activate your trust workspace',
  onboardingDescription:
    'Complete these steps to connect commerce evidence and claim sources before durable trust surfaces appear.',

  stepLabels: {
    1: 'Create trust workspace',
    2: 'Connect commerce truth',
    3: 'Connect claim sources',
    4: 'Confirm privacy boundary',
    5: 'Generate first TrustEnvelope',
    6: 'Invite teammates',
  } as const,

  step1: {
    heading: 'Create your trust workspace',
    body: 'Skeldir verifies revenue claims against deterministic commerce evidence. Start by naming the workspace that owns this evidence.',
    workspaceNameLabel: 'Workspace name',
    tenantContextLabel: 'Tenant context',
    continueBlocked: 'Confirm workspace context before continuing.',
    submitting: 'Confirming workspace…',
    success: 'Trust workspace confirmed.',
    error: 'Workspace activation failed. No financial truth was changed.',
  },

  step2: {
    heading: 'Connect commerce truth',
    body: 'Commerce and payment systems are the authority for verified revenue. Connect at least one source before reviewing attribution.',
    blockedCopy: 'Commerce truth is required before Skeldir can verify platform claims.',
    continueBlocked: 'Connect at least one commerce truth source to continue.',
  },

  step3: {
    heading: 'Connect claim sources',
    body: 'Ad platforms provide claims. Skeldir reconciles those claims against commerce evidence.',
    skipWarning:
      'You can verify commerce truth now. Attribution comparison begins after claim sources connect.',
    skipAction: 'Continue without claim sources',
  },

  step4: {
    heading: 'Confirm privacy boundary',
    body: 'Skeldir does not store durable email addresses, IP addresses, raw headers, user agents, or user-level identifiers in commerce truth.',
    acknowledgementLabel:
      'I confirm Skeldir’s privacy minimization boundary for commerce truth.',
    continueBlocked: 'Acknowledge the privacy boundary before completing activation.',
    confirming: 'Confirming privacy boundary…',
    success: 'Privacy boundary confirmed.',
    failure: 'Privacy boundary confirmation failed.',
  },

  footer: {
    back: 'Back',
    continue: 'Continue',
    complete: 'Complete activation',
    loading: 'Loading…',
  },

  routeGuard: {
    stepBlocked: 'Complete the previous activation step before continuing.',
    sessionRequired: 'Sign in to access activation.',
    tenantRequired: 'Create a tenant before accessing activation.',
  },

  completion: {
    title: 'Activation complete',
    body: 'Your workspace generated its first TrustEnvelope and teammate invitation paths are available through governed settings. TrustEnvelope ledgers and detail screens remain blocked until later levels.',
    integrationsLink: 'Manage integrations',
  },

  integrationsPageTitle: 'Integrations',
} as const;

export function stepLabel(step: 1 | 2 | 3 | 4 | 5 | 6): string {
  return ACTIVATION_COPY.stepLabels[step];
}
