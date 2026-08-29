import type { ReactNode } from 'react';
import { Typography } from '../../layout/Typography/Typography';
import styles from './OnboardingStepPanel.module.css';

export interface OnboardingStepPanelProps {
  heading: string;
  body?: string;
  children: ReactNode;
  footer?: ReactNode;
}

export function OnboardingStepPanel({ heading, body, children, footer }: OnboardingStepPanelProps) {
  return (
    <article className={styles.panel} data-onboarding-step-panel>
      <div className={styles.content}>
        <Typography variant="h2" className={styles.heading}>
          {heading}
        </Typography>
        {body ? (
          <p className={styles.body} id="step-panel-body">
            {body}
          </p>
        ) : null}
        {children}
      </div>
      {footer}
    </article>
  );
}
