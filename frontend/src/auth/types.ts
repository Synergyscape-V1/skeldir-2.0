export type OAuthProvider = 'github' | 'google' | 'microsoft';

export const OAUTH_PROVIDERS: readonly OAuthProvider[] = ['github', 'google', 'microsoft'];

export interface Session {
  sessionId: string;
  userId: string;
  expiresAt: string;
  tenantId?: string;
}

export interface Tenant {
  tenantId: string;
  workspaceName: string;
  onboardingStatus: 'pending' | 'ready';
}

export interface UserProfile {
  firstName: string;
  lastName: string;
  email: string;
}

export type AuthOutcome =
  | { kind: 'success_session_established'; session: Session }
  | { kind: 'success_tenant_created'; session: Session; tenant: Tenant }
  | { kind: 'invalid_credentials' }
  | { kind: 'email_not_business'; detail?: string }
  | { kind: 'tenant_already_exists' }
  | { kind: 'oauth_provider_unavailable'; provider: OAuthProvider }
  | { kind: 'oauth_callback_error'; provider: OAuthProvider; detail?: string }
  | { kind: 'rate_limited'; retryAfterSeconds?: number }
  | { kind: 'network_error' }
  | { kind: 'session_expired' }
  | { kind: 'permission_denied' }
  | { kind: 'tenant_creation_pending'; tenantId: string }
  | { kind: 'tenant_creation_failed'; detail?: string }
  | { kind: 'unknown_error'; detail?: string };

export type AuthFormState =
  | 'uninitialized'
  | 'loading'
  | 'submitting'
  | 'success'
  | 'invalid_input'
  | 'auth_error'
  | 'oauth_pending'
  | 'oauth_error'
  | 'network_failure'
  | 'rate_limited'
  | 'session_expired'
  | 'tenant_pending'
  | 'tenant_exists'
  | 'tenant_creation_failed'
  | 'unsafe_redirect'
  | 'disabled'
  | 'focused'
  | 'already_authenticated';

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface SignUpInput {
  email: string;
  password: string;
  workspaceName: string;
}

export interface IdentitySignUpInput {
  firstName: string;
  lastName: string;
  email: string;
  password: string;
}

export interface OrganizationCreateInput {
  organizationName: string;
  inviteEmails?: string[];
}

export interface AuthTransport {
  login(credentials: LoginCredentials, signal?: AbortSignal): Promise<AuthOutcome>;
  signUp(input: SignUpInput, signal?: AbortSignal): Promise<AuthOutcome>;
  signUpIdentity?(input: IdentitySignUpInput, signal?: AbortSignal): Promise<AuthOutcome>;
  createOrganization?(input: OrganizationCreateInput, signal?: AbortSignal): Promise<AuthOutcome>;
  startOAuth(provider: OAuthProvider, signal?: AbortSignal): Promise<AuthOutcome>;
  validateSession(signal?: AbortSignal): Promise<AuthOutcome | { kind: 'no_session' }>;
}
