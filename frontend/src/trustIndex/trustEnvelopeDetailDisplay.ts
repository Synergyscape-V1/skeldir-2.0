import { TRUST_ENVELOPE_DETAIL_COPY } from './trustEnvelopeDetailCopy';
import type { TrustEnvelopeDetailDTO } from '../detail/types';
import { formatMajorUnitsGrouped } from '../lib/money';

/** Display-only cents formatting for TrustEnvelope detail surfaces — not authoritative truth */
export function formatTrustEnvelopeMoneyMinorDisplay(amountMinor: bigint): string {
  const negative = amountMinor < 0n;
  const abs = negative ? -amountMinor : amountMinor;
  const major = abs / 100n;
  const cents = (abs % 100n).toString().padStart(2, '0');
  const prefix = negative ? '-$' : '$';
  return `${prefix}${formatMajorUnitsGrouped(major)}.${cents}`;
}
const CANONICAL_ENVELOPE_IDS: Record<string, string> = {
  env_0001: 'tenv_01JZA72J4M1WKH7RNPY5Q2A7S',
};

export function resolveTrustEnvelopeCanonicalId(envelopeId: string, canonicalEnvelopeId?: string): string {
  return canonicalEnvelopeId ?? CANONICAL_ENVELOPE_IDS[envelopeId] ?? envelopeId;
}

export function formatTrustEnvelopeDetailCreatedAt(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return 'Created —';

  const datePart = new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date);

  const timePart = new Intl.DateTimeFormat('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  }).format(date);

  return `Created ${datePart} · ${timePart} UTC`;
}

export function trustEnvelopeDetailStatusLabel(status: TrustEnvelopeDetailDTO['status']): string {
  return TRUST_ENVELOPE_DETAIL_COPY.status[status];
}

function formatIntervalValue(value: number): string {
  return Number.isInteger(value) ? value.toFixed(0) : value.toFixed(2);
}

export function formatTrustEnvelopeCredibleIntervalDisplay(
  intervalLower: number,
  intervalUpper: number,
): string {
  return `[${formatIntervalValue(intervalLower)}, ${formatIntervalValue(intervalUpper)}]`;
}

export function formatTrustEnvelopePosteriorSupportDisplay(posteriorSupport: number): string {
  const percent = posteriorSupport <= 1 ? posteriorSupport * 100 : posteriorSupport;
  const formatted = Number.isInteger(percent) ? percent.toFixed(0) : percent.toFixed(1);
  return `${formatted}%`;
}

export function formatTrustEnvelopeModelFreshnessDisplay(
  freshnessAt: string,
  referenceAt: string,
): string {
  const freshness = new Date(freshnessAt).getTime();
  const reference = new Date(referenceAt).getTime();
  if (Number.isNaN(freshness) || Number.isNaN(reference)) return 'Updated —';

  const diffMs = reference - freshness;
  if (diffMs < 60_000) return 'Updated just now';

  const diffMin = Math.round(diffMs / 60_000);
  if (diffMin < 60) return `Updated ${diffMin} min ago`;

  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `Updated ${diffHr} hr ago`;

  const diffDay = Math.round(diffHr / 24);
  return `Updated ${diffDay} day${diffDay === 1 ? '' : 's'} ago`;
}

export function formatTrustEnvelopeProvenanceTimestampDisplay(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return '—';

  const datePart = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: 'UTC',
  }).format(date);

  const timePart = new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  }).format(date);

  return `${datePart} ${timePart}`;
}

export function formatTrustEnvelopeHashDisplay(hash: string): string {
  const normalized = hash.startsWith('sha256:') ? hash : `sha256:${hash}`;
  const body = normalized.slice('sha256:'.length);
  if (body.length <= 24) {
    return `sha256: ${body}`;
  }
  return `sha256: ${body.slice(0, 16)}...${body.slice(-8)}`;
}
