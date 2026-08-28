import type { DiagnosticIssueKind } from '../../../operationalAudit/types';
import { TrustChip, type TrustChipTone } from '../../trust/TrustChip/TrustChip';

const KIND_CONFIG: Record<DiagnosticIssueKind, { label: string; tone: TrustChipTone }> = {
  task_failure: { label: 'Task failure', tone: 'error' },
  integration_degradation: { label: 'Integration', tone: 'warning' },
  confidence_delayed: { label: 'Confidence delayed', tone: 'info' },
  trust_api_paused: { label: 'Trust API paused', tone: 'error' },
  unknown: { label: 'Unknown', tone: 'neutral' },
};

export interface OperationalIssueStatusBadgeProps {
  kind: DiagnosticIssueKind;
}

export function OperationalIssueStatusBadge({ kind }: OperationalIssueStatusBadgeProps) {
  const config = KIND_CONFIG[kind] ?? KIND_CONFIG.unknown;
  return (
    <TrustChip tone={config.tone} data-operational-issue-badge title={config.label}>
      {config.label}
    </TrustChip>
  );
}
