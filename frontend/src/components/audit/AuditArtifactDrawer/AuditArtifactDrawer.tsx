import { useMemo, useRef } from 'react';
import { Drawer } from '../../layout/Drawer/Drawer';
import { OPERATIONAL_AUDIT_COPY } from '../../../operationalAudit/copy';
import { useAuditArtifact } from '../../../operationalAudit/useOperationalAudit';
import {
  assessForensicChainIntegrity,
  findAdjacentForensicEvents,
} from '../../../operationalAudit/forensicChainIntegrity';
import type { AuditEvent } from '../../../operationalAudit/types';
import { AuditForensicChainPanel } from '../AuditForensicChainPanel/AuditForensicChainPanel';
import { AuditArtifactUnavailablePanel } from '../AuditArtifactUnavailablePanel/AuditArtifactUnavailablePanel';
import { AuditArtifactHashPanel } from '../AuditArtifactHashPanel/AuditArtifactHashPanel';
import { AuditArtifactJsonPreview } from '../AuditArtifactJsonPreview/AuditArtifactJsonPreview';
import { AuditTechnicalDetailsSections } from '../AuditTechnicalDetailsSections/AuditTechnicalDetailsSections';

export interface AuditArtifactDrawerProps {
  eventId: string | null;
  open: boolean;
  onClose: () => void;
  triggerRef?: React.RefObject<HTMLElement | null>;
  timelineEvents?: AuditEvent[];
  variant?: 'inspector' | 'technical';
}

export function AuditArtifactDrawer({
  eventId,
  open,
  onClose,
  triggerRef,
  timelineEvents = [],
  variant = 'inspector',
}: AuditArtifactDrawerProps) {
  const fallbackTrigger = useRef<HTMLElement | null>(null);
  const {
    artifact,
    loading,
    unavailable,
    corrupted,
    invalidSignature,
    accessDenied,
  } = useAuditArtifact(open ? eventId : null);

  const chainAssessment = useMemo(() => {
    if (!eventId) return { verdict: 'unavailable' as const };
    const { previous } = findAdjacentForensicEvents(timelineEvents, eventId);
    return assessForensicChainIntegrity(artifact, previous);
  }, [artifact, eventId, timelineEvents]);

  if (!eventId && open) {
    return (
      <div role="alert" data-drawer-without-selection>
        Drawer requires a selected audit row.
      </div>
    );
  }

  const drawerState = loading ? 'loading' : 'open';

  return (
    <Drawer
      open={open && Boolean(eventId)}
      onClose={onClose}
      triggerRef={triggerRef ?? fallbackTrigger}
      title={
        variant === 'technical'
          ? OPERATIONAL_AUDIT_COPY.forensicTechnicalDrawerTitle
          : OPERATIONAL_AUDIT_COPY.forensicDrawerTitle
      }
      state={drawerState}
      progressCopy={loading ? 'Loading forensic evidence…' : undefined}
    >
      {accessDenied ? <AuditArtifactUnavailablePanel variant="access_denied" /> : null}
      {unavailable ? (
        <AuditArtifactUnavailablePanel variant="unavailable" reason={artifact?.unavailableReason} />
      ) : null}
      {corrupted ? <AuditArtifactUnavailablePanel variant="corrupted" /> : null}
      {invalidSignature ? (
        <AuditArtifactUnavailablePanel variant="invalid_signature" />
      ) : null}
      {!accessDenied && !unavailable && !corrupted && !invalidSignature ? (
        <>
          <AuditForensicChainPanel assessment={chainAssessment} />
          <AuditTechnicalDetailsSections artifact={artifact} />
          <AuditArtifactHashPanel artifact={artifact} />
          <AuditArtifactJsonPreview
            jsonPreview={artifact?.metadataJson ?? artifact?.jsonPreview}
            title={OPERATIONAL_AUDIT_COPY.forensicMetadataTitle}
          />
        </>
      ) : null}
    </Drawer>
  );
}
