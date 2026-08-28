import type {
  ClaimProvider,
  CommerceProvider,
  IntegrationOutcome,
  IntegrationProvider,
  IntegrationSourceState,
  IntegrationTransport,
} from './types';
import { CLAIM_PROVIDERS, COMMERCE_PROVIDERS } from './types';

/** Network boundary — fetch permitted only in this module */
async function postJson<T>(url: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
    signal,
    credentials: 'include',
  });
  return response.json() as Promise<T>;
}

export interface IntegrationClient {
  getWorkspace(tenantId: string, signal?: AbortSignal): Promise<IntegrationOutcome>;
  confirmWorkspace(
    tenantId: string,
    workspaceName: string,
    signal?: AbortSignal,
  ): Promise<IntegrationOutcome>;
  listIntegrations(tenantId: string, signal?: AbortSignal): Promise<IntegrationSourceState[]>;
  connectProvider(
    tenantId: string,
    provider: IntegrationProvider,
    signal?: AbortSignal,
  ): Promise<IntegrationOutcome>;
  repairProvider(
    tenantId: string,
    provider: IntegrationProvider,
    signal?: AbortSignal,
  ): Promise<IntegrationOutcome>;
  confirmPrivacyBoundary(tenantId: string, signal?: AbortSignal): Promise<IntegrationOutcome>;
}

export function createIntegrationClient(transport: IntegrationTransport): IntegrationClient {
  return {
    getWorkspace: (tenantId, signal) => transport.getWorkspace(tenantId, signal),
    confirmWorkspace: (tenantId, workspaceName, signal) =>
      transport.confirmWorkspace(tenantId, workspaceName, signal),
    listIntegrations: (tenantId, signal) => transport.listIntegrations(tenantId, signal),
    connectProvider: (tenantId, provider, signal) =>
      transport.connectProvider(tenantId, provider, signal),
    repairProvider: (tenantId, provider, signal) =>
      transport.repairProvider(tenantId, provider, signal),
    confirmPrivacyBoundary: (tenantId, signal) =>
      transport.confirmPrivacyBoundary(tenantId, signal),
  };
}

function defaultCommerceState(provider: CommerceProvider): IntegrationSourceState {
  return { provider, kind: 'commerce', status: 'not_connected' };
}

function defaultClaimState(provider: ClaimProvider): IntegrationSourceState {
  return { provider, kind: 'claim', status: 'not_connected' };
}

export function createDefaultIntegrationStates(): IntegrationSourceState[] {
  return [
    ...COMMERCE_PROVIDERS.map(defaultCommerceState),
    ...CLAIM_PROVIDERS.map(defaultClaimState),
  ];
}

