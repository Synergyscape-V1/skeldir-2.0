/** Level 2 app shell copy — no health semantics, no trust summaries */

export const SHELL_COPY = {
  shellLandingTitle: 'App frame ready',
  shellLandingBody:
    'You are inside the authenticated Skeldir product frame. Downstream trust surfaces unlock in later build levels. This is not the Overview.',
  shellLandingNextStep:
    'Onboarding and integrations become available at Level 3. Use navigation to inspect blocked destinations and their unlock levels.',
  blockedRouteTitle: (label: string) => `${label} is not available yet`,
  blockedRouteBody: (unlockLabel: string) =>
    `${unlockLabel} has not been implemented at this build level. Skeldir will not render placeholder product content for unavailable routes.`,
  blockedRouteInvariant:
    'This panel confirms topological blocking — not a preview of downstream UI.',
  unknownRouteTitle: 'Unknown authenticated route',
  unknownRouteBody:
    'This path is not registered in the Level 2 shell. No downstream product surface was rendered.',
  sessionMissingTitle: 'Session required',
  sessionMissingBody: 'Sign in to access the authenticated app frame.',
  tenantMissingTitle: 'Workspace required',
  tenantMissingBody:
    'A tenant workspace must exist before the app frame can render tenant-scoped navigation.',
  tenantMissingAction: 'Create a workspace',
  permissionDeniedTitle: 'Permission denied',
  permissionDeniedBody: 'You do not have permission to access this shell region.',
  shellLoading: 'Loading app frame…',
  shellError: 'Unable to load the app frame. No trust state was changed.',
  skipToContent: 'Skip to main content',
  sidebarLabel: 'Primary navigation',
  bottomNavLabel: 'Mobile primary navigation',
  moreNavLabel: 'More navigation',
  moreNavTitle: 'All navigation',
  pageTitleDefault: 'Skeldir',
  commandCenterPageTitle: 'Overview',
  notificationsLabel: 'Notifications',
  interfaceLocationLabel: (name: string) => `Current interface: ${name}`,
  welcomeBack: (tenantName: string) => `Welcome Back ${tenantName}`,
  sidebarToggleCollapse: 'Collapse navigation sidebar',
  sidebarToggleExpand: 'Expand navigation sidebar',
  chatToggleOpen: 'Open workspace assistant',
  chatToggleClose: 'Close workspace assistant',
  chatPanelTitle: 'Workspace assistant',
  chatPanelDescription:
    'Ask questions about navigation, trust workflows, and policy context. Responses are UI-only until a model provider is connected.',
  chatEmptyTitle: 'How can I help?',
  chatEmptyDescription: 'Choose a prompt below or write your own message.',
  chatComposerLabel: 'Message',
  chatComposerPlaceholder: 'Ask about trust workflows, audit events, or navigation…',
  chatSend: 'Send message',
  chatModelLabel: 'Model',
  chatRecommendedLabel: 'Recommended',
  chatRecommendedToggle: 'Use recommended model',
  chatRecommendedDescription: 'Our top pick for fast, high-quality responses',
  chatPanelResize: 'Resize workspace assistant panel',
  chatTabsLabel: 'Agent conversations',
  chatSessionTabLabel: 'New Agent',
  chatNewSession: 'New agent chat',
  chatHistoryLabel: 'Agent chat history',
  chatCloseSession: (title: string) => `Close ${title}`,
  chatTyping: 'Assistant is typing',
  chatStubReplyPrefix: 'Preview response:',
  chatSuggestions: [
    'How do I review audit events?',
    'Explain trust envelope tiers',
    'Where are integration settings?',
  ] as const,
  accountMenuLabel: 'Account menu',
  accountMenuLogout: 'Log out',
  accountInitialsLabel: (initials: string) => `Account initials ${initials}`,
  enterAppFrame: 'Enter app frame',
  handoffSessionBody:
    'Your product session is active. Continue into the authenticated app frame when your workspace is ready.',
  handoffWorkspaceBody:
    'Your workspace exists. Enter the app frame to begin supervised trust workflows once downstream levels unlock.',
} as const;
