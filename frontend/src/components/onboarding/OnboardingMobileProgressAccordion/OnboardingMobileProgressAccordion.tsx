import { useState } from 'react';

import shared from '../../../styles/shared.module.css';

import { stepLabel } from '../../../activation/copy';

import type { OnboardingStep } from '../../../activation/types';

import styles from './OnboardingMobileProgressAccordion.module.css';



export interface OnboardingMobileProgressAccordionProps {

  currentStep: OnboardingStep;

  maxUnlockedStep: OnboardingStep;

}



const STEPS: OnboardingStep[] = [1, 2, 3, 4, 5, 6];



export function OnboardingMobileProgressAccordion({

  currentStep,

  maxUnlockedStep,

}: OnboardingMobileProgressAccordionProps) {

  const [open, setOpen] = useState(false);



  return (

    <div className={styles.accordion} data-mobile-progress-accordion>

      <button

        type="button"

        className={[styles.trigger, shared.focusVisible].join(' ')}

        aria-expanded={open}

        aria-controls="mobile-progress-panel"

        onClick={() => setOpen((value) => !value)}

      >

        <span>

          Step {currentStep} of 6 — {stepLabel(currentStep)}

        </span>

        <span className={[styles.chevron, open ? styles.chevronOpen : ''].join(' ')} aria-hidden>

          ▾

        </span>

      </button>

      {open ? (

        <div id="mobile-progress-panel" className={styles.panel} role="region" aria-label="Onboarding steps">

          <ul className={styles.stepList}>

            {STEPS.map((step) => (

              <li

                key={step}

                className={[

                  styles.stepItem,

                  step === currentStep ? styles.stepItemActive : '',

                  step > maxUnlockedStep ? styles.stepItem : '',

                ]

                  .filter(Boolean)

                  .join(' ')}

              >

                Step {step}: {stepLabel(step)}

                {step > maxUnlockedStep ? ' (locked)' : ''}

              </li>

            ))}

          </ul>

        </div>

      ) : null}

    </div>

  );

}


