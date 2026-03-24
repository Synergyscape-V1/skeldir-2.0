import React, { useMemo, useState } from 'react';
import { AlertTriangle, Check, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { IntegrityIcon, integrityStateFromScore } from './Badges';
import { useVerifiedRevenuePolling } from '../hooks/useVerifiedRevenuePolling';

export interface TrustBandVerifiedRevenue {
  rawValue: number;
  status: 'verified' | 'partial' | 'unverified';
  source: string;
  lastUpdatedLabel: string;
}

export interface TrustBandIntegrity {
  score: number;
}

export type DataFreshnessState = 'fresh' | 'aging' | 'stale';

export interface TrustBandDataFreshness {
  lastSyncMinutesAgo: number;
  syncHistory: string[];
}

export interface TrustBandData {
  verifiedRevenue: TrustBandVerifiedRevenue;
  integrityScore: TrustBandIntegrity;
  dataFreshness: TrustBandDataFreshness;
}

/** Spec: fresh &lt;5 min, aging 5–30 min, stale &gt;30 min */
export function deriveFreshnessState(minutes: number): DataFreshnessState {
  if (minutes < 5) return 'fresh';
  if (minutes <= 30) return 'aging';
  return 'stale';
}

function FreshnessIcon({ state }: { state: DataFreshnessState }) {
  const common = { size: 16 as const, strokeWidth: 2 as const, 'aria-hidden': true as const };
  if (state === 'fresh') return <Check {...common} />;
  if (state === 'aging') return <AlertTriangle {...common} />;
  return <X {...common} />;
}

function freshnessStatusLabel(state: DataFreshnessState) {
  if (state === 'fresh') return 'Fresh';
  if (state === 'aging') return 'Aging';
  return 'Stale';
}

export default function TrustBand({ data }: { data: TrustBandData }) {
  const navigate = useNavigate();
  const { verifiedRevenue, integrityScore, dataFreshness } = data;
  const { displayFormatted } = useVerifiedRevenuePolling(verifiedRevenue.rawValue, 30_000);

  const [freshnessOpen, setFreshnessOpen] = useState(false);
  const [integrityOpen, setIntegrityOpen] = useState(false);

  const integrity = useMemo(() => integrityStateFromScore(integrityScore.score), [integrityScore.score]);

  const freshnessState = useMemo(
    () => deriveFreshnessState(dataFreshness.lastSyncMinutesAgo),
    [dataFreshness.lastSyncMinutesAgo]
  );

  const freshnessStatusClass = useMemo(() => {
    if (freshnessState === 'fresh') return 'cc-freshness-line__status--fresh';
    if (freshnessState === 'aging') return 'cc-freshness-line__status--aging';
    return 'cc-freshness-line__status--stale';
  }, [freshnessState]);

  /** Reuse freshness status colors: Good → fresh (verified), Needs Review → aging, Critical → stale */
  const integrityStatusClass = useMemo(() => {
    if (integrity.variant === 'verified') return 'cc-freshness-line__status--fresh';
    if (integrity.variant === 'caution') return 'cc-freshness-line__status--aging';
    return 'cc-freshness-line__status--stale';
  }, [integrity.variant]);

  return (
    <>
      <section className="cc-trust-band" aria-label="Data trust status">
        {/* Verified Revenue */}
        <div className="cc-trust-band__section">
          <p className="cc-trust-band__label">Verified Revenue</p>
          <div className="cc-trust-band__value-row">
            <span className="cc-trust-band__value">{displayFormatted}</span>
          </div>
          <p className="cc-trust-band__meta cc-trust-band__meta--source">
            via <span className="cc-trust-band__source-name">{verifiedRevenue.source}</span>
          </p>
          <p className="cc-trust-band__meta">Last updated: {verifiedRevenue.lastUpdatedLabel}</p>
        </div>

        <div className="cc-trust-band__divider" aria-hidden="true" />

        {/* Integrity Score — same block + lines + popover pattern as Data Freshness (no pill) */}
        <div className="cc-trust-band__section">
          <p className="cc-trust-band__label">Integrity Score</p>
          <button
            type="button"
            className="cc-freshness-block"
            onClick={() => setIntegrityOpen((o) => !o)}
            aria-expanded={integrityOpen}
            aria-controls="cc-integrity-popover"
            id="cc-integrity-trigger"
            aria-label={`Integrity composite ${integrityScore.score} of 100, ${integrity.label}. ${integrity.threshold}. Toggle details.`}
          >
            <span className="cc-freshness-line">
              <span className="cc-freshness-line__label">Composite score:</span>
              <span className="cc-freshness-line__time">
                {integrityScore.score}/100
              </span>
            </span>
            <span className={`cc-freshness-line cc-freshness-line__status ${integrityStatusClass}`}>
              <IntegrityIcon variant={integrity.variant} />
              {integrity.label}
              <span className="cc-freshness-line__meta"> · {integrity.threshold}</span>
            </span>
          </button>
          {integrityOpen && (
            <div id="cc-integrity-popover" role="tooltip" className="cc-freshness-popover">
              <strong className="cc-freshness-popover__title">Integrity breakdown</strong>
              <p className="cc-freshness-popover__text">
                Composite <strong>{integrityScore.score}/100</strong> — {integrity.label}. {integrity.threshold}. Weighted from
                source freshness, reconciliation coverage, and platform agreement.
              </p>
              <button
                type="button"
                className="cc-integrity-popover__cta"
                onClick={() => {
                  navigate('/data');
                  setIntegrityOpen(false);
                }}
              >
                Open Data Health →
              </button>
            </div>
          )}
        </div>

        <div className="cc-trust-band__divider" aria-hidden="true" />

        {/* Data Freshness */}
        <div className="cc-trust-band__section">
          <p className="cc-trust-band__label">Data Freshness</p>
          <button
            type="button"
            className="cc-freshness-block"
            onClick={() => setFreshnessOpen((o) => !o)}
            aria-expanded={freshnessOpen}
            aria-controls="cc-freshness-popover"
            id="cc-freshness-trigger"
          >
            <span className="cc-freshness-line">
              <span className="cc-freshness-line__label">Last sync:</span>
              <span className="cc-freshness-line__time">
                {dataFreshness.lastSyncMinutesAgo} minute{dataFreshness.lastSyncMinutesAgo === 1 ? '' : 's'} ago
              </span>
            </span>
            <span className={`cc-freshness-line cc-freshness-line__status ${freshnessStatusClass}`}>
              <FreshnessIcon state={freshnessState} />
              {freshnessStatusLabel(freshnessState)}
            </span>
          </button>
          {freshnessOpen && (
            <div
              id="cc-freshness-popover"
              role="tooltip"
              className="cc-freshness-popover"
            >
              <strong className="cc-freshness-popover__title">Sync history by platform</strong>
              <ul className="cc-freshness-popover__list">
                {dataFreshness.syncHistory.map((line) => (
                  <li key={line} className="cc-freshness-popover__item">
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </section>
    </>
  );
}
