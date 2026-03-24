import React, { useState } from 'react';
import { ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function formatDateLabel(dateStr: string) {
  const parts = dateStr.split('-');
  const month = parseInt(parts[1], 10) - 1;
  return MONTHS[month];
}

function MetricSelector({ selected, onChange }: { selected: string; onChange: (v: string) => void }) {
  const options = [
    { value: 'roas', label: 'ROAS' },
    { value: 'verified_revenue', label: 'Revenue' },
    { value: 'spend', label: 'Spend' },
  ];
  return (
    <div style={{ display: 'flex', gap: '2px', background: 'var(--bg-subtle)', borderRadius: 'var(--radius-sm)', padding: '2px' }}>
      {options.map(opt => (
        <button key={opt.value} onClick={() => onChange(opt.value)} style={{
          padding: '5px 12px', fontSize: '12px', fontWeight: 500, fontFamily: 'var(--font-sans)',
          borderRadius: 'var(--radius-sm)', border: 'none', cursor: 'pointer',
          background: selected === opt.value ? 'var(--brand-primary)' : 'transparent',
          color: selected === opt.value ? '#fff' : 'var(--text-secondary)',
          transition: 'var(--transition-fast)',
        }}>
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const bayesian = payload.find((p: any) => p.dataKey === 'bayesian.estimate');
  const det = payload.find((p: any) => p.dataKey === 'deterministic');
  const upper = payload.find((p: any) => p.dataKey === 'bayesian.upper');
  const lower = payload.find((p: any) => p.dataKey === 'bayesian.lower');
  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-md)',
      padding: '12px', minWidth: '200px', fontSize: '12px',
    }}>
      <div style={{ color: 'var(--text-secondary)', marginBottom: '8px', fontFamily: 'var(--font-sans)' }}>{label}</div>
      {bayesian && (
        <div style={{ marginBottom: '6px' }}>
          <div style={{ color: 'var(--text-secondary)', fontSize: '11px', marginBottom: '3px' }}>Posterior mean (Bayesian)</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '3px', background: 'var(--data-1)', display: 'inline-block', borderRadius: '2px' }} />
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontSize: '13px', fontWeight: 600 }}>{bayesian.value?.toFixed(2)}</span>
          </div>
          {upper && lower && (
            <div style={{ color: 'var(--text-tertiary)', fontSize: '11px', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
              80% CI: {lower.value?.toFixed(2)} &ndash; {upper.value?.toFixed(2)}
            </div>
          )}
        </div>
      )}
      {det && (
        <div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '11px', marginBottom: '3px' }}>Point estimate (Deterministic)</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '2px', borderTop: '2px dashed var(--text-tertiary)', display: 'inline-block' }} />
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)', fontSize: '12px' }}>{det.value?.toFixed(2)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function CustomLegend({ bandLabel }: { bandLabel?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '24px', justifyContent: 'center', marginTop: '12px', flexWrap: 'wrap' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-secondary)', fontFamily: 'var(--font-sans)' }}>
        <svg width="20" height="3"><line x1="0" y1="1.5" x2="20" y2="1.5" stroke="var(--data-1)" strokeWidth="2" /></svg>
        Posterior mean (Bayesian)
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-secondary)', fontFamily: 'var(--font-sans)' }}>
        <svg width="20" height="12"><rect x="0" y="0" width="20" height="12" fill="var(--data-range-fill)" stroke="var(--data-range-stroke)" strokeWidth="1" /></svg>
        {bandLabel || '80% highest density interval Bayesian model'}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-secondary)', fontFamily: 'var(--font-sans)' }}>
        <svg width="20" height="3"><line x1="0" y1="1.5" x2="20" y2="1.5" stroke="var(--text-tertiary)" strokeWidth="1.5" strokeDasharray="4 2" /></svg>
        Point estimate (Deterministic)
      </div>
    </div>
  );
}

function flattenData(data: any[]) {
  return data.map(d => ({
    ...d,
    'bayesian.estimate': d.bayesian?.estimate ?? null,
    'bayesian.lower': d.bayesian?.lower ?? null,
    'bayesian.upper': d.bayesian?.upper ?? null,
  }));
}

function getXAxisTicks(data: any[]) {
  const seen = new Set<string>();
  return data.reduce((acc: string[], d) => {
    const month = d.date.slice(0, 7);
    if (!seen.has(month)) { seen.add(month); acc.push(d.date); }
    return acc;
  }, []);
}

export default function TimeSeriesChart({ data }: { data: any[] }) {
  const [selectedMetric, setSelectedMetric] = useState('roas');
  const flatData = flattenData(data || []);
  const ticks = getXAxisTicks(flatData);

  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-sm)',
      padding: '20px 24px 16px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <span style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)' }}>Performance Over Time</span>
        <MetricSelector selected={selectedMetric} onChange={setSelectedMetric} />
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '4px' }}>
        <div style={{
          writingMode: 'vertical-rl', textOrientation: 'mixed', transform: 'rotate(180deg)',
          fontSize: '10px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)',
          marginRight: '4px', marginTop: '8px', letterSpacing: '0.05em', textTransform: 'uppercase',
        }}>
          {selectedMetric === 'roas' ? 'ROAS' : selectedMetric === 'verified_revenue' ? 'Revenue' : 'Spend'}
        </div>
        <div style={{ flex: 1, height: '280px', position: 'relative' }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={flatData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <Area dataKey="bayesian.upper" stroke="none" strokeWidth={0} fill="var(--data-range-fill)" fillOpacity={1} connectNulls={false} legendType="none" activeDot={false} isAnimationActive={false} name="ci-upper" />
              <Area dataKey="bayesian.lower" stroke="rgba(59,130,246,0.35)" strokeWidth={0} fill="var(--bg-surface)" fillOpacity={1} connectNulls={false} legendType="none" activeDot={false} isAnimationActive={false} name="ci-lower" />
              <Line dataKey="bayesian.estimate" stroke="var(--data-1)" strokeWidth={2} dot={false} connectNulls={false} name="Posterior mean (Bayesian)" activeDot={{ r: 4, fill: 'var(--data-1)', stroke: 'var(--bg-surface)', strokeWidth: 2 }} isAnimationActive={false} />
              <Line dataKey="deterministic" stroke="var(--text-tertiary)" strokeWidth={1.5} strokeDasharray="4 2" dot={false} connectNulls={true} name="Point estimate (Deterministic)" activeDot={{ r: 3, fill: 'var(--text-tertiary)', stroke: 'var(--bg-surface)', strokeWidth: 2 }} isAnimationActive={false} />
              <XAxis dataKey="date" ticks={ticks} tickFormatter={formatDateLabel} tick={{ fontSize: 11, fill: 'var(--text-tertiary)', fontFamily: 'JetBrains Mono' }} axisLine={{ stroke: 'var(--border-default)' }} tickLine={false} />
              <YAxis tickFormatter={(v: number) => v?.toFixed(1)} tick={{ fontSize: 11, fill: 'var(--text-tertiary)', fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} width={36} domain={['auto', 'auto']} />
              <CartesianGrid strokeDasharray="2 4" stroke="var(--border-default)" vertical={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend content={() => null} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
      <CustomLegend bandLabel="80% highest density interval Bayesian model" />
    </div>
  );
}
