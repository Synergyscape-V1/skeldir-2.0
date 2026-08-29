import { Link } from 'react-router-dom';

import shared from '../../../styles/shared.module.css';

import { FIRST_TRUST_ENVELOPE_COPY } from '../../../firstTrustEnvelope/copy';

import { mapReadinessOutcomeToMessage } from '../../../firstTrustEnvelope/outcomeMapping';

import { isGenerationErrorPhase } from '../../../firstTrustEnvelope/step5StateMachine';

import { useActivationState } from '../../../activation/useActivationState';

import { useFirstTrustEnvelopeGeneration } from '../../../firstTrustEnvelope/useFirstTrustEnvelopeGeneration';

import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';

import { Skeleton } from '../../layout/Skeleton/Skeleton';

import { OnboardingStepPanel } from '../OnboardingStepPanel/OnboardingStepPanel';

import { FirstTrustEnvelopeSummary } from '../FirstTrustEnvelopeSummary/FirstTrustEnvelopeSummary';

import styles from './GenerateFirstTrustEnvelopeStep.module.css';



export function GenerateFirstTrustEnvelopeStep() {

  const activation = useActivationState();

  const { prerequisiteState, statusMessage, submitLocked, loadingReadiness, canGenerate, generate } =

    useFirstTrustEnvelopeGeneration();



  const showSummary =

    activation.firstEnvelopeSummary &&

    (activation.generationPhase === 'generation_succeeded' ||

      activation.generationPhase === 'generation_already_exists');



  const isErrorPhase = isGenerationErrorPhase(activation.generationPhase);



  const blockedMessage =

    prerequisiteState !== 'ready_to_generate'

      ? mapReadinessOutcomeToMessage({

          kind: 'first_envelope_unavailable',

          reason: prerequisiteState,

        })

      : undefined;



  const isGenerating =

    activation.generationPhase === 'generation_queued' ||

    activation.generationPhase === 'generation_in_progress';



  return (

    <OnboardingStepPanel

      heading={FIRST_TRUST_ENVELOPE_COPY.step5.heading}

      body={FIRST_TRUST_ENVELOPE_COPY.step5.body}

    >

      <div className={styles.panel} data-onboarding-step-5>

        <p className={styles.claimWarning}>{FIRST_TRUST_ENVELOPE_COPY.step5.claimTruthWarning}</p>



        {loadingReadiness ? <Skeleton rows={3} variant="block" /> : null}



        {blockedMessage && !showSummary ? (

          <p role="status" className={styles.status}>

            {blockedMessage}

          </p>

        ) : null}



        {prerequisiteState === 'waiting_for_verified_commerce_event' ? (

          <Link to="/app/integrations" className={styles.waitingLink}>

            {FIRST_TRUST_ENVELOPE_COPY.step5.waitingEventAction}

          </Link>

        ) : null}



        {statusMessage ? (

          <p

            role={isErrorPhase ? 'alert' : 'status'}

            aria-live={isErrorPhase ? 'assertive' : 'polite'}

            className={styles.status}

            data-generation-status

          >

            {statusMessage}

          </p>

        ) : null}



        {isGenerating ? (

          <Skeleton rows={4} variant="block" aria-busy="true" />

        ) : null}



        {isErrorPhase && statusMessage ? <ErrorBanner message={statusMessage} /> : null}



        {showSummary && activation.firstEnvelopeSummary ? (

          <FirstTrustEnvelopeSummary envelope={activation.firstEnvelopeSummary} />

        ) : null}



        {!showSummary ? (

          <div className={styles.actions}>

            <button

              type="button"

              className={[styles.generateButton, shared.focusVisible].join(' ')}

              disabled={!canGenerate || submitLocked}

              aria-disabled={!canGenerate || submitLocked}

              aria-describedby={blockedMessage ? 'step5-blocked-reason' : undefined}

              onClick={() => void generate()}

              data-generate-first-envelope

            >

              {isErrorPhase

                ? FIRST_TRUST_ENVELOPE_COPY.step5.retryLabel

                : FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel}

            </button>

            {blockedMessage ? (

              <span id="step5-blocked-reason" className={shared.srOnly}>

                {blockedMessage}

              </span>

            ) : null}

          </div>

        ) : null}

      </div>

    </OnboardingStepPanel>

  );

}

