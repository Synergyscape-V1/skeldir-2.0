import { PolicyAuthorityCard } from '../PolicyAuthorityCard/PolicyAuthorityCard';
import { AuditArtifactStatusCard } from '../AuditArtifactStatusCard/AuditArtifactStatusCard';
import { InputAuthorityPanel } from '../InputAuthorityPanel/InputAuthorityPanel';
import { BUDGET_SIMULATION_COPY } from '../../../budget/copy';
import type { BudgetSimulationResultDTO, SufficiencySummary } from '../../../budget/budgetSimulationTypes';
import shared from '../../../styles/shared.module.css';
import styles from './BudgetSimulationRightColumn.module.css';

export interface BudgetSimulationRightColumnProps {
  sufficiency: SufficiencySummary;
  channelCount: number;
  verifiedConversions: number;
  trustApiOperational: boolean;
  result: BudgetSimulationResultDTO | null;
  canSubmit: boolean;
  submitLoading: boolean;
  stale: boolean;
  onSubmit: () => void;
}

export function BudgetSimulationRightColumn({
  sufficiency,
  channelCount,
  verifiedConversions,
  trustApiOperational,
  result,
  canSubmit,
  submitLoading,
  stale,
  onSubmit,
}: BudgetSimulationRightColumnProps) {
  return (
    <aside className={styles.column} aria-label="Authority and submission" data-budget-right-column>
      <InputAuthorityPanel
        sufficiency={sufficiency}
        channelCount={channelCount}
        verifiedConversions={verifiedConversions}
        trustApiOperational={trustApiOperational}
      />

      {result ? (
        <>
          <PolicyAuthorityCard policyAuthority={result.policyAuthority} />
          <AuditArtifactStatusCard
            status={result.auditArtifactStatus}
            auditReference={result.auditReference}
          />
          <button
            type="button"
            className={[styles.submitButton, shared.focusVisible].join(' ')}
            disabled={!canSubmit || submitLoading || stale}
            aria-busy={submitLoading}
            data-submit-proposal-button
            onClick={onSubmit}
          >
            {submitLoading
              ? BUDGET_SIMULATION_COPY.submit.loading
              : BUDGET_SIMULATION_COPY.submit.label}
          </button>
          <p className={styles.submitCaption}>{BUDGET_SIMULATION_COPY.submit.caption}</p>
        </>
      ) : null}
    </aside>
  );
}
