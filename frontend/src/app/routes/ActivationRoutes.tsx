import { Typography } from '../../components/layout/Typography/Typography';
import { ACTIVATION_COPY } from '../../activation/copy';
import { Level3RouteGuard } from '../../components/onboarding/Level3RouteGuard/Level3RouteGuard';
import { IntegrationGroup } from '../../components/integration/IntegrationGroup/IntegrationGroup';
import { CommerceSourceCard } from '../../components/integration/CommerceSourceCard/CommerceSourceCard';
import { ClaimSourceCard } from '../../components/integration/ClaimSourceCard/ClaimSourceCard';
import { IntegrationReadinessSummary } from '../../components/integration/IntegrationReadinessSummary/IntegrationReadinessSummary';
import { INTEGRATION_COPY } from '../../integration/copy';
import { useIntegrations } from '../../integration/useIntegrations';
import { COMMERCE_PROVIDERS, CLAIM_PROVIDERS } from '../../integration/types';
import { TimedLoadingPanel } from '../../lib/loading';
import { ErrorBanner } from '../../components/layout/ErrorBanner/ErrorBanner';
import { useActivationState } from '../../activation/useActivationState';
import styles from './integrationsPage.module.css';

export function IntegrationsPage() {
  const { integrations, loading, error, connectProvider, repairProvider } = useIntegrations();
  const activation = useActivationState();

  const commerceStates = integrations.filter((entry) => entry.kind === 'commerce');
  const claimStates = integrations.filter((entry) => entry.kind === 'claim');

  return (
    <Level3RouteGuard mode="integrations">
      <div className={styles.page} data-integrations-page>
        <Typography variant="h1">{ACTIVATION_COPY.integrationsPageTitle}</Typography>
        <IntegrationReadinessSummary
          integrations={integrations}
          claimSkipped={activation.claimSkipped}
        />
        {error ? <ErrorBanner message={error} /> : null}
        {loading ? (
          <TimedLoadingPanel active skeletonRows={6} skeletonVariant="block" />
        ) : (
          <div className={styles.groups}>
            <IntegrationGroup
              id="commerce-truth-group"
              title={INTEGRATION_COPY.commerceGroupTitle}
              description={INTEGRATION_COPY.commerceGroupDescription}
            >
              {COMMERCE_PROVIDERS.map((provider) => {
                const state = commerceStates.find((entry) => entry.provider === provider);
                if (!state) return null;
                return (
                  <CommerceSourceCard
                    key={provider}
                    state={state}
                    onConnect={connectProvider}
                    onRepair={repairProvider}
                  />
                );
              })}
            </IntegrationGroup>
            <IntegrationGroup
              id="claim-sources-group"
              title={INTEGRATION_COPY.claimGroupTitle}
              description={INTEGRATION_COPY.claimGroupDescription}
            >
              {CLAIM_PROVIDERS.map((provider) => {
                const state = claimStates.find((entry) => entry.provider === provider);
                if (!state) return null;
                return (
                  <ClaimSourceCard
                    key={provider}
                    state={state}
                    onConnect={connectProvider}
                    onRepair={repairProvider}
                  />
                );
              })}
            </IntegrationGroup>
          </div>
        )}
      </div>
    </Level3RouteGuard>
  );
}
