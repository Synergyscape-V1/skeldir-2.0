import { useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { getAuthState } from '../../../auth/sessionStore';
import { getDefaultBudgetSimulationDetailClient } from '../../../budget/budgetSimulationDetailClient';
import { BUDGET_DETAIL_COPY } from '../../../budget/copy';
import { COMMAND_CENTER_PRIORITY_ISSUES } from '../../../commandCenter/commandCenterPriorityFixtures';
import { COMMAND_CENTER_COPY } from '../../../commandCenter/copy';
import { parseTriageSearch } from '../../../commandCenter/triageHref';
import { beginTriageSession, getTriageQueueSnapshot } from '../../../commandCenter/triageQueueStore';
import { resolveIssueTitle, useTriageAdvance } from '../../../commandCenter/useTriageAdvance';
import { DetailReturnLink } from '../../../detail/DetailReturnLink';
import { DetailStateView } from '../../../detail/DetailStateView';
import { resolveParentContext } from '../../../detail/parentContext';
import { useDetailFetch } from '../../../detail/useDetailFetch';
import { BudgetProposalFlow } from '../../../actions/BudgetProposalFlow';
import { formatBpsAsPercentOneDecimal, formatMoneyMinorDisplay } from '../../../lib/money';
import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { Typography } from '../../layout/Typography/Typography';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import { DataUnavailablePanel } from '../../trust/DataUnavailablePanel/DataUnavailablePanel';
import { ConfidenceCell } from '../../ledger/ConfidenceCell/ConfidenceCell';
import { BenchmarkCell } from '../../ledger/BenchmarkCell/BenchmarkCell';
import { TriageContextHeader } from '../../triage/TriageContextHeader/TriageContextHeader';
import { COMMAND_CENTER_POLICY_CHIP_PROPS } from '../../../commandCenter/commandCenterChipProps';
import { BudgetSimulationDetailSummaryRow } from '../BudgetSimulationDetailSummaryRow/BudgetSimulationDetailSummaryRow';
import styles from './BudgetSimulationDetailPage.module.css';

function channelLabel(channel: string): string {
  return channel
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function BudgetSimulationDetailPage() {
  const { simulationId = '' } = useParams();
  const [searchParams] = useSearchParams();
  const focus = searchParams.get('focus');
  const triage = parseTriageSearch(searchParams);
  const { tenant } = getAuthState();
  const parentContext = useMemo(() => resolveParentContext('budget'), []);
  const [proposalSucceeded, setProposalSucceeded] = useState(false);

  const { kind, data, message, loadingPhase, reload } = useDetailFetch(
    (signal) =>
      getDefaultBudgetSimulationDetailClient().getBudgetSimulationDetail(
        tenant?.tenantId ?? '',
        simulationId,
        signal,
      ),
    [simulationId, tenant?.tenantId],
  );

  useEffect(() => {
    if (kind !== 'loaded' || focus !== 'policy') return;
    const panel = document.querySelector('[data-budget-policy-authority-section]');
    if (!(panel instanceof HTMLElement)) return;
    panel.setAttribute('data-budget-detail-focus-target', 'policy');
    if (typeof panel.scrollIntoView === 'function') {
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [kind, focus, data?.simulationId]);

  const triageActive = triage.isTriage;
  const triageIssueId = triage.isTriage ? triage.issueId : '';

  useEffect(() => {
    if (!triageActive) return;
    const snapshot = getTriageQueueSnapshot();
    if (!snapshot.sessionActive || snapshot.issues.length === 0) {
      beginTriageSession(COMMAND_CENTER_PRIORITY_ISSUES);
    }
  }, [triageActive, triageIssueId]);

  const issueTitle = triage.isTriage
    ? resolveIssueTitle(triage.issueId, COMMAND_CENTER_COPY.priorityIssues.metaBudgetTitle)
    : '';

  const { overlay } = useTriageAdvance({
    enabled: triage.isTriage,
    issueId: triage.isTriage ? triage.issueId : '',
    issueTitle,
    successSignal: proposalSucceeded,
  });

  if (kind !== 'loaded' || !data) {
    return (
      <PageSurface className={styles.page} data-budget-detail-page>
        {triage.isTriage ? (
          <TriageContextHeader
            issueIndex={triage.issueIndex}
            issueTotal={triage.issueTotal}
            title={issueTitle || 'Pending Certification'}
          />
        ) : (
          <DetailReturnLink surface="budget" />
        )}
        <DetailStateView
          kind={kind}
          message={message}
          loadingPhase={loadingPhase}
          parentContext={parentContext}
          onRetry={reload}
        />
      </PageSurface>
    );
  }

  const statusLabel = BUDGET_DETAIL_COPY.status[data.simulationStatus] ?? data.simulationStatus;

  return (
    <PageSurface
      className={styles.page}
      data-budget-detail-page
      data-budget-detail-loaded
      data-budget-triage-mode={triage.isTriage ? 'true' : 'false'}
    >
      <div className={styles.masthead} data-budget-detail-masthead>
        {triage.isTriage ? (
          <TriageContextHeader
            issueIndex={triage.issueIndex}
            issueTotal={triage.issueTotal}
            title={issueTitle || 'Pending Certification'}
          />
        ) : (
          <DetailReturnLink surface="budget" />
        )}

        <div className={styles.headerRow} data-budget-detail-header-row>
          <header className={styles.pageHeaderStack} data-budget-detail-header data-page-interface-header>
            <Typography variant="h1" className={styles.pageTitle}>
              {BUDGET_DETAIL_COPY.titlePrefix} {data.simulationId}
            </Typography>
            <p className={styles.pageSubtitle}>{BUDGET_DETAIL_COPY.subtitle}</p>
            <p className={styles.pageMetadata}>{BUDGET_DETAIL_COPY.metadataLine}</p>
          </header>
          <div className={styles.headerActionColumn}>
            <p className={styles.statusPill} data-simulation-status={data.simulationStatus}>
              {statusLabel}
            </p>
          </div>
        </div>
      </div>

      <BudgetSimulationDetailSummaryRow detail={data} />

      <div className={styles.panelGrid} data-budget-detail-panel-grid>
        <section className={styles.panel} id="budget-detail-assumptions" data-budget-detail-panel="assumptions">
          <h2 className={styles.panelTitle}>{BUDGET_DETAIL_COPY.sections.assumptions}</h2>
          <ul className={styles.list}>
            {data.inputAssumptions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className={styles.panelMeta}>
            Basis {formatMoneyMinorDisplay(data.verifiedRevenueBasisMinor, data.currencyCode)}
          </p>
        </section>

        <section
          className={styles.panel}
          id="budget-detail-confidence-detail"
          data-budget-detail-panel="confidence"
        >
          <h2 className={styles.panelTitle}>{BUDGET_DETAIL_COPY.sections.confidence}</h2>
          {data.confidence.status === 'unavailable' ? (
            <DataUnavailablePanel variant="sparse_data" reason={data.confidence.reason} />
          ) : (
            <ConfidenceCell confidence={data.confidence} />
          )}
        </section>

        <section className={styles.panel} data-budget-detail-panel="benchmark">
          <h2 className={styles.panelTitle}>{BUDGET_DETAIL_COPY.sections.benchmark}</h2>
          <BenchmarkCell benchmark={data.benchmark} />
        </section>

        <section
          className={styles.panel}
          id="budget-detail-policy-detail"
          data-budget-detail-panel="policy"
        >
          <h2 className={styles.panelTitle}>{BUDGET_DETAIL_COPY.sections.policy}</h2>
          <div className={styles.policyRow}>
            <PolicyAuthorityPill state={data.policyAuthority} {...COMMAND_CENTER_POLICY_CHIP_PROPS} />
          </div>
        </section>

        <section
          className={styles.panel}
          id="budget-detail-allocation"
          data-budget-detail-panel="allocation"
        >
          <h2 className={styles.panelTitle}>{BUDGET_DETAIL_COPY.sections.allocation}</h2>
          <ul className={styles.allocationList}>
            {data.projectedAllocation.map((row) => (
              <li key={row.channel} className={styles.allocationRow}>
                <span>{channelLabel(row.channel)}</span>
                <span className={styles.allocationValue}>{formatBpsAsPercentOneDecimal(row.shareBps)}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className={styles.panel} data-budget-detail-panel="risks">
          <h2 className={styles.panelTitle}>{BUDGET_DETAIL_COPY.sections.risks}</h2>
          <ul className={styles.list}>
            {data.riskCaveats.map((caveat) => (
              <li key={caveat}>{caveat}</li>
            ))}
          </ul>
        </section>

        <section className={styles.panel} data-budget-detail-panel="audit">
          <h2 className={styles.panelTitle}>{BUDGET_DETAIL_COPY.sections.audit}</h2>
          <p className={styles.auditRef}>{data.auditReference}</p>
        </section>
      </div>

      <div className={styles.proposalPanel} data-budget-detail-panel="proposal">
        <BudgetProposalFlow
          simulationId={data.simulationId}
          versionStamp={data.versionStamp}
          policyAuthority={data.policyAuthority}
          triageMode={triage.isTriage}
          onTriageSuccess={() => setProposalSucceeded(true)}
        />
      </div>
      {overlay}
    </PageSurface>
  );
}
