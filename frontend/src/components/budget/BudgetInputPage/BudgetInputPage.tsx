import { useEffect } from 'react';

import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { TimedLoadingPanel } from '../../../lib/loading';

import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';

import { Toast } from '../../layout/Toast/Toast';

import { PermissionDeniedPanel } from '../../governance/PermissionDeniedPanel/PermissionDeniedPanel';

import { BUDGET_SIMULATION_COPY } from '../../../budget/copy';

import { BUDGET_SUFFICIENCY_THRESHOLDS } from '../../../budget/budgetFixtures';

import { useBudgetSimulationPage } from '../../../budget/useBudgetSimulationPage';

import { BudgetBlockedSparseDataPanel } from '../BudgetBlockedSparseDataPanel/BudgetBlockedSparseDataPanel';

import { BudgetSimulationInputCard } from '../BudgetSimulationInputCard/BudgetSimulationInputCard';

import { BudgetSimulationPageHeader } from '../BudgetSimulationPageHeader/BudgetSimulationPageHeader';

import { BudgetSimulationRightColumn } from '../BudgetSimulationRightColumn/BudgetSimulationRightColumn';

import { SimulationResultRegion } from '../SimulationResultRegion/SimulationResultRegion';

import shared from '../../../styles/shared.module.css';

import styles from './BudgetInputPage.module.css';



export function BudgetInputPage() {

  const {

    pagePhase,

    form,

    patchForm,

    sufficiency,

    generatePhase,

    submitPhase,

    result,

    stale,

    blockedMessage,

    errorMessage,

    toast,

    inputsLocked,

    longGenerateLoading,

    generateSimulation,

    submitProposal,

    dismissToast,

    canGenerate,

    canSubmit,

  } = useBudgetSimulationPage();



  useEffect(() => {

    if (pagePhase === 'ready') {

      document.getElementById('budget-simulation-title')?.focus();

    }

  }, [pagePhase]);



  useEffect(() => {

    if (!result) return;

    const heading = document.getElementById('budget-simulation-result-heading');

    if (heading && typeof heading.scrollIntoView === 'function') {

      heading.scrollIntoView({ behavior: 'smooth', block: 'start' });

    }

    heading?.focus();

  }, [result]);



  if (pagePhase === 'permission_denied') {

    return (

      <PageSurface data-budget-page>

        <PermissionDeniedPanel />

      </PageSurface>

    );

  }

  if (pagePhase === 'loading') {
    return (
      <PageSurface className={styles.page} data-budget-page data-budget-state="loading">
        <BudgetSimulationPageHeader />
        <TimedLoadingPanel active skeletonRows={6} skeletonVariant="block" />
      </PageSurface>
    );
  }



  const inputsDisabled = inputsLocked || pagePhase !== 'ready';

  const generateLoading = generatePhase === 'loading';



  return (

    <PageSurface className={styles.page} data-budget-page data-budget-simulation-page>

      <BudgetSimulationPageHeader />



      {pagePhase === 'trust_api_error' && errorMessage ? (

        <ErrorBanner message={errorMessage} />

      ) : null}



      {sufficiency.state === 'blocked' ? (

        <BudgetBlockedSparseDataPanel

          channelsAvailable={form.channelIds.length}

          verifiedConversionsAvailable={BUDGET_SUFFICIENCY_THRESHOLDS.fixtureVerifiedConversions}

        />

      ) : blockedMessage ? (

        <div role="status" className={styles.blockedInline}>

          {blockedMessage}

        </div>

      ) : null}



      <div data-page-content-rail>
      <div className={styles.pageGrid}>

        <div className={styles.mainColumn}>

          <div className={styles.inputStack}>

            <BudgetSimulationInputCard

              form={form}

              sufficiency={sufficiency}

              disabled={inputsDisabled}

              onPatch={patchForm}

            />

            <button

              type="button"

              className={[styles.generateButton, shared.focusVisible].join(' ')}

              disabled={inputsDisabled || !canGenerate || generateLoading}

              aria-busy={generateLoading}

              data-generate-simulation-button

              onClick={() => void generateSimulation()}

            >

              {generateLoading

                ? longGenerateLoading

                  ? BUDGET_SIMULATION_COPY.generate.loadingProgress

                  : BUDGET_SIMULATION_COPY.generate.loading

                : BUDGET_SIMULATION_COPY.generate.label}

            </button>

          </div>

          {result ? <SimulationResultRegion result={result} stale={stale} /> : null}

        </div>



        <BudgetSimulationRightColumn

          sufficiency={sufficiency}

          channelCount={form.channelIds.length}

          verifiedConversions={BUDGET_SUFFICIENCY_THRESHOLDS.fixtureVerifiedConversions}

          trustApiOperational={pagePhase === 'ready'}

          result={result}

          canSubmit={canSubmit}

          submitLoading={submitPhase === 'loading'}

          stale={stale}

          onSubmit={() => void submitProposal()}

        />

      </div>
      </div>



      {toast ? (

        <Toast

          severity={toast.severity}

          message={toast.message}

          open

          onDismiss={dismissToast}

          placement="desktop"

        />

      ) : null}

    </PageSurface>

  );

}


