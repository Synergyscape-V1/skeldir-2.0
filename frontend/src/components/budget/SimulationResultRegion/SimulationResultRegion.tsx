import { IconWarning } from '../../icons/StatusIcons';

import { BUDGET_SIMULATION_COPY } from '../../../budget/copy';

import type { BudgetSimulationResultDTO } from '../../../budget/budgetSimulationTypes';

import { AllocationComparisonCard } from '../AllocationComparisonCard/AllocationComparisonCard';

import { ExpectedImpactPanel } from '../ExpectedImpactPanel/ExpectedImpactPanel';

import { SourceTrustEnvelopesTable } from '../SourceTrustEnvelopesTable/SourceTrustEnvelopesTable';

import shared from '../../../styles/shared.module.css';

import styles from './SimulationResultRegion.module.css';



export interface SimulationResultRegionProps {

  result: BudgetSimulationResultDTO;

  stale: boolean;

}



export function SimulationResultRegion({ result, stale }: SimulationResultRegionProps) {

  const totalMinor = result.simulatedAllocation.reduce((sum, row) => sum + row.amountMinor, 0n);

  const currentTotal = result.currentAllocation.reduce((sum, row) => sum + row.amountMinor, 0n);



  return (

    <section

      className={styles.region}

      aria-labelledby="budget-simulation-result-heading"

      data-simulation-result-region
    >

      <h2 id="budget-simulation-result-heading" className={styles.regionTitle} tabIndex={-1}>

        {BUDGET_SIMULATION_COPY.resultSectionLabel}

      </h2>



      {stale ? (

        <div className={styles.staleBanner} role="status" aria-live="polite" data-stale-banner>

          <span className={shared.iconWithLabel}>

            <IconWarning aria-hidden="true" />

            <span>{BUDGET_SIMULATION_COPY.staleBanner}</span>

          </span>

        </div>

      ) : null}



      <div className={styles.outputStack}>

        <AllocationComparisonCard

          currentRows={result.currentAllocation}

          simulatedRows={result.simulatedAllocation}

          currentTotalMinor={currentTotal}

          simulatedTotalMinor={totalMinor}

          currencyCode={result.currencyCode}

        />

        <ExpectedImpactPanel result={result} />

        <SourceTrustEnvelopesTable rows={result.sourceTrustEnvelopes} currencyCode={result.currencyCode} />

      </div>

    </section>

  );

}


