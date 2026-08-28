import { useCallback, useEffect, useState } from 'react';
import { getAuthState } from '../auth/sessionStore';
import {
  createDefaultIntegrationStates,
  getDefaultIntegrationClient,
  isCommerceReady,
} from '../integration/integrationClient';
import { mapIntegrationOutcomeToMessage } from '../integration/outcomeMapping';
import type { IntegrationProvider, IntegrationSourceState } from '../integration/types';
import { setIntegrationsLoaded } from '../activation/activationStore';

export function useIntegrations() {
  const [integrations, setIntegrations] = useState<IntegrationSourceState[]>(
    createDefaultIntegrationStates(),
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | undefined>();

  const refresh = useCallback(async () => {
    const { tenant } = getAuthState();
    if (!tenant) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(undefined);
    try {
      const client = getDefaultIntegrationClient();
      const list = await client.listIntegrations(tenant.tenantId);
      setIntegrations(list);
      setIntegrationsLoaded();
    } catch {
      setError('Integration service unavailable. Try again shortly.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const connectProvider = useCallback(
    async (provider: IntegrationProvider) => {
      const { tenant } = getAuthState();
      if (!tenant) return;
      const client = getDefaultIntegrationClient();
      const outcome = await client.connectProvider(tenant.tenantId, provider);
      if (
        outcome.kind === 'commerce_connected' ||
        outcome.kind === 'claim_source_connected'
      ) {
        await refresh();
        return;
      }
      const message = mapIntegrationOutcomeToMessage(outcome);
      if (message) setError(message);
      else setError('Connection action failed. No financial truth was changed.');
    },
    [refresh],
  );

  const repairProvider = useCallback(
    async (provider: IntegrationProvider) => {
      const { tenant } = getAuthState();
      if (!tenant) return;
      const client = getDefaultIntegrationClient();
      const outcome = await client.repairProvider(tenant.tenantId, provider);
      if (
        outcome.kind === 'commerce_connected' ||
        outcome.kind === 'claim_source_connected'
      ) {
        await refresh();
        return;
      }
      const message = mapIntegrationOutcomeToMessage(outcome);
      if (message) setError(message);
    },
    [refresh],
  );

  return {
    integrations,
    loading,
    error,
    commerceReady: isCommerceReady(integrations),
    refresh,
    connectProvider,
    repairProvider,
  };
}
