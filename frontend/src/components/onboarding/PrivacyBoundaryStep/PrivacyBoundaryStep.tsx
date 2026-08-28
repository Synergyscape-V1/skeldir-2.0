import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import { ACTIVATION_COPY } from '../../../activation/copy';
import {
  setPrivacyAcknowledged,
  setPrivacyConfirming,
  setPrivacyConfirmed,
  setPrivacyFailed,
} from '../../../activation/activationStore';
import { useActivationState } from '../../../activation/useActivationState';
import { getAuthState } from '../../../auth/sessionStore';
import { getDefaultIntegrationClient } from '../../../integration/integrationClient';
import { mapIntegrationOutcomeToMessage } from '../../../integration/outcomeMapping';
import { PrivacyBoundaryAcknowledgement } from '../PrivacyBoundaryAcknowledgement/PrivacyBoundaryAcknowledgement';
import { OnboardingStepPanel } from '../OnboardingStepPanel/OnboardingStepPanel';

export function PrivacyBoundaryStep() {
  const activation = useActivationState();

  return (
    <OnboardingStepPanel heading={ACTIVATION_COPY.step4.heading}>
      <p id="privacy-boundary-copy" className="step-body">
        {ACTIVATION_COPY.step4.body}
      </p>
      <PrivacyBoundaryAcknowledgement
        checked={activation.privacyAcknowledged}
        onChange={setPrivacyAcknowledged}
        disabled={activation.privacyStatus === 'confirming'}
      />
      {activation.privacyStatus === 'confirmed' ? (
        <p role="status" aria-live="polite">
          {ACTIVATION_COPY.step4.success}
        </p>
      ) : null}
      {activation.privacyStatus === 'failed' && activation.privacyError ? (
        <ErrorBanner message={activation.privacyError} />
      ) : null}
    </OnboardingStepPanel>
  );
}

export async function submitPrivacyStep(acknowledged: boolean): Promise<boolean> {
  if (!acknowledged) {
    setPrivacyFailed(ACTIVATION_COPY.step4.continueBlocked);
    return false;
  }
  const { tenant } = getAuthState();
  if (!tenant) return false;
  setPrivacyConfirming();
  const client = getDefaultIntegrationClient();
  const outcome = await client.confirmPrivacyBoundary(tenant.tenantId);
  if (outcome.kind === 'privacy_confirmed') {
    setPrivacyConfirmed();
    return true;
  }
  setPrivacyFailed(
    mapIntegrationOutcomeToMessage(outcome) || ACTIVATION_COPY.step4.failure,
  );
  return false;
}
