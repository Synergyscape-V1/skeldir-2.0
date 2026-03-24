import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, LabelList } from 'recharts';

export default function RevenueWaterfall({ channelAttribution, onExplainClick }: { channelAttribution: any; onExplainClick: () => void }) {
  const {
    claimedRevenue = 82000, claimedRevenueFormatted = '$82,000',
    verifiedRevenue = 71680, verifiedRevenueFormatted = '$71,680',
    discrepancyPct = -12.6, attributionWeight = 0.342,
  } = channelAttribution || {};

  const adjustment = verifiedRevenue - claimedRevenue;
  const attributedRevenue = Math.round(verifiedRevenue * attributionWeight);

  const barData = [
    { name: 'Platform\nClaimed\nRevenue', value: claimedRevenue, start: 0, color: '#1E40AF', label: claimedRevenueFormatted, base: 0, barVal: claimedRevenue },
    { name: 'Verification\nAdjustment', value: Math.abs(adjustment), start: verifiedRevenue, color: '#DC2626', label: `-$${Math.abs(adjustment).toLocaleString()}`, base: verifiedRevenue, barVal: Math.abs(adjustment) },
    { name: 'Verified\nRevenue', value: verifiedRevenue, start: 0, color: '#3B82F6', label: verifiedRevenueFormatted, base: 0, barVal: verifiedRevenue },
    { name: 'Attribution\nAllocation', value: attributedRevenue, start: 0, color: '#60A5FA', label: `\u00D7${(attributionWeight * 100).toFixed(1)}%`, base: 0, barVal: attributedRevenue },
    { name: 'Attributed\nRevenue', value: attributedRevenue, start: 0, color: '#1E40AF', label: `$${attributedRevenue.toLocaleString()}`, base: 0, barVal: attributedRevenue },
  ];

  const maxVal = claimedRevenue * 1.05;

  const NAME_LABELS: Record<string, string> = {
    'Platform\nClaimed\nRevenue': 'Platform Claimed',
    'Verification\nAdjustment': 'Adjustment',
    'Verified\nRevenue': 'Verified',
    'Attribution\nAllocation': 'Allocation',
    'Attributed\nRevenue': 'Attributed',
  };

  const formatTickName = (name: string) => NAME_LABELS[name] ?? name.replace(/\n/g, ' ');

  const getSeverityStyle = (pct: number) => {
    if (pct >= -5) return { color: 'var(--status-verified)', icon: '\u2713' };
    if (pct >= -25) return { color: 'var(--status-caution)', icon: '\u26A0' };
    return { color: 'var(--status-critical)', icon: '\u2715' };
  };
  const severity = getSeverityStyle(discrepancyPct);

  const formatValue = (v: number) => v >= 1000 ? `$${(v / 1000).toFixed(0)}K` : `$${v}`;

  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-sm)',
      padding: '20px 20px 16px', height: '100%', display: 'flex', flexDirection: 'column', minHeight: '320px',
    }}>
      <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)', marginBottom: '12px', flexShrink: 0 }}>
        Revenue Verification Waterfall
      </div>
      <div style={{ flex: 1, minHeight: '220px' }}>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart
            data={barData}
            layout="vertical"
            margin={{ top: 8, right: 78, bottom: 4, left: 6 }}
            barCategoryGap="35%"
          >
            <CartesianGrid strokeDasharray="2 4" stroke="var(--border-default)" horizontal={false} />
            <XAxis
              type="number"
              tickFormatter={formatValue}
              tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'JetBrains Mono' }}
              axisLine={false}
              tickLine={false}
              domain={[0, maxVal]}
            />
            <YAxis
              type="category"
              dataKey="name"
              tickFormatter={formatTickName}
              tick={{ fontSize: 9, fill: 'var(--text-tertiary)', fontFamily: 'JetBrains Mono' }}
              axisLine={false}
              tickLine={false}
              width={72}
              interval={0}
            />
            <Tooltip
              formatter={(value: any, name: any) =>
                name === 'barVal' ? [`$${Number(value).toLocaleString()}`, ''] : [null, null]
              }
              contentStyle={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-default)',
                borderRadius: '4px',
                fontSize: '11px',
                fontFamily: 'JetBrains Mono',
                padding: '4px 6px',
                minWidth: 'auto',
                maxWidth: 160,
              }}
              labelStyle={{
                fontFamily: 'var(--font-sans)',
                fontSize: '10px',
                color: 'var(--text-secondary)',
              }}
              cursor={false}
            />
            <Bar
              dataKey="barVal"
              isAnimationActive={false}
              radius={[0, 3, 3, 0] as any}
              maxBarSize={18}
            >
              {barData.map((entry, index) => (<Cell key={`cell-${index}`} fill={entry.color} />))}
              <LabelList dataKey="label" position="right" offset={8} style={{ fontSize: '10px', fontFamily: 'JetBrains Mono', fill: 'var(--text-primary)', fontWeight: 600 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div style={{
        fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'var(--font-sans)',
        textAlign: 'center', marginBottom: '6px',
        background: 'var(--bg-subtle)', padding: '4px 8px', borderRadius: 'var(--radius-sm)', flexShrink: 0,
      }}>
        Verification Adjustment based on Stripe webhook matching
      </div>
      <div style={{
        marginTop: '6px', paddingTop: '10px', borderTop: '1px solid var(--border-default)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '6px', flexShrink: 0,
      }}>
        <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontFamily: 'var(--font-sans)' }}>
          Discrepancy{' '}
          <span style={{ color: severity.color, fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{discrepancyPct?.toFixed(1)}%</span>
          {' '}{severity.icon}
        </span>
        <button onClick={onExplainClick} style={{
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--brand-primary)', fontSize: '12px', fontFamily: 'var(--font-sans)', padding: 0,
        }}>
          Why does this discrepancy exist? &rarr;
        </button>
      </div>
    </div>
  );
}
