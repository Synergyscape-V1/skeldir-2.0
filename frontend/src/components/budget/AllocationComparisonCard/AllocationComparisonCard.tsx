import { BUDGET_SIMULATION_COPY } from '../../../budget/copy';
import type { AllocationRow } from '../../../budget/budgetSimulationTypes';
import { AllocationComparisonPanel } from '../AllocationComparisonPanel/AllocationComparisonPanel';
import styles from './AllocationComparisonCard.module.css';

export interface AllocationComparisonCardProps {
  currentRows: AllocationRow[];
  simulatedRows: AllocationRow[];
  currentTotalMinor: bigint;
  simulatedTotalMinor: bigint;
  currencyCode: string;
}

export function AllocationComparisonCard({
  currentRows,
  simulatedRows,
  currentTotalMinor,
  simulatedTotalMinor,
  currencyCode,
}: AllocationComparisonCardProps) {
  return (
    <section
      className={styles.card}
      aria-label={BUDGET_SIMULATION_COPY.allocation.comparisonLabel}
      data-allocation-comparison-card
      data-budget-elevated-panel="true"
    >
      <div className={styles.grid}>
        <AllocationComparisonPanel
          embedded
          title={BUDGET_SIMULATION_COPY.allocation.current}
          rows={currentRows}
          totalMinor={currentTotalMinor}
          currencyCode={currencyCode}
        />
        <AllocationComparisonPanel
          embedded
          title={BUDGET_SIMULATION_COPY.allocation.simulated}
          rows={simulatedRows}
          totalMinor={simulatedTotalMinor}
          currencyCode={currencyCode}
        />
      </div>
    </section>
  );
}

