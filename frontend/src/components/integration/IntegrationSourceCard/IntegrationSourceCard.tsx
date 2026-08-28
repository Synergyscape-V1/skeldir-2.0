import { useRef, useState } from 'react';
import { Card } from '../../layout/Card/Card';
import { Typography } from '../../layout/Typography/Typography';
import { ChannelLogo } from '../../commandCenter/ChannelLogo/ChannelLogo';
import { INTEGRATION_COPY, providerLabel } from '../../../integration/copy';
import type { IntegrationProvider, IntegrationSourceState } from '../../../integration/types';
import { IntegrationActionButton } from '../IntegrationActionButton/IntegrationActionButton';
import { IntegrationErrorState } from '../IntegrationErrorState/IntegrationErrorState';
import { IntegrationRepairAction } from '../IntegrationRepairAction/IntegrationRepairAction';
import { IntegrationStatusBadge } from '../IntegrationStatusBadge/IntegrationStatusBadge';
import styles from './IntegrationSourceCard.module.css';

export interface IntegrationSourceCardProps {
  state: IntegrationSourceState;
  onConnect: (provider: IntegrationProvider) => Promise<void>;
  onRepair: (provider: IntegrationProvider) => Promise<void>;
  authorityCopy: string;
  cardClassName?: string;
  showLastEvent?: boolean;
  showLastClaim?: boolean;
  showVerification?: boolean;
  showReconciliation?: boolean;
}

function formatTimestamp(value?: string | null): string {
  if (!value) return INTEGRATION_COPY.lastEventUnavailable;
  try {
    return new Date(value).toLocaleString();
  } catch {
    return INTEGRATION_COPY.lastEventUnavailable;
  }
}

export function IntegrationSourceCard({
  state,
  onConnect,
  onRepair,
  authorityCopy,
  cardClassName,
  showLastEvent = false,
  showLastClaim = false,
  showVerification = false,
  showReconciliation = false,
}: IntegrationSourceCardProps) {
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | undefined>();
  const submitLock = useRef(false);

  const isUnknown = state.status === 'unknown_status';
  const needsRepair =
    state.status === 'repair_required' ||
    state.status === 'connection_failed' ||
    state.status === 'verification_failed' ||
    state.status === 'network_error';
  const canConnect = state.status === 'not_connected';
  const isConnecting = state.status === 'connecting' || state.status === 'repair_pending';

  async function runAction(action: 'connect' | 'repair') {
    if (submitLock.current) return;
    submitLock.current = true;
    setActionLoading(true);
    setActionError(undefined);
    try {
      if (action === 'connect') await onConnect(state.provider);
      else await onRepair(state.provider);
    } catch {
      setActionError(INTEGRATION_COPY.actionFailed);
    } finally {
      setActionLoading(false);
      submitLock.current = false;
    }
  }

  return (
    <Card
      title={undefined}
      state="populated"
      className={[styles.sourceCard, cardClassName ?? ''].filter(Boolean).join(' ')}
      data-integration-provider={state.provider}
      data-integration-kind={state.kind}
    >
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <div className={styles.identity}>
            <ChannelLogo claimSource={state.provider} />
            <Typography variant="h3" className={styles.title}>
              {providerLabel(state.provider)}
            </Typography>
          </div>
          <IntegrationStatusBadge status={state.status} />
        </div>
        <p className={styles.authorityCopy}>{authorityCopy}</p>
      </div>

      {isUnknown ? (
        <p className={styles.unknownError} role="alert">
          {INTEGRATION_COPY.unknownStatusError}
        </p>
      ) : null}

      <div className={styles.metaGrid}>
        {showLastEvent ? (
          <div className={styles.metaRow}>
            <span className={styles.metaLabel}>{INTEGRATION_COPY.lastEvent}</span>
            <span className={styles.metaValue}>
              {state.lastEventAt ? formatTimestamp(state.lastEventAt) : INTEGRATION_COPY.lastEventUnavailable}
            </span>
          </div>
        ) : null}
        {showLastClaim ? (
          <div className={styles.metaRow}>
            <span className={styles.metaLabel}>{INTEGRATION_COPY.lastClaim}</span>
            <span className={styles.metaValue}>
              {state.lastClaimAt ? formatTimestamp(state.lastClaimAt) : INTEGRATION_COPY.lastClaimUnavailable}
            </span>
          </div>
        ) : null}
        {showVerification && state.verificationLabel ? (
          <div className={styles.metaRow}>
            <span className={styles.metaLabel}>{INTEGRATION_COPY.verificationStatus}</span>
            <span className={styles.metaValue}>{state.verificationLabel}</span>
          </div>
        ) : null}
        {showReconciliation && state.reconciliationLabel ? (
          <div className={styles.metaRow}>
            <span className={styles.metaLabel}>{INTEGRATION_COPY.reconciliationReadiness}</span>
            <span className={styles.metaValue}>{state.reconciliationLabel}</span>
          </div>
        ) : null}
      </div>

      {state.errorMessage ? <IntegrationErrorState message={state.errorMessage} /> : null}
      {actionError ? <IntegrationErrorState message={actionError} /> : null}

      <div className={styles.actions}>
        {canConnect ? (
          <IntegrationActionButton
            action="connect"
            loading={actionLoading || isConnecting}
            onClick={() => void runAction('connect')}
          />
        ) : null}
        {needsRepair ? (
          <IntegrationRepairAction
            loading={actionLoading || isConnecting}
            onRepair={() => void runAction('repair')}
          />
        ) : null}
      </div>
    </Card>
  );
}
