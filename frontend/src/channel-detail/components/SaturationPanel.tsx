import React from 'react';
import { Info } from 'lucide-react';

export default function SaturationPanel({ channelAttribution }: { channelAttribution: any }) {
  const saturation = channelAttribution?.saturation;
  const currentSpendFormatted = channelAttribution?.spendFormatted || '$22,400';

  if (!saturation) {
    return (
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-sm)', padding: '20px 24px' }}>
        <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '16px', fontFamily: 'var(--font-sans)' }}>Channel Saturation</div>
        <p style={{ fontSize: '13px', color: 'var(--text-tertiary)', textAlign: 'center', marginTop: '24px' }}>Saturation analysis not yet available for this channel. Requires at least 60 days of spend data.</p>
      </div>
    );
  }

  const { headroomPct, saturationPoint, currentUtilization, headroomFormatted } = saturation;
  const pct = currentUtilization * 100;

  const getBarColor = (util: number) => {
    if (util < 0.60) return 'var(--status-verified)';
    if (util <= 0.85) return 'var(--brand-primary)';
    if (util <= 0.95) return 'var(--status-caution)';
    return 'var(--status-critical)';
  };

  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-sm)',
      padding: '20px 24px', height: '100%', display: 'flex', flexDirection: 'column', gap: '12px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)' }}>Channel Saturation</span>
        <Info size={14} style={{ color: 'var(--text-tertiary)', cursor: 'pointer' }} />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {/* LeverageScientific.com — bar track/fill element leaner/slimmer */}
        <div style={{ width: '100%', height: '10px', background: '#E2E8F0', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
          <div style={{ width: `${pct}%`, height: '100%', background: getBarColor(currentUtilization), borderRadius: 'var(--radius-md)', transition: 'width 0.5s ease' }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-primary)', fontFamily: 'var(--font-sans)' }}>{pct.toFixed(0)}% utilized</span>
        </div>
      </div>
      <div style={{ height: '1px', background: 'var(--border-default)' }} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {[
          { label: 'Saturation point', value: `$${saturationPoint.toLocaleString()}/mo` },
          { label: 'Current spend', value: `${currentSpendFormatted}/mo` },
          { label: 'Headroom', value: headroomFormatted },
        ].map((row, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-secondary)', fontFamily: 'var(--font-sans)' }}>{row.label}</span>
            <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 500 }}>{row.value}</span>
          </div>
        ))}
      </div>
      <div style={{ height: '1px', background: 'var(--border-default)' }} />
      <p style={{ fontSize: '13px', color: 'var(--text-secondary)', fontFamily: 'var(--font-sans)', lineHeight: 1.5, margin: 0, fontStyle: 'italic' }}>
        Spend can increase ~{headroomPct.toFixed(0)}% before diminishing returns begin.
      </p>
    </div>
  );
}
