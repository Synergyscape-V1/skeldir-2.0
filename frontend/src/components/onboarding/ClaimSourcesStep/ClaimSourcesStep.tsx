import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import { TimedLoadingPanel } from '../../../lib/loading';
import { SubmitButton } from '../../form/SubmitButton/SubmitButton';
import { ACTIVATION_COPY } from '../../../activation/copy';
import { setClaimSkipped } from '../../../activation/activationStore';
import { useActivationState } from '../../../activation/useActivationState';
import { ClaimSourceCard } from '../../integration/ClaimSourceCard/ClaimSourceCard';
import { useIntegrations } from '../../../integration/useIntegrations';
import { CLAIM_PROVIDERS } from '../../../integration/types';
import { isClaimConnected as checkClaimConnected } from '../../../integration/integrationClient';
import { OnboardingStepPanel } from '../OnboardingStepPanel/OnboardingStepPanel';

export function ClaimSourcesStep() {
  const activation = useActivationState();
  const { integrations, loading, error, connectProvider, repairProvider } = useIntegrations();
  const claimStates = integrations.filter((entry) => entry.kind === 'claim');
  const anyClaimConnected = checkClaimConnected(integrations);

  return (
    <OnboardingStepPanel heading={ACTIVATION_COPY.step3.heading} body={ACTIVATION_COPY.step3.body}>
      {activation.claimSkipWarningVisible || (!anyClaimConnected && activation.claimSkipped) ? (
        <ErrorBanner variant="warning" message={ACTIVATION_COPY.step3.skipWarning} />
      ) : null}
      {error ? <ErrorBanner message={error} /> : null}
      {loading ? (
        <TimedLoadingPanel active skeletonRows={4} skeletonVariant="block" />
      ) : (
        <div style={{ display: 'grid', gap: 'var(--sk-space-6)' }}>
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
        </div>
      )}
      {!anyClaimConnected ? (
        <SubmitButton
          type="button"
          variant="secondary"
          onClick={() => setClaimSkipped(true)}
        >
          {ACTIVATION_COPY.step3.skipAction}
        </SubmitButton>
      ) : null}
    </OnboardingStepPanel>
  );
}

export function isClaimStepComplete(
  integrations: ReturnType<typeof useIntegrations>['integrations'],
  claimSkipped: boolean,
): boolean {
  return claimSkipped || checkClaimConnected(integrations);
}
