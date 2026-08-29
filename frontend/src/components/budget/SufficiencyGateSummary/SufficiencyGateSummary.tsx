import { IconCheckmark, IconError, IconWarning } from '../../icons/StatusIcons';

import { BUDGET_SIMULATION_COPY } from '../../../budget/copy';

import type { SufficiencyGateRow, SufficiencySummary } from '../../../budget/budgetSimulationTypes';

import { SupervisoryStatusChip } from '../../trust/SupervisoryStatusChip/SupervisoryStatusChip';
import type { SupervisoryStatusTone } from '../../trust/SupervisoryStatusChip/SupervisoryStatusChip';

import shared from '../../../styles/shared.module.css';

import styles from './SufficiencyGateSummary.module.css';



export interface SufficiencyGateSummaryProps {

  summary: SufficiencySummary;

  /** Inset sub-panel inside input card — no independent elevation */

  variant?: 'elevated' | 'inset';

}



function GateIcon({ status }: { status: SufficiencyGateRow['status'] }) {
  if (status === 'passed' || status === 'available') {
    return <IconCheckmark className={styles.gateCheckmark} size={16} />;
  }

  if (status === 'failed') return <IconError aria-hidden="true" />;

  return <IconWarning aria-hidden="true" />;
}



function statusWord(status: SufficiencyGateRow['status']): string {

  if (status === 'passed') return BUDGET_SIMULATION_COPY.gates.passed;

  if (status === 'available') return BUDGET_SIMULATION_COPY.gates.available;

  if (status === 'failed') return BUDGET_SIMULATION_COPY.gates.failed;

  return '';

}



function statusLabel(state: SufficiencySummary['state']): string {

  switch (state) {

    case 'eligible':

      return BUDGET_SIMULATION_COPY.readiness.ready;

    case 'blocked':

      return BUDGET_SIMULATION_COPY.readiness.blocked;

    case 'partial':

      return BUDGET_SIMULATION_COPY.readiness.partial;

    case 'loading':

      return BUDGET_SIMULATION_COPY.readiness.loading;

    case 'error':

      return BUDGET_SIMULATION_COPY.readiness.error;

    default:

      return BUDGET_SIMULATION_COPY.readiness.empty;

  }

}



function readinessTone(state: SufficiencySummary['state']): SupervisoryStatusTone {
  if (state === 'eligible') return 'success';
  if (state === 'blocked' || state === 'error') return 'error';
  if (state === 'partial') return 'warning';
  return 'neutral';
}

export function SufficiencyGateSummary({ summary, variant = 'elevated' }: SufficiencyGateSummaryProps) {

  const statusClass =

    summary.state === 'eligible'

      ? styles.eligible

      : summary.state === 'blocked' || summary.state === 'error'

        ? styles.blocked

        : summary.state === 'partial'

          ? styles.partial

          : styles.neutral;



  const shellClass = variant === 'inset' ? styles.insetPanel : styles.panel;



  return (

    <section

      className={[shellClass, statusClass].join(' ')}

      aria-label={BUDGET_SIMULATION_COPY.readiness.title}

      role="status"

      aria-live="polite"

      data-sufficiency-gate-summary

      data-sufficiency-state={summary.state}

      data-budget-inset-panel={variant === 'inset' ? 'true' : undefined}

      data-budget-elevated-panel={variant === 'elevated' ? 'true' : undefined}

    >

      <div className={styles.headerRow}>

        <h3 className={styles.title}>

          <span className={shared.iconWithLabel}>

            {summary.state === 'eligible' ? <IconCheckmark className={styles.gateCheckmark} size={16} /> : null}

            {summary.state === 'blocked' ? <IconError aria-hidden="true" /> : null}

            {summary.state === 'partial' ? <IconWarning aria-hidden="true" /> : null}

            <span>{BUDGET_SIMULATION_COPY.readiness.title}</span>

          </span>

        </h3>

        {summary.state !== 'empty' ? (
          <SupervisoryStatusChip tone={readinessTone(summary.state)} data-readiness-tag>
            {statusLabel(summary.state)}
          </SupervisoryStatusChip>
        ) : null}

      </div>



      {summary.state === 'empty' ? (

        <p className={styles.emptyCopy}>{BUDGET_SIMULATION_COPY.readiness.empty}</p>

      ) : null}



      {summary.state === 'loading' ? (

        <p className={styles.loadingCopy}>{BUDGET_SIMULATION_COPY.readiness.loading}</p>

      ) : null}



      {summary.state === 'error' ? (

        <p className={styles.errorCopy} role="alert">

          {BUDGET_SIMULATION_COPY.readiness.error}

        </p>

      ) : null}



      {summary.rows.length > 0 ? (

        <ul className={styles.gateList}>

          {summary.rows.map((row) => (

            <li key={row.id} className={styles.gateRow} data-gate-id={row.id}>

              <span className={styles.gateLabelCell}>

                <span className={shared.iconWithLabel}>

                  <GateIcon status={row.status} />

                  <span className={styles.gateLabel}>{row.label}</span>

                </span>

              </span>

              <span className={styles.gateStatusCell}>{statusWord(row.status)}</span>

              <span className={styles.gateMetricCell}>{row.detail || '\u00A0'}</span>

            </li>

          ))}

        </ul>

      ) : null}

    </section>

  );

}


