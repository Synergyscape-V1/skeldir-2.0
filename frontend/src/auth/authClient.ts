import {
  readPersistedDesignSprintAuth,
} from './designSprintAuth';
import type {
  AuthOutcome,
  AuthTransport,
  IdentitySignUpInput,
  LoginCredentials,
  OAuthProvider,
  OrganizationCreateInput,
  Session,
  SignUpInput,
  Tenant,
  UserProfile,
} from './types';

/** Network boundary — fetch is permitted only in this module */
async function postJson<T>(
  url: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
    signal,
    credentials: 'include',
  });
  return response.json() as Promise<T>;
}

export interface AuthClient {
  login(credentials: LoginCredentials, signal?: AbortSignal): Promise<AuthOutcome>;
  signUp(input: SignUpInput, signal?: AbortSignal): Promise<AuthOutcome>;
  signUpIdentity(input: IdentitySignUpInput, signal?: AbortSignal): Promise<AuthOutcome>;
  createOrganization(input: OrganizationCreateInput, signal?: AbortSignal): Promise<AuthOutcome>;
  startOAuth(provider: OAuthProvider, signal?: AbortSignal): Promise<AuthOutcome>;
  validateSession(signal?: AbortSignal): Promise<AuthOutcome | { kind: 'no_session' }>;
}

export function createAuthClient(transport: AuthTransport): AuthClient {
  return {
    login: (credentials, signal) => transport.login(credentials, signal),
    signUp: (input, signal) => transport.signUp(input, signal),
    signUpIdentity: (input, signal) =>
      transport.signUpIdentity?.(input, signal) ??
      transport.signUp({ email: input.email, password: input.password, workspaceName: '' }),
    createOrganization: (input, signal) =>
      transport.createOrganization?.(input, signal) ??
      transport.signUp({
        email: '',
        password: '',
        workspaceName: input.organizationName,
      }),
    startOAuth: (provider, signal) => transport.startOAuth(provider, signal),
    validateSession: (signal) => transport.validateSession(signal),
  };
}

export interface MockAuthTransportOptions {
  loginResult?: AuthOutcome;
  signUpResult?: AuthOutcome;
  signUpIdentityResult?: AuthOutcome;
  createOrganizationResult?: AuthOutcome;
  oauthResult?: AuthOutcome;
  sessionResult?: AuthOutcome | { kind: 'no_session' };
  delayMs?: number;
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(timer);
      reject(new DOMException('Aborted', 'AbortError'));
    });
  });
}

export function createMockSession(overrides?: Partial<Session>): Session {
  return {
    sessionId: 'sess_test_001',
    userId: 'user_test_001',
    expiresAt: new Date(Date.now() + 3600_000).toISOString(),
    tenantId: 'tenant_test_001',
    ...overrides,
  };
}

export function createMockTenant(overrides?: Partial<Tenant>): Tenant {
  return {
    tenantId: 'tenant_test_001',
    workspaceName: 'Acme RevOps',
    onboardingStatus: 'pending',
    ...overrides,
  };
}

export function createMockUserProfile(overrides?: Partial<UserProfile>): UserProfile {
  return {
    firstName: 'Alex',
    lastName: 'Operator',
    email: 'engineering@skeldir.com',
    ...overrides,
  };
}

export function createMockAuthTransport(options: MockAuthTransportOptions = {}): AuthTransport {
  return {
    async login(_credentials, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      return options.loginResult ?? {
        kind: 'success_session_established',
        session: createMockSession(),
      };
    },
    async signUp(_input, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      return options.signUpResult ?? {
        kind: 'success_tenant_created',
        session: createMockSession(),
        tenant: createMockTenant(),
      };
    },
    async signUpIdentity(_input, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      return options.signUpIdentityResult ?? {
        kind: 'success_session_established',
        session: createMockSession({ tenantId: undefined }),
      };
    },
    async createOrganization(input, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      return options.createOrganizationResult ?? {
        kind: 'success_tenant_created',
        session: createMockSession(),
        tenant: createMockTenant({ workspaceName: input.organizationName }),
      };
    },
    async startOAuth(_provider, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      return options.oauthResult ?? {
        kind: 'success_session_established',
        session: createMockSession(),
      };
    },
    async validateSession(signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      if (options.sessionResult) return options.sessionResult;
      const persisted = readPersistedDesignSprintAuth();
      if (persisted) {
        return { kind: 'success_session_established', session: persisted.session };
      }
      return { kind: 'no_session' };
    },
  };
}

export function createHttpAuthTransport(baseUrl: string): AuthTransport {
  return {
    async login(credentials, signal) {
      try {
        return await postJson<AuthOutcome>(`${baseUrl}/auth/login`, credentials, signal);
      } catch {
        return { kind: 'network_error' };
      }
    },
    async signUp(input, signal) {
      try {
        return await postJson<AuthOutcome>(`${baseUrl}/auth/signup`, input, signal);
      } catch {
        return { kind: 'network_error' };
      }
    },
    async startOAuth(provider, signal) {
      try {
        return await postJson<AuthOutcome>(`${baseUrl}/auth/oauth/${provider}/start`, {}, signal);
      } catch {
        return { kind: 'network_error' };
      }
    },
    async validateSession(signal) {
      try {
        return await postJson<AuthOutcome | { kind: 'no_session' }>(
          `${baseUrl}/auth/session`,
          {},
          signal,
        );
      } catch {
        return { kind: 'network_error' };
      }
    },
  };
}

let defaultClient: AuthClient | null = null;

export function getDefaultAuthClient(): AuthClient {
  if (!defaultClient) {
    const baseUrl = import.meta.env.VITE_AUTH_API_BASE_URL ?? '';
    defaultClient = baseUrl
      ? createAuthClient(createHttpAuthTransport(baseUrl))
      : createAuthClient(createMockAuthTransport());
  }
  return defaultClient;
}

export function setDefaultAuthClient(client: AuthClient): void {
  defaultClient = client;
}

export function resetDefaultAuthClient(): void {
  defaultClient = null;
}
