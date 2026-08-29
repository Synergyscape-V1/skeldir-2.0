import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import { TimedLoadingPanel } from '../../../lib/loading';
import { ACTIVATION_COPY } from '../../../activation/copy';
import { CommerceSourceCard } from '../../integration/CommerceSourceCard/CommerceSourceCard';
import { useIntegrations } from '../../../integration/useIntegrations';
import { COMMERCE_PROVIDERS } from '../../../integration/types';
import { OnboardingStepPanel } from '../OnboardingStepPanel/OnboardingStepPanel';

export function CommerceTruthStep() {
  const { integrations, loading, error, connectProvider, repairProvider, commerceReady } =
    useIntegrations();

  const commerceStates = integrations.filter((entry) => entry.kind === 'commerce');

  return (
    <OnboardingStepPanel heading={ACTIVATION_COPY.step2.heading} body={ACTIVATION_COPY.step2.body}>
      {!commerceReady ? (
        <ErrorBanner variant="warning" message={ACTIVATION_COPY.step2.blockedCopy} />
      ) : null}
      {error ? <ErrorBanner message={error} /> : null}
      {loading ? (
        <TimedLoadingPanel active skeletonRows={4} skeletonVariant="block" />
      ) : (
        <div style={{ display: 'grid', gap: 'var(--sk-space-6)' }}>
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
        </div>
      )}
    </OnboardingStepPanel>
  );
}

export function isCommerceStepComplete(commerceReady: boolean): boolean {
  return commerceReady;
}
