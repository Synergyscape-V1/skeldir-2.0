import shared from '../../../styles/shared.module.css';

import { stepLabel } from '../../../activation/copy';

import type { OnboardingStep } from '../../../activation/types';

import styles from './OnboardingProgressRail.module.css';



export interface OnboardingProgressRailProps {

  currentStep: OnboardingStep;

  maxUnlockedStep: OnboardingStep;

  onStepSelect?: (step: OnboardingStep) => void;

}



const STEPS: OnboardingStep[] = [1, 2, 3, 4, 5, 6];



export function OnboardingProgressRail({

  currentStep,

  maxUnlockedStep,

  onStepSelect,

}: OnboardingProgressRailProps) {

  return (

    <nav className={styles.rail} aria-label="Onboarding progress">

      <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'contents' }}>

        {STEPS.map((step) => {

          const unlocked = step <= maxUnlockedStep;

          const active = step === currentStep;

          const complete = step < currentStep && unlocked;



          return (

            <li key={step}>

              <button

                type="button"

                className={[

                  styles.item,

                  shared.focusVisible,

                  active ? styles.itemActive : '',

                  complete ? styles.itemComplete : '',

                  !unlocked ? styles.itemDisabled : '',

                ]

                  .filter(Boolean)

                  .join(' ')}

                disabled={!unlocked}

                aria-current={active ? 'step' : undefined}

                onClick={() => unlocked && onStepSelect?.(step)}

                data-onboarding-step-rail={step}

              >

                <span className={styles.stepNumber}>Step {step}</span>

                <span>{stepLabel(step)}</span>

              </button>

            </li>

          );

        })}

      </ol>

    </nav>

  );

}


