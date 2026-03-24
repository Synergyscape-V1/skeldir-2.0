import React, { useState } from 'react';
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';

function MiniRangeBar({ lower, upper, bucket, estimate }: { lower: number; upper: number; bucket?: string; estimate?: number }) {
  const colors: Record<string, string> = { narrow: 'var(--narrow-bucket)', medium: 'var(--medium-bucket)', wide: 'var(--wide-bucket)' };
  const range = upper - lower;
  const fillPct = range > 0 && estimate !== undefined ? ((estimate - lower) / range) * 100 : 50;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: 'var(--text-primary)', fontWeight: 500 }}>{estimate?.toFixed(2) || '\u2014'}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        <span style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{lower}</span>
        <div style={{ flex: 1, height: '3px', background: 'var(--border-default)', borderRadius: '2px', overflow: 'hidden', position: 'relative', minWidth: '40px' }}>
          <div style={{ position: 'absolute', left: `${Math.max(0, Math.min(80, fillPct))}%`, top: 0, width: '20%', height: '100%', background: colors[bucket || ''] || 'var(--brand-primary)' }} />
        </div>
        <span style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{upper}</span>
      </div>
      <span style={{ fontSize: '10px', color: colors[bucket || ''] || 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: '3px' }}>
        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: colors[bucket || ''], display: 'inline-block' }} />
        {bucket ? bucket.charAt(0).toUpperCase() + bucket.slice(1) : ''}
      </span>
    </div>
  );
}

function DiscrepancyCell({ pct, status }: { pct: number | null; status: string }) {
  if (pct === null || pct === undefined) return <span style={{ color: 'var(--text-tertiary)' }}>&mdash;</span>;
  const colors: Record<string, string> = { accurate: 'var(--status-verified)', flagged: 'var(--status-caution)', severe: 'var(--status-critical)' };
  const color = colors[status] || 'var(--text-secondary)';
  const sign = pct > 0 ? '+' : '';
  return <span style={{ color, fontSize: '12px', fontFamily: 'var(--font-mono)', fontWeight: 500, whiteSpace: 'nowrap' }}>{sign}{pct.toFixed(1)}%</span>;
}

