import { Link } from 'react-router-dom';
import shared from '../../../styles/shared.module.css';
import { FIRST_TRUST_ENVELOPE_COPY } from '../../../firstTrustEnvelope/copy';
import { useActivationState } from '../../../activation/useActivationState';
import { getCurrentUserRole } from '../../../governance/governanceStore';
import { canManageTeam } from '../../../governance/permissions';
import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import { OnboardingStepPanel } from '../OnboardingStepPanel/OnboardingStepPanel';
import styles from './AddHumansOrAgentsStep.module.css';

export function AddHumansOrAgentsStep() {
  const activation = useActivationState();
  const role = getCurrentUserRole();
  const canInvite = canManageTeam(role);
  const permissionDenied = !canInvite;

  if (!activation.step5Complete && activation.generationPhase !== 'generation_already_exists') {
    return (
      <OnboardingStepPanel heading={FIRST_TRUST_ENVELOPE_COPY.step6.heading}>
        <p role="status">{FIRST_TRUST_ENVELOPE_COPY.step6.lockedBeforeEnvelope}</p>
      </OnboardingStepPanel>
    );
  }

  return (
    <OnboardingStepPanel
      heading={FIRST_TRUST_ENVELOPE_COPY.step6.heading}
      body={FIRST_TRUST_ENVELOPE_COPY.step6.body}
    >
      <div className={styles.panel} data-onboarding-step-6>
        {permissionDenied ? (
          <ErrorBanner message={FIRST_TRUST_ENVELOPE_COPY.step6.permissionDenied} />
        ) : null}

        <article className={styles.card}>
          <h3>{FIRST_TRUST_ENVELOPE_COPY.step6.humanPathTitle}</h3>
          <p>{FIRST_TRUST_ENVELOPE_COPY.step6.humanPathBody}</p>
          <Link
            to="/app/settings/team"
            className={[styles.link, !canInvite ? styles.linkDisabled : '', shared.focusVisible]
              .filter(Boolean)
              .join(' ')}
            aria-disabled={!canInvite}
            data-step6-team-link
          >
            {FIRST_TRUST_ENVELOPE_COPY.step6.humanPathLink}
          </Link>
        </article>

        <p className={styles.boundary}>{FIRST_TRUST_ENVELOPE_COPY.step6.truthBoundary}</p>
      </div>
    </OnboardingStepPanel>
  );
}
