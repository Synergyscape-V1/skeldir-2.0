import React from 'react';
import { AlertTriangle, Check, ShieldAlert } from 'lucide-react';

type PillKind = 'green' | 'teal' | 'amber' | 'red' | 'blue' | 'slate';

const PILL_SHADOW = '0 1px 2px rgba(15,23,42,0.08)';

function pillStyle(kind: PillKind): React.CSSProperties {
  const tokens: Record<PillKind, { fg: string; bg: string; border: string; dot: string }> = {
    green: { fg: '#16A34A', bg: 'rgba(22,163,74,0.14)', border: 'rgba(22,163,74,0.28)', dot: '#16A34A' },
    teal: { fg: '#0D9488', bg: 'rgba(20,184,166,0.14)', border: 'rgba(20,184,166,0.28)', dot: '#14B8A6' },
    amber: { fg: '#B45309', bg: 'rgba(245,158,11,0.14)', border: 'rgba(245,158,11,0.30)', dot: '#F59E0B' },
    red: { fg: '#DC2626', bg: 'rgba(239,68,68,0.14)', border: 'rgba(239,68,68,0.28)', dot: '#EF4444' },
    blue: { fg: '#2563EB', bg: 'rgba(59,130,246,0.14)', border: 'rgba(59,130,246,0.28)', dot: '#3B82F6' },
    slate: { fg: '#475569', bg: 'rgba(148,163,184,0.18)', border: 'rgba(148,163,184,0.32)', dot: '#64748B' },
  };
  const t = tokens[kind];
  return {
    color: t.fg,
    // Make pill fill completely see-through; keep only border/text.
    backgroundColor: 'transparent',
    border: `1px solid ${t.border}`,
    boxShadow: 'none',
    backdropFilter: 'none',
    WebkitBackdropFilter: 'none',
  };
}

export function AttributionMethodBadge({ method = 'bayesian', converged = true, size = 'md' }: { method?: string; converged?: boolean; size?: 'sm' | 'md' }) {
  const sizeStyle = size === 'sm'
    ? { fontSize: '10px', padding: '2px 9px', borderRadius: '9999px' }
    : { fontSize: '11px', padding: '3px 10px', borderRadius: '9999px' };

  if (method === 'bayesian') {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: '3px', fontWeight: 600,
        ...(converged ? pillStyle('teal') : pillStyle('amber')),
        ...sizeStyle,
      }}>
        Bayesian {converged ? '\u2713' : '\u25CC'}
      </span>
    );
  }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', fontWeight: 600,
      ...pillStyle('slate'),
      ...sizeStyle,
    }}>
      {method === 'deterministic_fallback' ? 'Deterministic (fallback)' : method.replace('_', '-')}
    </span>
  );
}

/**
 * Revenue verification pill — verified uses plain `Check`; partial / unverified are text-only (no shield icons).
 * `title` / tooltip: source + last sync when provided.
 */
export function VerificationBadge({
  status = 'verified',
  source = 'Stripe',
  lastSyncLabel,
  compact = false,
}: {
  status?: string;
  source?: string;
  /** e.g. "4 min ago" — included in native tooltip */
  lastSyncLabel?: string;
  /** tighter padding for table cells */
  compact?: boolean;
}) {
  const tooltip = [source && status === 'verified' ? `Verified via ${source}` : null, lastSyncLabel ? `Last sync: ${lastSyncLabel}` : null]
    .filter(Boolean)
    .join(' · ');

  if (status === 'verified') {
    const label = source === 'Verified' || source === 'Stripe' ? 'Verified' : source;
    return (
      <span
        title={tooltip || undefined}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: compact ? 3 : 4,
          fontSize: compact ? '10px' : '11px',
          fontWeight: 600,
          padding: compact ? '2px 8px' : '3px 10px',
          borderRadius: '9999px',
          color: '#059669',
          backgroundColor: 'rgba(5, 150, 105, 0.12)',
          border: '1px solid rgba(5, 150, 105, 0.28)',
        }}
      >
        <Check size={compact ? 12 : 14} strokeWidth={2} aria-hidden />
        {label}
      </span>
    );
  }
  if (status === 'partial') {
    const partialTip = [source ? `Sources: ${source}` : null, lastSyncLabel ? `Last sync: ${lastSyncLabel}` : null]
      .filter(Boolean)
      .join(' · ');
    return (
      <span
        title={partialTip || 'Partially verified revenue'}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: compact ? 3 : 4,
          fontSize: compact ? '10px' : '11px',
          fontWeight: 600,
          padding: compact ? '2px 8px' : '3px 10px',
          borderRadius: '9999px',
          color: '#B45309',
          backgroundColor: 'rgba(245, 158, 11, 0.14)',
          border: '1px solid rgba(245, 158, 11, 0.35)',
        }}
      >
        Partially verified
      </span>
    );
  }
  if (status === 'unverified') {
    const unverTip = [lastSyncLabel, source && source !== '—' ? `Source: ${source}` : null]
      .filter(Boolean)
      .join(' · ');
    return (
      <span
        title={unverTip || 'Unverified revenue'}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: compact ? 3 : 4,
          fontSize: compact ? '10px' : '11px',
          fontWeight: 600,
          padding: compact ? '2px 8px' : '3px 10px',
          borderRadius: '9999px',
          color: '#64748B',
          backgroundColor: 'rgba(100, 116, 139, 0.12)',
          border: '1px solid rgba(100, 116, 139, 0.28)',
        }}
      >
        Unverified
      </span>
    );
  }

  const config: Record<string, { text: string; kind: PillKind }> = {
    verified: { text: source ? `\u2713 ${source}` : '\u2713 Verified', kind: 'green' },
    partial: { text: '\u26A0 Partial', kind: 'amber' },
    unverified: { text: '\u2715 Unverified', kind: 'red' },
  };
  const c = config[status] || config.verified;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '2px',
      fontSize: '9px', fontWeight: 600, padding: '1px 7px', borderRadius: '9999px',
      ...pillStyle(c.kind),
    }}>
      {c.text}
    </span>
  );
}

