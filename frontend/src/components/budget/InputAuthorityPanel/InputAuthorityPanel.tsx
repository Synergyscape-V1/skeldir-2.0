import { BUDGET_SIMULATION_COPY } from '../../../budget/copy';
import { resolveInputAuthorityPresentation } from '../../../budget/inputAuthorityPanel';
import type { SufficiencySummary } from '../../../budget/budgetSimulationTypes';
import { SupervisoryStatusChip } from '../../trust/SupervisoryStatusChip/SupervisoryStatusChip';
import styles from './InputAuthorityPanel.module.css';

export interface InputAuthorityPanelProps {
  sufficiency: SufficiencySummary;
  channelCount: number;
  verifiedConversions: number;
  trustApiOperational: boolean;
}

export function InputAuthorityPanel({
  sufficiency,
  channelCount,
  verifiedConversions,
  trustApiOperational,
}: InputAuthorityPanelProps) {
  const presentation = resolveInputAuthorityPresentation(
    sufficiency,
    channelCount,
    verifiedConversions,
    trustApiOperational,
  );

  return (
    <section
      className={[styles.panel, styles[presentation.panelTone]].join(' ')}
      aria-label={BUDGET_SIMULATION_COPY.inputAuthority.title}
      role="status"
      aria-live="polite"
      data-input-authority-panel
      data-input-authority-state={sufficiency.state}
      data-budget-elevated-panel="true"
    >
      <div className={styles.headerRow}>
        <h3 className={styles.title}>{BUDGET_SIMULATION_COPY.inputAuthority.title}</h3>
        <SupervisoryStatusChip tone={presentation.chipTone} data-input-authority-tag>
          {presentation.statusLabel}
        </SupervisoryStatusChip>
      </div>

      <p className={styles.intro}>{presentation.intro}</p>

      <dl className={styles.details}>
        {presentation.facts.map((fact) => (
          <div key={fact.term}>
            <dt>{fact.term}</dt>
            <dd>{fact.detail}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
