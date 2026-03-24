import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';

const ENTITY_LABELS: Record<string, string> = {
  revenue_verification: 'Revenue Verification Analysis',
  roas_interval: 'ROAS Credible Interval Analysis',
  model_divergence: 'Model Divergence Analysis',
  saturation_estimate: 'Saturation Estimate Analysis',
  campaign_anomaly: 'Campaign Anomaly Analysis',
};

function SkeletonLine({ width = '100%' }: { width?: string }) {
  return (
    <div style={{
      width, height: '14px', background: 'var(--border-default)',
      borderRadius: 'var(--radius-sm)', animation: 'shimmer 1.5s ease-in-out infinite',
    }} />
  );
}

export default function ExplanationDrawer({ isOpen, entityType, onClose }: {
  isOpen: boolean; entityType: string | null; onClose: () => void; channelId?: string;
}) {
  const [status, setStatus] = useState<'loading' | 'complete'>('loading');

  useEffect(() => {
    if (isOpen) {
      setStatus('loading');
      const timer = setTimeout(() => setStatus('complete'), 2500);
      return () => clearTimeout(timer);
    }
  }, [isOpen, entityType]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && isOpen) onClose(); };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, onClose]);

  // When closed, do not render the drawer or overlay at all.
  if (!isOpen) {
    return null;
  }

  return (
    <>
      <div onClick={onClose} style={{
        position: 'fixed', inset: 0, zIndex: 200, background: 'rgba(0,0,0,0.3)',
        opacity: 1, pointerEvents: 'auto',
        transition: 'opacity var(--transition-slow)',
      }} />
      <div role="dialog" aria-modal="true" aria-label={`${entityType || ''} explanation`} style={{
        position: 'fixed', right: 0, top: 0, width: '480px', height: '100vh',
        background: 'var(--bg-surface)', boxShadow: '-4px 0 15px rgba(0,0,0,0.1)',
        borderRadius: 'var(--radius-lg) 0 0 var(--radius-lg)', zIndex: 201,
        transform: 'translateX(0)',
        transition: 'transform var(--transition-slow)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}>
        <div style={{
          height: '64px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 24px', borderBottom: '1px solid var(--border-default)',
          background: 'var(--bg-surface)', flexShrink: 0,
        }}>
          <span style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)' }}>
            {ENTITY_LABELS[entityType || ''] || 'Analysis'}
          </span>
          <button onClick={onClose} aria-label="Close drawer" style={{
            width: '32px', height: '32px', background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--text-secondary)', borderRadius: 'var(--radius-sm)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'var(--transition-fast)',
          }}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-subtle)'; e.currentTarget.style.color = 'var(--text-primary)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'none'; e.currentTarget.style.color = 'var(--text-secondary)'; }}>
            <X size={16} />
          </button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
          {status === 'loading' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <SkeletonLine width="80%" /><SkeletonLine width="65%" /><SkeletonLine width="90%" /><SkeletonLine width="55%" />
              <div style={{ marginTop: '8px' }}><SkeletonLine width="75%" /><div style={{ height: '8px' }} /><SkeletonLine width="60%" /></div>
              <div style={{ marginTop: '16px', textAlign: 'center', fontSize: '12px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-sans)' }}>
                <span style={{ marginRight: '6px' }}>{'\u25CF'}</span>Running {'\u00B7'} estimated 15&ndash;30 seconds
              </div>
            </div>
          )}
          {status === 'complete' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <p style={{ margin: '0 0 4px', fontSize: '11px', fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.06em', fontFamily: 'var(--font-sans)' }}>Key Data Points</p>
                <div style={{ background: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {[
                    { label: 'Platform claimed:', value: '$82,000' },
                    { label: 'Webhook verified:', value: '$71,680' },
                    { label: 'Discrepancy:', value: '-$10,320 (\u221212.6%)' },
                    { label: 'Unmatched events:', value: '1,243 events' },
                  ].map((dp, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontFamily: 'var(--font-sans)' }}>{dp.label}</span>
                      <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 600 }}>{dp.value}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div style={{ height: '1px', background: 'var(--border-default)' }} />
              <div style={{ fontSize: '13px', color: 'var(--text-primary)', fontFamily: 'var(--font-sans)', lineHeight: 1.6 }}>
                <p style={{ fontWeight: 600, marginBottom: '8px', marginTop: 0 }}>Why does this discrepancy exist?</p>
                <p style={{ margin: '0 0 10px' }}>
                  Google Ads over-reported revenue by <strong style={{ fontFamily: 'var(--font-mono)' }}>$10,320 ({'\u2212'}12.6%)</strong> compared to Stripe webhook-verified transactions. This is a common occurrence due to platform attribution windows that differ from actual payment timestamps.
                </p>
                <p style={{ margin: '0 0 10px' }}>
                  The primary cause is <strong>view-through attribution</strong> {'\u2014'} Google Ads is claiming credit for conversions that occurred after ad impressions, but where no direct click-through can be verified against our Stripe webhook data.
                </p>
                <p style={{ margin: 0 }}>
                  This discrepancy is within the <strong>flagged ({'\u2212'}5% to {'\u2212'}25%)</strong> range. Consider tightening the attribution window in your Google Ads settings from 30 days to 7 days to reduce over-reporting.
                </p>
              </div>
              <div style={{ marginTop: '8px', paddingTop: '12px', borderTop: '1px solid var(--border-default)' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-sans)' }}>Generated March 6, 2026 at 11:47 PM</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
