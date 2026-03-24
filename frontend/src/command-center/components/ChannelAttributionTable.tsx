import React, { useMemo, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { AttributionMethodBadge, BucketBadge, VerificationBadge } from './Badges';
import CredibleIntervalBar from './CredibleIntervalBar';
import type { ChannelAttributionRow, ConfidenceBucket } from '../types/channelAttribution';

/** Platform logo assets aligned with ChannelIcon (channel-comparison). */
const PLATFORM_ICONS: Record<string, { src: string; alt: string }> = {
  google_ads: { src: '/assets/platform-icons/google-ads.svg', alt: 'Google Ads' },
  meta: { src: '/assets/platform-icons/meta-ads.svg', alt: 'Meta Ads' },
  tiktok: { src: '/assets/platform-icons/tiktok-ads.svg', alt: 'TikTok Ads' },
  linkedin: { src: '/assets/platform-icons/linkedin-ads.svg', alt: 'LinkedIn Ads' },
  pinterest: { src: '/assets/platform-icons/pinterest-ads.svg', alt: 'Pinterest Ads' },
};

const PLATFORM_ICON_SIZE = 24;

function PlatformIcon({ platform }: { platform: string }) {
  const meta = PLATFORM_ICONS[platform] ?? { src: '', alt: platform };
  if (!meta.src) {
    return (
      <span
        className="cc-channel-table__icon-fallback"
        aria-label={platform}
      >
        ?
      </span>
    );
  }
  return (
    <img
      src={meta.src}
      alt=""
      width={PLATFORM_ICON_SIZE}
      height={PLATFORM_ICON_SIZE}
      className="cc-channel-table__platform-img"
      loading="lazy"
      decoding="async"
    />
  );
}

function parseMoney(s: string): number {
  const n = parseFloat(String(s).replace(/[^0-9.-]/g, ''));
  return Number.isFinite(n) ? n : 0;
}

function formatUsd(n: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);
}

function revenueSubline(ch: ChannelAttributionRow): string {
  if (ch.verifiedStatus === 'verified') {
    return ch.verificationSource ? `Verified via ${ch.verificationSource}` : 'Verified';
  }
  if (ch.verifiedStatus === 'partial') return 'Partially verified';
  return 'Unverified';
}

export type ChannelSortKey = 'source' | 'spend' | 'revenue' | 'roas' | 'confidence' | 'trend';

const CONF_ORDER: Record<ConfidenceBucket, number> = {
  narrow: 0,
  medium: 1,
  wide: 2,
};

function compareRows(a: ChannelAttributionRow, b: ChannelAttributionRow, key: ChannelSortKey): number {
  switch (key) {
    case 'source':
      return a.channelName.localeCompare(b.channelName, undefined, { sensitivity: 'base' });
    case 'spend':
      return parseMoney(a.spend) - parseMoney(b.spend);
    case 'revenue':
      return parseMoney(a.verifiedRevenue) - parseMoney(b.verifiedRevenue);
    case 'roas':
      return a.roas.estimate - b.roas.estimate;
    case 'confidence':
      return CONF_ORDER[a.confidence] - CONF_ORDER[b.confidence];
    case 'trend':
      return a.trend.sortValue - b.trend.sortValue;
    default:
      return 0;
  }
}

