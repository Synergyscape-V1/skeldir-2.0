import type { ExceptionQueueRowDTO } from '../../../ledger/types';
import { EXCEPTION_STATUS_LABELS } from '../../../exceptions/copy';
import statusText from '../../../styles/trustStatusText.module.css';
import { trustChipClassNames, type TrustChipTone } from '../../trust/TrustChip/TrustChip';

type ExceptionStatus = ExceptionQueueRowDTO['status'];

const STATUS_TONE: Record<ExceptionStatus, TrustChipTone> = {
  open: 'success',
  acknowledged: 'info',
  suppressed: 'neutral',
  resolved: 'success',
};

const TABLE_STATUS_LABELS: Record<ExceptionStatus, string> = {
  open: 'Open',
  acknowledged: 'Acknowledged',
  suppressed: 'Suppressed',
  resolved: 'Resolved',
};

const TABLE_STATUS_TEXT_LABELS: Record<ExceptionStatus, string> = {
  open: 'Open',
  acknowledged: 'Acknowledged',
  suppressed: 'Suppressed',
  resolved: 'Resolved',
};

const TONE_TEXT_CLASS: Record<TrustChipTone, string> = {
  success: statusText.labelSuccess,
  warning: statusText.labelWarning,
  error: statusText.labelError,
  info: statusText.labelInfo,
  neutral: statusText.labelNeutral,
  probabilistic: statusText.labelProbabilistic,
  benchmark: statusText.labelBenchmark,
  deterministic: statusText.labelSuccess,
};

type ExceptionBadgeOptions = {
  variant?: 'chip' | 'text';
  table?: boolean;
  compact?: boolean;
};

export function ExceptionStatusBadge({
  status,
  variant = 'chip',
}: { status: ExceptionStatus } & ExceptionBadgeOptions) {
  const tone = STATUS_TONE[status];
  const className = variant === 'text' ? TONE_TEXT_CLASS[tone] : trustChipClassNames(tone);
  const displayLabel = variant === 'text' ? TABLE_STATUS_TEXT_LABELS[status] : TABLE_STATUS_LABELS[status];

  return (
    <span
      className={className}
      {...(variant === 'text' ? { 'data-status-text': true } : { 'data-trust-chip': true })}
      data-exception-status={status}
      title={EXCEPTION_STATUS_LABELS[status]}
      role="status"
    >
      {displayLabel}
    </span>
  );
}
