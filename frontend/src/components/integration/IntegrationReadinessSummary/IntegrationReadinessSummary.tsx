import { INTEGRATION_COPY } from '../../../integration/copy';
import { isCommerceReady, isClaimConnected } from '../../../integration/integrationClient';
import type { IntegrationSourceState } from '../../../integration/types';
import styles from './IntegrationReadinessSummary.module.css';

export interface IntegrationReadinessSummaryProps {
  integrations: IntegrationSourceState[];
  claimSkipped?: boolean;
}

export function IntegrationReadinessSummary({
  integrations,
  claimSkipped = false,
}: IntegrationReadinessSummaryProps) {
  const commerceReady = isCommerceReady(integrations);
  const claimConnected = isClaimConnected(integrations);

  return (
    <div className={styles.summary} data-readiness-summary aria-live="polite">
      <p>
        {commerceReady
          ? INTEGRATION_COPY.commerceReadySummary
          : INTEGRATION_COPY.commerceMissingSummary}
      </p>
      {claimSkipped ? <p>{INTEGRATION_COPY.claimSkippedSummary}</p> : null}
      {!claimSkipped && claimConnected ? <p>{INTEGRATION_COPY.claimReadySummary}</p> : null}
    </div>
  );
}
