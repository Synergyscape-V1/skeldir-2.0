import React, { useState } from 'react';
import { Info } from 'lucide-react';
import { AttributionMethodBadge } from '../../command-center/components/Badges';

function Sparkline({ data }: { data: number[] }) {
  if (!data || data.length < 2) return null;
  const height = 32;
  const padY = 2;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => ({ x: i / (data.length - 1), y: padY + (1 - (v - min) / range) * (height - padY * 2) }));
  const buildPath = (points: { x: number; y: number }[], w: number) => {
    const scaled = points.map(p => ({ x: p.x * w, y: p.y }));
    let d = `M ${scaled[0].x},${scaled[0].y}`;
    for (let i = 1; i < scaled.length; i++) {
      const prev = scaled[i - 1]; const curr = scaled[i];
      const cpx = (prev.x + curr.x) / 2;
      d += ` C ${cpx},${prev.y} ${cpx},${curr.y} ${curr.x},${curr.y}`;
    }
    return d;
  };
  const gradientId = `spark-fill-${Math.random().toString(36).slice(2, 8)}`;
  return (
    <svg width="100%" height={height} viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" style={{ display: 'block' }}>
      <defs><linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#059669" stopOpacity="0.15" /><stop offset="100%" stopColor="#059669" stopOpacity="0" /></linearGradient></defs>
      <path d={`${buildPath(pts, 100)} L 100,${height} L 0,${height} Z`} fill={`url(#${gradientId})`} />
      <path d={buildPath(pts, 100)} fill="none" stroke="#059669" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function BucketBadge({ bucket }: { bucket?: string }) {
  if (!bucket) return null;
  const colors: Record<string, string> = { narrow: 'var(--narrow-bucket)', medium: 'var(--medium-bucket)', wide: 'var(--wide-bucket)' };
  const labels: Record<string, string> = { narrow: 'Narrow', medium: 'Medium', wide: 'Wide' };
  const color = colors[bucket];
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', color, fontFamily: 'var(--font-sans)' }}>
      <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: color, display: 'inline-block', flexShrink: 0 }} />
      {labels[bucket]}
    </span>
  );
}

function RangeBar({ bucket }: { bucket?: string }) {
  const colors: Record<string, string> = { narrow: 'var(--narrow-bucket)', medium: 'var(--medium-bucket)', wide: 'var(--wide-bucket)' };
  return (
    <div style={{ width: '100%', height: '4px', background: 'var(--border-default)', borderRadius: 'var(--radius-sm)', overflow: 'hidden' }}>
      <div style={{ width: '60%', height: '100%', background: colors[bucket || ''] || 'var(--brand-primary)', borderRadius: 'var(--radius-sm)' }} />
    </div>
  );
}

export default function KPITile({
  label, value, credibleInterval, trend, verificationStatus, attributionMethod,
  infoTooltip, subLabel, agreementScore, sparklineData,
}: {
  label: string; value: string; credibleInterval?: any; trend?: any; verificationStatus?: string;
  attributionMethod?: string; infoTooltip?: string; subLabel?: string; agreementScore?: number;
  sparklineData?: number[];
}) {
  const [showTooltip, setShowTooltip] = useState(false);
  const [hovered, setHovered] = useState(false);
  const baseShadow = '0 4px 12px rgba(0,0,0,0.10)';
  const hoverShadow = '0 6px 16px rgba(0,0,0,0.12)';

  const getAgreementBadge = (score: number) => {
    if (score >= 0.9) return { dot: 'var(--status-verified)', label: 'Models agree' };
    if (score >= 0.7) return { dot: 'var(--status-caution)', label: 'Moderate divergence' };
    return { dot: 'var(--status-critical)', label: 'Models diverge \u2014 investigate' };
  };

  const getTrendStyle = (dir: string): React.CSSProperties => {
    if (dir === 'up') return { color: 'var(--status-verified)' };
    if (dir === 'down') return { color: 'var(--status-critical)' };
    return { color: 'var(--text-tertiary)' };
  };

  const getVerificationBadge = (status: string) => {
    if (status === 'verified') return { label: '\u2713 Stripe', color: 'var(--status-verified)' };
    if (status === 'partial') return { label: '\u26A1 Partial', color: 'var(--status-caution)' };
    return { label: '\u26A0 Unverified', color: 'var(--status-critical)' };
  };

  return (
    <div style={{
      background: '#FFFFFF',
      border: hovered ? '1px solid rgba(30,64,175,0.30)' : '1px solid #E5E7EB',
      borderRadius: '10px',
      boxShadow: hovered ? hoverShadow : baseShadow,
      padding: '20px', display: 'flex', flexDirection: 'column', gap: '6px', minHeight: '120px',
      cursor: 'default',
      transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
      position: 'relative',
    }}
      onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
      {/* Label row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '0.06em', color: 'var(--text-secondary)', textTransform: 'uppercase', fontFamily: 'var(--font-sans)' }}>
          {label}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {attributionMethod && <AttributionMethodBadge method={attributionMethod} converged={true} size="sm" />}
          {infoTooltip && (
            <div style={{ position: 'relative' }}>
              <button onMouseEnter={() => setShowTooltip(true)} onMouseLeave={() => setShowTooltip(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', padding: '2px', display: 'flex' }}>
                <Info size={13} />
              </button>
              {showTooltip && (
                <div style={{
                  position: 'absolute', top: '20px', right: 0, zIndex: 100,
                  background: 'var(--text-primary)', color: '#fff',
                  fontSize: '11px', padding: '8px 10px', borderRadius: 'var(--radius-sm)',
                  maxWidth: '220px', lineHeight: 1.5, whiteSpace: 'normal',
                  boxShadow: 'var(--shadow-lg)', minWidth: '180px',
                }}>
                  {infoTooltip}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Value */}
      <div style={{ fontSize: '32px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', lineHeight: 1.1 }}>
        {value}
      </div>

      {/* Verification badge */}
      {verificationStatus && (() => {
        const badge = getVerificationBadge(verificationStatus);
        return <span style={{ fontSize: '12px', color: badge.color, fontWeight: 500, fontFamily: 'var(--font-sans)' }}>{badge.label}</span>;
      })()}

      {/* Credible interval */}
      {credibleInterval && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '2px' }}>
          <RangeBar bucket={credibleInterval.bucket} />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{credibleInterval.lower}</span>
              <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>&mdash;</span>
              <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{credibleInterval.upper}</span>
            </div>
            <BucketBadge bucket={credibleInterval.bucket} />
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-sans)' }}>{credibleInterval.rangeLabel || '80% credible interval'}</span>
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-sans)' }}>{'\u25CF'} Narrow {'\u00B7'} Safe to act</span>
        </div>
      )}

      {/* Sub label */}
      {subLabel && <span style={{ fontSize: '12px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-sans)' }}>{subLabel}</span>}

      {/* Agreement score */}
      {agreementScore !== undefined && (() => {
        const ag = getAgreementBadge(agreementScore);
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '12px', color: 'var(--text-secondary)' }}>
            <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: ag.dot, display: 'inline-block' }} />
            {ag.label}
          </span>
        );
      })()}

      {/* Sparkline */}
      {sparklineData && (
        <div style={{ marginTop: '4px', marginBottom: '2px' }}>
          <Sparkline data={sparklineData} />
        </div>
      )}

      {/* Trend */}
      {trend && (
        <span style={{ ...getTrendStyle(trend.direction), fontSize: '12px', fontFamily: 'var(--font-sans)' }}>
          {trend.formattedValue} {trend.comparisonPeriod}
        </span>
      )}
    </div>
  );
}
