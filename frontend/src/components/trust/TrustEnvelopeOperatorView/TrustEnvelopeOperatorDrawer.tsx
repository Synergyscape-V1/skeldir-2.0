import { useEffect, useRef, useState } from 'react';
import { getAuthState } from '../../../auth/sessionStore';
import type { TrustEnvelopeDetailDTO } from '../../../detail/types';
import { DetailStateView } from '../../../detail/DetailStateView';
import { getDefaultTrustEnvelopeDetailClient } from '../../../trustIndex/trustEnvelopeDetailClient';
import { Modal } from '../../layout/Modal/Modal';
import { Skeleton } from '../../layout/Skeleton/Skeleton';
import { ExportReportButton } from '../../../actions/ExportReportButton';
import { TrustEnvelopeOperatorContent } from './TrustEnvelopeOperatorContent';
import styles from './TrustEnvelopeOperatorDrawer.module.css';

export interface TrustEnvelopeOperatorDrawerProps {
  envelopeId: string;
  open: boolean;
  onClose: () => void;
  triggerRef?: React.RefObject<HTMLElement | null>;
}

export function TrustEnvelopeOperatorDrawer({
  envelopeId,
  open,
  onClose,
  triggerRef,
}: TrustEnvelopeOperatorDrawerProps) {
  const { tenant } = getAuthState();
  const [detail, setDetail] = useState<TrustEnvelopeDetailDTO | null>(null);
  const [kind, setKind] = useState<'loading' | 'loaded' | 'error'>('loading');
  const [message, setMessage] = useState<string>();
  const localTriggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open || !envelopeId || !tenant?.tenantId) return;
    let cancelled = false;
    setKind('loading');
    setDetail(null);
    void getDefaultTrustEnvelopeDetailClient()
      .getTrustEnvelopeDetail(tenant.tenantId, envelopeId)
      .then((outcome) => {
        if (cancelled) return;
        if (outcome.kind === 'loaded') {
          setDetail(outcome.detail);
          setKind('loaded');
          return;
        }
        setKind('error');
        setMessage(outcome.message);
      });
    return () => {
      cancelled = true;
    };
  }, [open, envelopeId, tenant?.tenantId]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      triggerRef={triggerRef ?? localTriggerRef}
      title="Trust record"
      size="wide"
      closeOnBackdropClick
    >
      {kind === 'loading' ? <Skeleton rows={6} variant="text" /> : null}
      {kind === 'loaded' && detail ? (
        <div
          className={styles.overlayBody}
          data-claim-trust-envelope-drawer
          data-trust-envelope-operator-drawer
          data-trust-envelope-operator-overlay
        >
          <div className={styles.actions}>
            <ExportReportButton
              envelopeId={detail.envelopeId}
              versionStamp={detail.versionStamp}
              policyAuthority={detail.policyAuthority.state}
              layout="inline"
            />
          </div>
          <TrustEnvelopeOperatorContent detail={detail} />
        </div>
      ) : null}
      {kind === 'error' ? (
        <div data-claim-trust-envelope-drawer data-trust-envelope-operator-overlay>
          <DetailStateView kind="unavailable" message={message ?? 'Trust record unavailable.'} />
        </div>
      ) : null}
    </Modal>
  );
}