export interface MockIntegrationTransportOptions {
  workspaceResult?: IntegrationOutcome;
  confirmWorkspaceResult?: IntegrationOutcome;
  integrations?: IntegrationSourceState[];
  connectResult?: IntegrationOutcome;
  repairResult?: IntegrationOutcome;
  privacyResult?: IntegrationOutcome;
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

export function createMockIntegrationTransport(
  options: MockIntegrationTransportOptions = {},
): IntegrationTransport {
  let integrations = options.integrations ?? createDefaultIntegrationStates();

  return {
    async getWorkspace(_tenantId, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      return (
        options.workspaceResult ?? {
          kind: 'workspace_ready',
          workspace: {
            tenantId: _tenantId,
            workspaceName: 'Acme RevOps',
            activationStatus: 'pending',
          },
        }
      );
    },
    async confirmWorkspace(tenantId, workspaceName, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      if (options.confirmWorkspaceResult) return options.confirmWorkspaceResult;
      return {
        kind: 'workspace_ready',
        workspace: { tenantId, workspaceName, activationStatus: 'confirmed' },
      };
    },
    async listIntegrations(_tenantId, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      return integrations;
    },
    async connectProvider(_tenantId, provider, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      if (options.connectResult) return options.connectResult;
      const kind = (COMMERCE_PROVIDERS as readonly string[]).includes(provider)
        ? 'commerce'
        : 'claim';
      const connected: IntegrationSourceState = {
        provider,
        kind: kind as 'commerce' | 'claim',
        status: kind === 'commerce' ? 'verification_ready' : 'connected',
        lastEventAt: kind === 'commerce' ? new Date().toISOString() : undefined,
        lastClaimAt: kind === 'claim' ? new Date().toISOString() : undefined,
        verificationLabel: kind === 'commerce' ? 'Signature verified' : undefined,
        reconciliationLabel: kind === 'claim' ? 'Pending commerce reconciliation' : undefined,
      };
      integrations = integrations.map((entry) =>
        entry.provider === provider ? connected : entry,
      );
      return kind === 'commerce'
        ? { kind: 'commerce_connected', provider: provider as CommerceProvider, state: connected }
        : {
            kind: 'claim_source_connected',
            provider: provider as ClaimProvider,
            state: connected,
          };
    },
    async repairProvider(tenantId, provider, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      if (options.repairResult) return options.repairResult;
      return this.connectProvider(tenantId, provider, signal);
    },
    async confirmPrivacyBoundary(_tenantId, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      return options.privacyResult ?? { kind: 'privacy_confirmed' };
    },
  };
}

export function createHttpIntegrationTransport(baseUrl: string): IntegrationTransport {
  return {
    async getWorkspace(tenantId, signal) {
      try {
        return await postJson<IntegrationOutcome>(
          `${baseUrl}/integrations/workspace`,
          { tenantId },
          signal,
        );
      } catch {
        return { kind: 'network_error' };
      }
    },
    async confirmWorkspace(tenantId, workspaceName, signal) {
      try {
        return await postJson<IntegrationOutcome>(
          `${baseUrl}/integrations/workspace/confirm`,
          { tenantId, workspaceName },
          signal,
        );
      } catch {
        return { kind: 'network_error' };
      }
    },
    async listIntegrations(tenantId, signal) {
      try {
        return await postJson<IntegrationSourceState[]>(
          `${baseUrl}/integrations/list`,
          { tenantId },
          signal,
        );
      } catch {
        return createDefaultIntegrationStates();
      }
    },
    async connectProvider(tenantId, provider, signal) {
      try {
        return await postJson<IntegrationOutcome>(
          `${baseUrl}/integrations/connect`,
          { tenantId, provider },
          signal,
        );
      } catch {
        return { kind: 'network_error' };
      }
    },
    async repairProvider(tenantId, provider, signal) {
      try {
        return await postJson<IntegrationOutcome>(
          `${baseUrl}/integrations/repair`,
          { tenantId, provider },
          signal,
        );
      } catch {
        return { kind: 'network_error' };
      }
    },
    async confirmPrivacyBoundary(tenantId, signal) {
      try {
        return await postJson<IntegrationOutcome>(
          `${baseUrl}/integrations/privacy/confirm`,
          { tenantId },
          signal,
        );
      } catch {
        return { kind: 'network_error' };
      }
    },
  };
}

let defaultClient: IntegrationClient | null = null;

export function getDefaultIntegrationClient(): IntegrationClient {
  if (!defaultClient) {
    const baseUrl =
      typeof import.meta !== 'undefined' && import.meta.env?.VITE_INTEGRATION_API_BASE
        ? String(import.meta.env.VITE_INTEGRATION_API_BASE)
        : '';
    defaultClient = baseUrl
      ? createIntegrationClient(createHttpIntegrationTransport(baseUrl))
      : createIntegrationClient(createMockIntegrationTransport());
  }
  return defaultClient;
}

export function setDefaultIntegrationClient(client: IntegrationClient): void {
  defaultClient = client;
}

export function resetDefaultIntegrationClient(): void {
  defaultClient = null;
}

export function isCommerceReady(states: IntegrationSourceState[]): boolean {
  return states.some(
    (entry) =>
      entry.kind === 'commerce' &&
      (entry.status === 'connected' ||
        entry.status === 'verification_pending' ||
        entry.status === 'verification_ready'),
  );
}

export function isClaimConnected(states: IntegrationSourceState[]): boolean {
  return states.some(
    (entry) =>
      entry.kind === 'claim' &&
      (entry.status === 'connected' ||
        entry.status === 'verification_ready' ||
        entry.status === 'verification_pending'),
  );
}
