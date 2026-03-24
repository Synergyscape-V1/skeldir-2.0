import React from 'react';

const BUCKET_TINT: Record<string, string> = {
  narrow: 'rgba(5, 150, 105, 0.08)',
  medium: 'rgba(217, 119, 6, 0.08)',
  wide: 'rgba(220, 38, 38, 0.08)',
};

const BUCKET_FILL: Record<string, string> = {
  narrow: 'rgba(5, 150, 105, 0.45)',
  medium: 'rgba(217, 119, 6, 0.45)',
  wide: 'rgba(220, 38, 38, 0.45)',
};

export default function CredibleIntervalBar({
  lower,
  upper,
  estimate,
  domainMin,
  domainMax,
  bucket = 'narrow',
  height = 4,
  widthPercent = 100,
  variant = 'default',
}: {
  lower: number;
  upper: number;
  estimate: number;
  domainMin?: number;
  domainMax?: number;
  bucket?: string;
  height?: number;
  widthPercent?: number;
  /** Directive card: inset track + bucket tint + interval (Constitution §3.1). */
  variant?: 'default' | 'directive';
}) {
  const autoPadding = (upper - lower) * 0.5;
  const min = domainMin ?? Math.max(0, lower - autoPadding);
  const max = domainMax ?? (upper + autoPadding);
  const range = Math.max(max - min, 1e-9);

  const clampPct = (pct: number) => Math.max(0, Math.min(100, pct));
  const lowerPct = clampPct(((lower - min) / range) * 100);
  const upperPct = clampPct(((upper - min) / range) * 100);
  const estimatePct = clampPct(((estimate - min) / range) * 100);
  const barLeft = Math.min(lowerPct, upperPct);
  const barWidth = Math.max(0, Math.abs(upperPct - lowerPct));

  const bucketColor: Record<string, string> = {
    narrow: '#16A34A',
    medium: '#D97706',
    wide: '#DC2626',
  };
  const color = bucketColor[bucket] || '#94A3B8';
  const markerWidthPx = Math.max(2, Math.round(height / 2));
  const cornerRadiusPx = variant === 'directive' ? 2 : 0;

  if (variant === 'directive') {
    const tint = BUCKET_TINT[bucket] ?? BUCKET_TINT.narrow;
    const fill = BUCKET_FILL[bucket] ?? BUCKET_FILL.narrow;
    return (
      <div
        className="cc-directive-ci-bar"
        style={{
          position: 'relative',
          width: `${widthPercent}%`,
          height: `${height + 4}px`,
        }}
      >
        {/* Full-width inset track */}
        <div
          style={{
            position: 'absolute',
            top: '50%',
            transform: 'translateY(-50%)',
            width: '100%',
            height: `${height}px`,
            borderRadius: `${cornerRadiusPx}px`,
            backgroundColor: 'var(--cc-bg-inset, #f4f6f8)',
          }}
        />
        {/* Bucket tint (8% opacity band) */}
        <div
          style={{
            position: 'absolute',
            top: '50%',
            transform: 'translateY(-50%)',
            width: '100%',
            height: `${height}px`,
            borderRadius: `${cornerRadiusPx}px`,
            backgroundColor: tint,
          }}
        />
        {/* Credible interval segment */}
        <div
          style={{
            position: 'absolute',
            top: '50%',
            transform: 'translateY(-50%)',
            height: `${height}px`,
            left: `${barLeft}%`,
            width: `${barWidth}%`,
            borderRadius: `${cornerRadiusPx}px`,
            backgroundColor: fill,
          }}
        />
        {/* Point estimate marker */}
        <div
          style={{
            position: 'absolute',
            top: '50%',
            height: `${height + 4}px`,
            left: `${estimatePct}%`,
            width: `${markerWidthPx}px`,
            borderRadius: `${cornerRadiusPx}px`,
            backgroundColor: '#0f172a',
            transform: 'translateX(-50%) translateY(-50%)',
          }}
        />
      </div>
    );
  }

  return (
    <div
      style={{
        position: 'relative',
        width: `${widthPercent}%`,
        margin: '0 auto',
        height: `${height + 4}px`,
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: '50%',
          transform: 'translateY(-50%)',
          width: '100%',
          height: `${height}px`,
          borderRadius: `${cornerRadiusPx}px`,
          backgroundColor: color,
          opacity: 0.18,
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: '50%',
          transform: 'translateY(-50%)',
          height: `${height}px`,
          left: `${barLeft}%`,
          width: `${barWidth}%`,
          borderRadius: `${cornerRadiusPx}px`,
          backgroundColor: color,
          opacity: 0.85,
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: '50%',
          height: `${height + 4}px`,
          left: `${estimatePct}%`,
          width: `${markerWidthPx}px`,
          borderRadius: `${cornerRadiusPx}px`,
          backgroundColor: '#0F172A',
          transform: 'translateX(-50%) translateY(-50%)',
        }}
      />
    </div>
  );
}
