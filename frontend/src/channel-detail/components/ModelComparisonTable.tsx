import React from 'react';

const METHOD_LABELS: Record<string, string> = {
  bayesian: 'Bayesian', first_touch: 'First-touch', last_touch: 'Last-touch',
  linear: 'Linear', time_decay: 'Time Decay', position_based: 'Position Based',
  deterministic_fallback: 'Deterministic (fallback)', bayesian_2: 'Bayesian', linear_2: 'Linear', bayesian_det: 'Bayesian',
};

function AgreementDot({ score }: { score: number | null }) {
  if (score === null || score === undefined) return <span style={{ color: 'var(--text-tertiary)' }}>&mdash;</span>;
  let color = 'var(--status-verified)';
  if (score < 0.9 && score >= 0.7) color = 'var(--status-caution)';
  if (score < 0.7) color = 'var(--status-critical)';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '12px', color: 'var(--text-secondary)' }}>
      <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: color, display: 'inline-block' }} />
      {score.toFixed(2)}
    </span>
  );
}

export default function ModelComparisonTable({ models, channelName }: { models: any[]; channelName?: string }) {
  const thStyle: React.CSSProperties = {
    padding: '10px 12px', fontSize: '11px', fontWeight: 600, color: 'var(--text-tertiary)',
    textTransform: 'uppercase', letterSpacing: '0.05em', borderBottom: '1px solid var(--border-default)',
    fontFamily: 'var(--font-sans)', whiteSpace: 'nowrap', background: 'var(--bg-subtle)',
  };

  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-sm)', overflow: 'hidden',
    }}>
      <div style={{ padding: '16px 20px 0', borderBottom: '1px solid var(--border-default)' }}>
        <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)', paddingBottom: '14px' }}>
          How do different models see this channel?
        </div>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }} aria-label={`Attribution model comparison for ${channelName || 'Google Ads'}`}>
        <thead>
          <tr>
            <th style={{ ...thStyle, textAlign: 'left' }}>Model</th>
            <th style={{ ...thStyle, textAlign: 'right' }}>ROAS</th>
            <th style={{ ...thStyle, textAlign: 'left', minWidth: '100px' }}>80% CI Range</th>
            <th style={{ ...thStyle, textAlign: 'right' }}>Attribution Wt.</th>
            <th style={{ ...thStyle, textAlign: 'center' }}>Agreement</th>
          </tr>
        </thead>
        <tbody>
          {models.map((row: any, i: number) => {
            const isBayesian = row.isActive;
            return (
              <tr key={i} style={{
                background: isBayesian ? 'var(--bg-selected)' : i % 2 === 0 ? 'var(--bg-surface)' : 'var(--bg-subtle)',
                borderLeft: isBayesian ? '3px solid var(--brand-primary)' : '3px solid transparent',
                transition: 'background var(--transition-fast)',
              }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-subtle)')}
                onMouseLeave={e => (e.currentTarget.style.background = isBayesian ? 'var(--bg-selected)' : i % 2 === 0 ? 'var(--bg-surface)' : 'var(--bg-subtle)')}>
                <td style={{ padding: '10px 12px', fontSize: '13px', fontWeight: isBayesian ? 600 : 400, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)', borderBottom: '1px solid var(--border-default)' }}>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    {row.method === 'bayesian' && <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--status-verified)', display: 'inline-block', marginRight: '6px', flexShrink: 0 }} />}
                    {row.displayName || METHOD_LABELS[row.method] || row.method}
                  </div>
                </td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: isBayesian ? 600 : 400, color: 'var(--text-primary)', borderBottom: '1px solid var(--border-default)' }}>
                  {row.roasFormatted}
                </td>
                <td style={{ padding: '10px 12px', fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-default)' }}>
                  {row.credibleInterval ? `${row.credibleInterval.lower} \u2013 ${row.credibleInterval.upper}` : <span style={{ color: 'var(--text-tertiary)' }}>&mdash;</span>}
                </td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '13px', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-default)' }}>
                  {row.weightFormatted}
                </td>
                <td style={{ padding: '10px 12px', textAlign: 'center', borderBottom: '1px solid var(--border-default)' }}>
                  {isBayesian ? <span style={{ color: 'var(--text-tertiary)', fontSize: '13px' }}>&mdash;</span> : <AgreementDot score={row.agreementWithBayesian} />}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div style={{ padding: '10px 12px', borderTop: '2px solid var(--border-default)', display: 'flex', justifyContent: 'space-between', background: 'var(--bg-subtle)' }}>
        <span style={{ fontSize: '12px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-sans)' }}>
          Attribution method in use: <strong>Bayesian (converged)</strong>
        </span>
        <span style={{ fontSize: '12px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-sans)' }}>Last updated: 14 min ago</span>
      </div>
    </div>
  );
}
