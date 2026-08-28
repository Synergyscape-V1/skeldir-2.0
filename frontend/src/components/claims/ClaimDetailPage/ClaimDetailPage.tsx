import { useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { getAuthState } from '../../../auth/sessionStore';
import { getDefaultClaimDetailClient } from '../../../claims/claimDetailClient';
import { resolveClaimExecutiveVerdict } from '../../../claims/claimDetailDisplay';
import { COMMAND_CENTER_PRIORITY_ISSUES } from '../../../commandCenter/commandCenterPriorityFixtures';
import { COMMAND_CENTER_COPY } from '../../../commandCenter/copy';
import { parseTriageSearch } from '../../../commandCenter/triageHref';
import { beginTriageSession, getTriageQueueSnapshot } from '../../../commandCenter/triageQueueStore';
import { resolveIssueTitle, useTriageAdvance } from '../../../commandCenter/useTriageAdvance';
import { DetailStateView } from '../../../detail/DetailStateView';
import { resolveParentContext } from '../../../detail/parentContext';
import { useDetailFetch } from '../../../detail/useDetailFetch';
import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { TriageContextHeader } from '../../triage/TriageContextHeader/TriageContextHeader';
import shared from '../../../styles/shared.module.css';
import { AttributionBreakdownPanel } from './AttributionBreakdownPanel';
import { ClaimDetailEventsPanel } from './ClaimDetailEventsPanel';
import { ClaimDetailFinancialSummary } from './ClaimDetailFinancialSummary';
import { ClaimDetailUnverifiedPanel } from './ClaimDetailUnverifiedPanel';
import { ClaimDetailHeader } from './ClaimDetailHeader';
import styles from './ClaimDetailPage.module.css';

export function ClaimDetailPage() {
  const { claimId = '' } = useParams();
  const [searchParams] = useSearchParams();
  const triage = parseTriageSearch(searchParams);
  const { tenant } = getAuthState();
  const [reviewed, setReviewed] = useState(false);

  const { kind, data, message, loadingPhase, reload } = useDetailFetch(
    (signal) => getDefaultClaimDetailClient().getClaimDetail(tenant?.tenantId ?? '', claimId, signal),
    [claimId, tenant?.tenantId],
  );

  const parentContext = useMemo(() => resolveParentContext('claims'), []);

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
    ? resolveIssueTitle(triage.issueId, 'Claim review')
    : '';

  const { overlay } = useTriageAdvance({
    enabled: triage.isTriage,
    issueId: triage.isTriage ? triage.issueId : '',
    issueTitle,
    successSignal: reviewed,
  });

  const triageChrome = triage.isTriage ? (
    <TriageContextHeader
      issueIndex={triage.issueIndex}
      issueTotal={triage.issueTotal}
      title={issueTitle || 'Claim review'}
    />
  ) : null;

  const triageAdvanceControl = triage.isTriage ? (
    <div data-claim-triage-advance className={styles.triageAdvance}>
      <button
        type="button"
        className={shared.focusVisible}
        data-claim-triage-advance-button
        onClick={() => setReviewed(true)}
        disabled={reviewed}
      >
        {COMMAND_CENTER_COPY.triage.markReviewedAndAdvance}
      </button>
    </div>
  ) : null;

  if (kind !== 'loaded' || !data) {
    return (
      <PageSurface data-claim-detail-page>
        {triageChrome}
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

  const verdict = resolveClaimExecutiveVerdict(data);

  if (verdict === 'unverified') {
    return (
      <PageSurface
        data-claim-detail-page
        data-claim-detail-loaded
        data-claim-detail-mode="unverified"
        data-claim-triage-mode={triage.isTriage ? 'true' : 'false'}
      >
        {triageChrome}
        <ClaimDetailHeader data={data} />
        <ClaimDetailUnverifiedPanel
          claimId={data.claimId}
          claimSource={data.claimSource}
          claimRef={data.claimRef}
        />
        {triageAdvanceControl}
        {overlay}
      </PageSurface>
    );
  }

  return (
    <PageSurface
      data-claim-detail-page
      data-claim-detail-loaded
      data-claim-detail-mode="executive"
      className={styles.page}
      data-claim-aesthetic="overview-tile"
      data-claim-triage-mode={triage.isTriage ? 'true' : 'false'}
    >
      {triageChrome}
      <ClaimDetailHeader data={data} />
      <ClaimDetailFinancialSummary data={data} claimId={data.claimId} />
      <AttributionBreakdownPanel
        claimSource={data.claimSource}
        claimedRevenueMinor={data.claimedRevenueMinor}
        currencyCode={data.currencyCode}
        defaultModel={data.defaultAttributionModel}
        paidAttribution={data.paidAttribution}
        journeyOrigins={data.journeyOrigins}
      />
      <ClaimDetailEventsPanel events={data.claimEvents} currencyCode={data.currencyCode} />
      {triageAdvanceControl}
      {overlay}
    </PageSurface>
  );
}
