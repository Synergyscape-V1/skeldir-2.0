import { SubmitButton } from '../../form/SubmitButton/SubmitButton';
import { ACTIVATION_COPY } from '../../../activation/copy';
import styles from './OnboardingFooterControls.module.css';

export interface OnboardingFooterControlsProps {
  onBack?: () => void;
  onContinue: () => void;
  backDisabled?: boolean;
  continueDisabled?: boolean;
  continueLoading?: boolean;
  continueLabel?: string;
  blockedReason?: string;
  showBack?: boolean;
}

export function OnboardingFooterControls({
  onBack,
  onContinue,
  backDisabled = false,
  continueDisabled = false,
  continueLoading = false,
  continueLabel,
  blockedReason,
  showBack = true,
}: OnboardingFooterControlsProps) {
  return (
    <footer className={styles.footer} data-onboarding-footer>
      {blockedReason ? (
        <p className={styles.blockedReason} role="alert" id="onboarding-continue-blocked">
          {blockedReason}
        </p>
      ) : null}
      <div className={styles.footer} style={{ border: 'none', paddingTop: 0, marginTop: 0 }}>
        {showBack ? (
          <SubmitButton
            type="button"
            variant="secondary"
            disabled={backDisabled || continueLoading}
            onClick={onBack}
          >
            {ACTIVATION_COPY.footer.back}
          </SubmitButton>
        ) : (
          <span />
        )}
        <SubmitButton
          type="button"
          loading={continueLoading}
          disabled={continueDisabled}
          onClick={onContinue}
          aria-describedby={blockedReason ? 'onboarding-continue-blocked' : undefined}
        >
          {continueLabel ?? ACTIVATION_COPY.footer.continue}
        </SubmitButton>
      </div>
      <div className={styles.liveRegion} aria-live="polite" aria-atomic="true">
        {continueLoading ? ACTIVATION_COPY.footer.loading : ''}
      </div>
    </footer>
  );
}