export default function CampaignTable({ campaigns, channelAttribution }: { campaigns: any[]; channelAttribution: any }) {
  const [sortCol, setSortCol] = useState('attributionWeight');
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc');
  const [hoveredRow, setHoveredRow] = useState<number | null>(null);

  const handleSort = (col: string) => {
    if (sortCol === col) setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    else { setSortCol(col); setSortDir('desc'); }
  };

  const sorted = [...(campaigns || [])].sort((a, b) => {
    let av: number, bv: number;
    if (sortCol === 'roas') { av = a.roas?.estimate; bv = b.roas?.estimate; }
    else if (sortCol === 'spend') { av = a.spend; bv = b.spend; }
    else if (sortCol === 'verifiedRevenue') { av = a.verifiedRevenue; bv = b.verifiedRevenue; }
    else { av = a.attributionWeight; bv = b.attributionWeight; }
    return sortDir === 'desc' ? bv - av : av - bv;
  });

  const thStyle: React.CSSProperties = {
    padding: '10px 12px', fontSize: '11px', fontWeight: 600, color: 'var(--text-tertiary)',
    textTransform: 'uppercase', letterSpacing: '0.05em', background: 'var(--bg-subtle)',
    borderBottom: '1px solid var(--border-default)', fontFamily: 'var(--font-sans)',
    whiteSpace: 'nowrap', cursor: 'pointer', userSelect: 'none',
  };

  const SortIcon = ({ col }: { col: string }) => {
    if (sortCol !== col) return <ArrowUpDown size={11} style={{ color: 'var(--text-tertiary)', marginLeft: '4px' }} />;
    return sortDir === 'desc'
      ? <ArrowDown size={11} style={{ color: 'var(--brand-primary)', marginLeft: '4px' }} />
      : <ArrowUp size={11} style={{ color: 'var(--brand-primary)', marginLeft: '4px' }} />;
  };

  const tdBase: React.CSSProperties = {
    padding: '10px 12px', fontSize: '13px', borderBottom: '1px solid var(--border-default)',
    fontFamily: 'var(--font-sans)', color: 'var(--text-primary)', verticalAlign: 'middle',
  };

  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-sm)', overflow: 'hidden' }}>
      <div style={{ padding: '16px 20px 0', borderBottom: '1px solid var(--border-default)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', paddingBottom: '14px' }}>
          <span style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)' }}>Campaign Breakdown</span>
          <span style={{ fontSize: '11px', color: 'var(--text-secondary)', background: 'var(--bg-subtle)', padding: '2px 8px', borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-sans)' }}>
            {campaigns?.length || 0} campaigns
          </span>
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '700px' }}>
          <thead>
            <tr>
              <th style={{ ...thStyle, textAlign: 'left' }} onClick={() => handleSort('campaign')}>Campaign</th>
              <th style={{ ...thStyle, textAlign: 'right' }} onClick={() => handleSort('spend')}>
                <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'flex-end', width: '100%' }}>Spend <SortIcon col="spend" /></span>
              </th>
              <th style={{ ...thStyle, textAlign: 'right' }} onClick={() => handleSort('verifiedRevenue')}>
                <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'flex-end', width: '100%' }}>Verified Revenue <SortIcon col="verifiedRevenue" /></span>
              </th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Discrepancy</th>
              <th style={{ ...thStyle, textAlign: 'left' }} onClick={() => handleSort('roas')}>
                <span style={{ display: 'flex', alignItems: 'center' }}>ROAS <SortIcon col="roas" /></span>
              </th>
              <th style={{ ...thStyle, textAlign: 'right' }} onClick={() => handleSort('attributionWeight')}>
                <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'flex-end', width: '100%' }}>Attribution Wt. <SortIcon col="attributionWeight" /></span>
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => (
              <tr key={row.campaignId} onMouseEnter={() => setHoveredRow(i)} onMouseLeave={() => setHoveredRow(null)}
                style={{ background: hoveredRow === i ? 'var(--bg-subtle)' : 'var(--bg-surface)', transition: 'background var(--transition-fast)', position: 'relative' }}>
                <td style={{ ...tdBase, fontWeight: 500 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>{row.campaignName}</span>
                    {hoveredRow === i && (
                      <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--brand-primary)', fontSize: '11px', fontFamily: 'var(--font-sans)', padding: '2px 6px', borderRadius: 'var(--radius-sm)' }}>
                        Explain &rarr;
                      </button>
                    )}
                  </div>
                </td>
                <td style={{ ...tdBase, textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{row.spendFormatted}</td>
                <td style={{ ...tdBase, textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{row.verifiedRevenueFormatted}</td>
                <td style={{ ...tdBase, textAlign: 'right' }}><DiscrepancyCell pct={row.discrepancyPct} status={row.discrepancyStatus} /></td>
                <td style={tdBase}>
                  <MiniRangeBar lower={row.roas?.lower || 0} upper={row.roas?.upper || 0} bucket={row.confidenceBucket} estimate={row.roas?.estimate} />
                </td>
                <td style={{ ...tdBase, textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{row.weightFormatted}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr style={{ background: 'var(--bg-subtle)', borderTop: '2px solid var(--border-default)' }}>
              <td style={{ ...tdBase, fontWeight: 600, borderBottom: 'none' }}>Channel (total)</td>
              <td style={{ ...tdBase, textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600, borderBottom: 'none' }}>{channelAttribution?.spendFormatted || '$22,400'}</td>
              <td style={{ ...tdBase, textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600, borderBottom: 'none' }}>{channelAttribution?.verifiedRevenueFormatted || '$71,680'}</td>
              <td style={{ ...tdBase, textAlign: 'right', borderBottom: 'none' }}>
                <DiscrepancyCell pct={channelAttribution?.discrepancyPct} status={Math.abs(channelAttribution?.discrepancyPct || 0) < 5 ? 'accurate' : Math.abs(channelAttribution?.discrepancyPct || 0) < 25 ? 'flagged' : 'severe'} />
              </td>
              <td style={{ ...tdBase, borderBottom: 'none' }}>
                <MiniRangeBar lower={channelAttribution?.roas?.lower || 0} upper={channelAttribution?.roas?.upper || 0} bucket={channelAttribution?.roas?.bucket} estimate={channelAttribution?.roas?.estimate} />
              </td>
              <td style={{ ...tdBase, textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600, borderBottom: 'none' }}>100%</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
