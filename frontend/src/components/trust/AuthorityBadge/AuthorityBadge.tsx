import { useId, useState } from 'react';
import { IconShield } from '../../icons/StatusIcons';
import { ERROR_COPY } from '../../../lib/copy';
import type { AuthorityClass } from '../../../lib/types';
import { AUTHORITY_CLASSES } from '../../../lib/types';
import { trustChipClassNames, type TrustChipTone } from '../TrustChip/TrustChip';
import statusText from '../../../styles/trustStatusText.module.css';
import shared from '../../../styles/shared.module.css';
import styles from './AuthorityBadge.module.css';

export interface AuthorityBadgeProps {
  authority?: AuthorityClass | string;
  label?: string;
  tooltip?: string;
  state?: 'uninitialized' | 'loading' | 'populated' | 'error';
  tokenMissing?: boolean;
  showIcon?: boolean;
  shape?: 'default' | 'pill';
  size?: 'default' | 'table';
  appearance?: 'chip' | 'text';
}

const AUTHORITY_LABELS: Record<AuthorityClass, string> = {
  deterministic: 'Deterministic',
  probabilistic: 'Probabilistic',
  benchmark: 'Benchmark',
  prior: 'Prior',
  unavailable: 'Unavailable',
  suppressed: 'Suppressed',
};

const TABLE_AUTHORITY_LABELS: Record<AuthorityClass, string> = {
  deterministic: 'Deterministic',
  probabilistic: 'Probabilistic',
  benchmark: 'Benchmark',
  prior: 'Prior',
  unavailable: 'Unavailable',
  suppressed: 'Suppressed',
};

const TABLE_AUTHORITY_TEXT_LABELS: Record<AuthorityClass, string> = {
  deterministic: 'Deterministic',
  probabilistic: 'Probabilistic',
  benchmark: 'Benchmark',
  prior: 'Prior',
  unavailable: 'Unavailable',
  suppressed: 'Suppressed',
};

const AUTHORITY_TONE: Record<AuthorityClass, TrustChipTone> = {
  deterministic: 'deterministic',
  probabilistic: 'probabilistic',
  benchmark: 'benchmark',
  prior: 'neutral',
  unavailable: 'neutral',
  suppressed: 'neutral',
};

const AUTHORITY_TEXT_CLASS: Record<AuthorityClass, string> = {
  deterministic: statusText.labelSuccess,
  probabilistic: statusText.labelProbabilistic,
  benchmark: statusText.labelBenchmark,
  prior: statusText.labelNeutral,
  unavailable: statusText.labelNeutral,
  suppressed: statusText.labelNeutral,
};

export function AuthorityBadge({
  authority,
  label,
  tooltip,
  state = 'populated',
  tokenMissing,
  showIcon = false,
  shape = 'default',
  size = 'table',
  appearance = 'chip',
}: AuthorityBadgeProps) {
  const tooltipId = useId();
  const [showTooltip, setShowTooltip] = useState(false);

  if (tokenMissing) {
    return (
      <span className={shared.errorState} role="alert">
        {ERROR_COPY.tokenMissing('trust.deterministic')}
      </span>
    );
  }

  if (state === 'loading') {
    return <span className={styles.skeleton} aria-busy="true" aria-label="Loading authority" />;
  }

  if (state === 'uninitialized' || authority === undefined || authority === null || authority === '') {
    return (
      <span className={shared.errorState} role="alert">
        {ERROR_COPY.missingRequiredProp('authority')}
      </span>
    );
  }

  if (!AUTHORITY_CLASSES.includes(authority as AuthorityClass)) {
    return (
      <span className={[styles.badge, styles.error].join(' ')} role="alert">
        <span className={shared.iconWithLabel}>
          <IconErrorInline />
          <span>{ERROR_COPY.invalidAuthorityState}</span>
        </span>
        <span className={styles.diagnostic}>{ERROR_COPY.unknownEnum('authority', String(authority))}</span>
      </span>
    );
  }

  const resolved = authority as AuthorityClass;

  // Canonical chrome: the authority class label "Probabilistic" is always TrustChip —
  // never densified text, never a divergent size/appearance path.
  if (resolved === 'probabilistic') {
    const probabilisticLabel = label ?? AUTHORITY_LABELS.probabilistic;
    return (
      <span
        className={trustChipClassNames('probabilistic')}
        role="status"
        data-trust-chip
        data-authority-class="probabilistic"
        aria-label={`${probabilisticLabel}. Source authority: probabilistic`}
        title={tooltip ?? 'Source authority: probabilistic'}
      >
        {probabilisticLabel}
      </span>
    );
  }

  const displayLabel =
    size === 'table' && appearance === 'text'
      ? TABLE_AUTHORITY_TEXT_LABELS[resolved]
      : size === 'table'
        ? TABLE_AUTHORITY_LABELS[resolved]
        : (label ?? AUTHORITY_LABELS[resolved]);
  const tooltipText = tooltip ?? `Source authority: ${resolved}`;

  if (size === 'table') {
    if (appearance === 'text') {
      return (
        <span
          className={AUTHORITY_TEXT_CLASS[resolved]}
          data-status-text
          role="status"
          aria-label={`${displayLabel}. Source authority: ${resolved}`}
        >
          {displayLabel}
        </span>
      );
    }

    return (
      <span
        className={trustChipClassNames(AUTHORITY_TONE[resolved])}
        role="status"
        data-trust-chip
        data-authority-class={resolved}
        aria-label={`${displayLabel}. Source authority: ${resolved}`}
      >
        {displayLabel}
      </span>
    );
  }

  return (
    <button
      type="button"
      className={[styles.badge, styles[resolved], shape === 'pill' ? styles.pillShape : ''].filter(Boolean).join(' ')}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      onFocus={() => setShowTooltip(true)}
      onBlur={() => setShowTooltip(false)}
      aria-describedby={showTooltip ? tooltipId : undefined}
      aria-label={`${displayLabel}. Source authority: ${resolved}`}
    >
      <span className={shared.iconWithLabel}>
        {showIcon ? <IconShield aria-hidden="true" /> : null}
        <span className={styles.label}>{displayLabel}</span>
      </span>
      {showTooltip ? (
        <span id={tooltipId} className={styles.tooltip}>
          {tooltipText.includes('Source authority:') ? tooltipText : `Source authority: ${resolved}`}
        </span>
      ) : null}
    </button>
  );
}

function IconErrorInline() {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="7" fill="currentColor" opacity="0.15" />
      <path d="M5 5l6 6M11 5l-6 6" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