export function BucketBadge({
  bucket = 'narrow',
  size = 'md',
  title,
}: {
  bucket?: string;
  size?: 'sm' | 'md';
  /** Action implication — shown on hover (native tooltip). */
  title?: string;
}) {
  const config: Record<string, { label: string; fg: string; bg: string; border: string }> = {
    narrow: {
      label: 'Narrow',
      fg: '#15803d',
      bg: 'rgba(22, 163, 74, 0.14)',
      border: 'rgba(22, 163, 74, 0.35)',
    },
    medium: {
      label: 'Medium',
      fg: '#B45309',
      bg: 'rgba(245, 158, 11, 0.16)',
      border: 'rgba(245, 158, 11, 0.38)',
    },
    wide: {
      label: 'Wide',
      fg: '#B91C1C',
      bg: 'rgba(239, 68, 68, 0.14)',
      border: 'rgba(239, 68, 68, 0.35)',
    },
  };
  const c = config[bucket] || {
    label: bucket,
    fg: '#475569',
    bg: 'rgba(148, 163, 184, 0.16)',
    border: 'rgba(148, 163, 184, 0.35)',
  };
  const fontSize = size === 'sm' ? '10px' : '11px';
  const padding = size === 'sm' ? '4px 8px' : '4px 10px';
  return (
    <span
      title={title}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        fontWeight: 600,
        fontSize,
        padding,
        borderRadius: '9999px',
        color: c.fg,
        backgroundColor: c.bg,
        border: `1px solid ${c.border}`,
      }}
    >
      {c.label}
    </span>
  );
}

export type IntegrityScoreVariant = 'verified' | 'caution' | 'critical';

export function integrityStateFromScore(score: number): {
  label: string;
  threshold: string;
  variant: IntegrityScoreVariant;
} {
  if (score >= 70) {
    return { label: 'Good', threshold: 'Score ≥ 70', variant: 'verified' };
  }
  if (score >= 50) {
    return { label: 'Needs Review', threshold: 'Score < 70', variant: 'caution' };
  }
  return { label: 'Critical', threshold: 'Score < 50', variant: 'critical' };
}

/** Good (≥70): same green checkmark iteration as Data Freshness “fresh”. */
export function IntegrityIcon({ variant }: { variant: IntegrityScoreVariant }) {
  if (variant === 'verified') return <Check size={16} strokeWidth={2} aria-hidden />;
  if (variant === 'caution') return <AlertTriangle size={16} strokeWidth={2} aria-hidden />;
  return <ShieldAlert size={16} strokeWidth={2} aria-hidden />;
}

export function AttributionMaturityBadge({ level = 'mature' }: { level?: string }) {
  const config: Record<string, { text: string; kind: PillKind }> = {
    mature: { text: '\u2713 Mature', kind: 'green' },
    developing: { text: 'Developing', kind: 'blue' },
    early: { text: 'Early', kind: 'amber' },
  };
  const c = config[level] || config.mature;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '2px',
      fontSize: '9px', fontWeight: 600, padding: '2px 9px', borderRadius: '9999px',
      ...pillStyle(c.kind),
    }}>
      {c.text}
    </span>
  );
}