export default function ChannelAttributionTable({
  channels,
  attributionMethod = 'bayesian',
  onChannelClick,
}: {
  channels: ChannelAttributionRow[];
  attributionMethod?: string;
  onChannelClick?: (channelId: string) => void;
}) {
  const [sortKey, setSortKey] = useState<ChannelSortKey>('spend');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const roasMin = Math.min(...channels.map((c) => c.roas.lower));
  const roasMax = Math.max(...channels.map((c) => c.roas.upper));
  const roasRange = Math.max(roasMax - roasMin, 1e-9);
  const roasDomainMin = Math.max(0, roasMin - roasRange * 0.05);
  const roasDomainMax = roasMax + roasRange * 0.05;

  const sorted = useMemo(() => {
    const next = [...channels];
    next.sort((a, b) => {
      const c = compareRows(a, b, sortKey);
      return sortDir === 'asc' ? c : -c;
    });
    return next;
  }, [channels, sortKey, sortDir]);

  const footer = useMemo(() => {
    let spend = 0;
    let rev = 0;
    let weightedRoas = 0;
    for (const ch of channels) {
      const s = parseMoney(ch.spend);
      const r = parseMoney(ch.verifiedRevenue);
      spend += s;
      rev += r;
      weightedRoas += s * ch.roas.estimate;
    }
    const blended = spend > 0 ? weightedRoas / spend : 0;
    return { spend, rev, blended };
  }, [channels]);

  const handleSort = (key: ChannelSortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(key);
      setSortDir(key === 'source' ? 'asc' : 'desc');
    }
  };

  const SortIcon = ({ col }: { col: ChannelSortKey }) => {
    if (sortKey !== col) {
      return (
        <span className="cc-channel-table__sort-icon cc-channel-table__sort-icon--idle" aria-hidden>
          <ChevronDown size={12} />
        </span>
      );
    }
    return sortDir === 'asc' ? (
      <span className="cc-channel-table__sort-icon cc-channel-table__sort-icon--active" aria-hidden>
        <ChevronUp size={12} />
      </span>
    ) : (
      <span className="cc-channel-table__sort-icon cc-channel-table__sort-icon--active" aria-hidden>
        <ChevronDown size={12} />
      </span>
    );
  };

  return (
    <section
      className={`cc-channel-table${onChannelClick ? ' cc-channel-table--interactive' : ''}`}
      aria-labelledby="cc-channel-table-heading"
    >
      <div className="cc-channel-table__toolbar">
        <h2 id="cc-channel-table-heading" className="cc-channel-table__heading">
          Channel Performance Table
        </h2>
        <AttributionMethodBadge method={attributionMethod} converged size="sm" />
      </div>

      <div className="cc-channel-table__scroll">
        <table className="cc-channel-table__grid">
          <thead>
            <tr>
              <th scope="col" className="cc-channel-table__th cc-channel-table__th--sortable" aria-sort={sortKey === 'source' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'} onClick={() => handleSort('source')}>
                <span className="cc-channel-table__th-inner">
                  Source
                  <SortIcon col="source" />
                </span>
              </th>
              <th scope="col" className="cc-channel-table__th cc-channel-table__th--sortable cc-channel-table__th--num" aria-sort={sortKey === 'spend' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'} onClick={() => handleSort('spend')}>
                <span className="cc-channel-table__th-inner">
                  Spend
                  <SortIcon col="spend" />
                </span>
              </th>
              <th scope="col" className="cc-channel-table__th cc-channel-table__th--sortable cc-channel-table__th--num" aria-sort={sortKey === 'revenue' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'} onClick={() => handleSort('revenue')}>
                <span className="cc-channel-table__th-inner">
                  Revenue (Verified)
                  <SortIcon col="revenue" />
                </span>
              </th>
              <th scope="col" className="cc-channel-table__th cc-channel-table__th--sortable cc-channel-table__th--num" aria-sort={sortKey === 'roas' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'} onClick={() => handleSort('roas')}>
                <span className="cc-channel-table__th-inner">
                  ROAS
                  <SortIcon col="roas" />
                </span>
              </th>
              <th scope="col" className="cc-channel-table__th cc-channel-table__th--sortable cc-channel-table__th--center" aria-sort={sortKey === 'confidence' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'} onClick={() => handleSort('confidence')}>
                <span className="cc-channel-table__th-inner">
                  Confidence
                  <SortIcon col="confidence" />
                </span>
              </th>
              <th scope="col" className="cc-channel-table__th cc-channel-table__th--sortable cc-channel-table__th--center cc-channel-table__col--trend" aria-sort={sortKey === 'trend' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'} onClick={() => handleSort('trend')}>
                <span className="cc-channel-table__th-inner">
                  Trend
                  <SortIcon col="trend" />
                </span>
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((ch) => {
              const halfWidth = (ch.roas.upper - ch.roas.lower) / 2;
              const roasTip = `${ch.roas.lower.toFixed(2)} – ${ch.roas.upper.toFixed(2)} · ${ch.roas.actionImplication ?? ch.confidenceActionImplication ?? ''}`;
              const verTip = [ch.verificationSource && ch.verifiedStatus === 'verified' ? `Source: ${ch.verificationSource}` : null, ch.lastVerifiedLabel ? `Last verified: ${ch.lastVerifiedLabel}` : null]
                .filter(Boolean)
                .join(' · ');
              const trendTitle = ch.trend.comparisonHint ?? '';

              return (
                <tr
                  key={ch.channelId}
                  className="cc-channel-table__row"
                  onClick={() => onChannelClick?.(ch.channelId)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onChannelClick?.(ch.channelId);
                    }
                  }}
                  tabIndex={onChannelClick ? 0 : undefined}
                  aria-label={onChannelClick ? `Open ${ch.channelName} channel details` : undefined}
                >
                  <td className="cc-channel-table__td">
                    <div className="cc-channel-table__source">
                      <PlatformIcon platform={ch.platform} />
                      <span className="cc-channel-table__source-name">{ch.channelName}</span>
                    </div>
                  </td>
                  <td className="cc-channel-table__td cc-channel-table__td--num">
                    <span className="cc-channel-table__mono">{ch.spend}</span>
                  </td>
                  <td className="cc-channel-table__td cc-channel-table__td--num">
                    <div className="cc-channel-table__rev">
                      <div className="cc-channel-table__rev-line">
                        <span className="cc-channel-table__mono">{ch.verifiedRevenue}</span>
                        <VerificationBadge
                          status={ch.verifiedStatus}
                          source={ch.verificationSource ?? 'Stripe'}
                          lastSyncLabel={ch.lastVerifiedLabel}
                          compact
                        />
                      </div>
                      <p className="cc-channel-table__rev-sub" title={verTip || undefined}>
                        {revenueSubline(ch)}
                      </p>
                    </div>
                  </td>
                  <td className="cc-channel-table__td cc-channel-table__td--num">
                    <div className="cc-channel-table__roas" title={roasTip}>
                      <div className="cc-channel-table__roas-line">
                        <span className="cc-channel-table__mono cc-channel-table__mono--500">{ch.roas.formattedEstimate}</span>
                        <span className="cc-channel-table__roas-pm">(±{halfWidth.toFixed(2)})</span>
                      </div>
                      <div className="cc-channel-table__roas-bar">
                        <CredibleIntervalBar
                          lower={ch.roas.lower}
                          upper={ch.roas.upper}
                          estimate={ch.roas.estimate}
                          domainMin={roasDomainMin}
                          domainMax={roasDomainMax}
                          bucket={ch.roas.bucket}
                          height={4}
                          widthPercent={100}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="cc-channel-table__td cc-channel-table__td--center">
                    <BucketBadge bucket={ch.confidence} size="sm" title={ch.confidenceActionImplication} />
                  </td>
                  <td className="cc-channel-table__td cc-channel-table__td--center cc-channel-table__col--trend">
                    <span
                      className={`cc-channel-table__trend cc-channel-table__trend--${ch.trend.direction}`}
                      title={trendTitle}
                    >
                      {ch.trend.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="cc-channel-table__foot-row">
              <td className="cc-channel-table__td cc-channel-table__td--foot">Totals</td>
              <td className="cc-channel-table__td cc-channel-table__td--num cc-channel-table__td--foot">
                <span className="cc-channel-table__mono">{formatUsd(footer.spend)}</span>
              </td>
              <td className="cc-channel-table__td cc-channel-table__td--num cc-channel-table__td--foot">
                <span className="cc-channel-table__mono">{formatUsd(footer.rev)}</span>
              </td>
              <td className="cc-channel-table__td cc-channel-table__td--num cc-channel-table__td--foot">
                <span className="cc-channel-table__mono">{footer.blended.toFixed(2)}</span>
                <span className="cc-channel-table__foot-hint"> blended</span>
              </td>
              <td className="cc-channel-table__td cc-channel-table__td--foot" colSpan={2} />
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
