import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';

export default function TopBar({ dateRange, currency, attributionModel, onDateRangeChange, onCurrencyChange, onModelChange }: {
  dateRange: string; currency: string; attributionModel: string;
  onDateRangeChange: (v: string) => void; onCurrencyChange: (v: string) => void; onModelChange: (v: string) => void;
}) {
  const [dateOpen, setDateOpen] = useState(false);
  const [currencyOpen, setCurrencyOpen] = useState(false);
  const [modelOpen, setModelOpen] = useState(false);

  const datePresets = ['Last 7 days', 'Last 14 days', 'Last 30 days', 'Last 60 days', 'Last 90 days'];
  const currencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD'];
  const models = ['Bayesian', 'First-touch', 'Last-touch', 'Linear', 'Time-decay'];
  const isBayesian = attributionModel === 'bayesian';

  /** Neutral dropdown trigger (date, currency). */
  const btnStyle: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: '6px',
    padding: '6px 12px', fontSize: '14px', fontWeight: 500, borderRadius: '6px',
    border: '1px solid #E2E8F0', background: '#fff', cursor: 'pointer',
    color: '#0F172A', fontFamily: 'var(--font-sans)', transition: 'background 150ms ease',
  };

  /** Primary CTA — same as DirectiveCard [Review & Approve]: #2563EB / white. */
  const primaryBtnStyle: React.CSSProperties = {
    ...btnStyle,
    ...(isBayesian
      ? {
        // Slightly darker, bluish-turquoise tint for the header CTA
        color: '#0891B2',
        backgroundColor: 'rgba(8,145,178,0.18)',
        backgroundImage: 'none',
        border: '1px solid rgba(8,145,178,0.35)',
        boxShadow: '0 1px 2px rgba(15,23,42,0.08)',
        backdropFilter: 'blur(6px)',
        WebkitBackdropFilter: 'blur(6px)',
        appearance: 'none',
        WebkitAppearance: 'none',
        fontWeight: 600,
      }
      : {
        background: '#2563EB',
        color: '#fff',
        border: 'none',
      }),
  };

  const dropdownStyle: React.CSSProperties = {
    position: 'absolute', right: 0, top: '100%', marginTop: '4px',
    background: '#fff', border: '1px solid #E2E8F0', borderRadius: '6px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.12)', zIndex: 50, minWidth: '140px',
  };

  const itemStyle: React.CSSProperties = {
    display: 'block', width: '100%', textAlign: 'left' as const,
    padding: '8px 12px', fontSize: '14px', color: '#0F172A',
    background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)',
  };

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      height: '56px',
      borderBottom: '1px solid #E2E8F0',
      background: '#FFFFFF',
      padding: '0 24px',
      position: 'sticky',
      top: 0,
      zIndex: 60,
      flexShrink: 0,
    }}>
      <h1 style={{ fontSize: '20px', fontWeight: 800, color: '#0F172A', letterSpacing: '-0.01em', fontFamily: 'var(--font-sans)', margin: 0 }}>
        Command Center
      </h1>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {/* Date Range */}
        <div style={{ position: 'relative' }}>
          <button style={btnStyle} onClick={() => setDateOpen(!dateOpen)}>
            {dateRange || 'Last 30 days'}
            <ChevronDown size={14} style={{ color: '#94A3B8', transition: 'transform 150ms', transform: dateOpen ? 'rotate(180deg)' : '' }} />
          </button>
          {dateOpen && (
            <div style={dropdownStyle}>
              {datePresets.map(p => (
                <button key={p} style={itemStyle} onClick={() => { onDateRangeChange(p); setDateOpen(false); }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#F1F5F9')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
                  {p}
                </button>
              ))}
            </div>
          )}
        </div>
        {/* Currency */}
        <div style={{ position: 'relative' }}>
          <button style={btnStyle} onClick={() => setCurrencyOpen(!currencyOpen)}>
            {currency || 'USD'}
            <ChevronDown size={14} style={{ color: '#94A3B8', transition: 'transform 150ms', transform: currencyOpen ? 'rotate(180deg)' : '' }} />
          </button>
          {currencyOpen && (
            <div style={dropdownStyle}>
              {currencies.map(c => (
                <button key={c} style={itemStyle} onClick={() => { onCurrencyChange(c); setCurrencyOpen(false); }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#F1F5F9')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
                  {c}
                </button>
              ))}
            </div>
          )}
        </div>
        {/* Attribution Model — primary style to match DirectiveCard CTA */}
        <div style={{ position: 'relative' }}>
          <button style={primaryBtnStyle} onClick={() => setModelOpen(!modelOpen)}>
            <span style={{ fontSize: 11, lineHeight: 1, color: isBayesian ? '#0891B2' : '#FFFFFF' }}>✓</span>
            {attributionModel === 'bayesian' ? 'Bayesian' : attributionModel}
            <ChevronDown
              size={14}
              style={{
                color: isBayesian ? 'rgba(8,145,178,0.78)' : 'rgba(255,255,255,0.9)',
                transition: 'transform 150ms',
                transform: modelOpen ? 'rotate(180deg)' : '',
              }}
            />
          </button>
          {modelOpen && (
            <div style={dropdownStyle}>
              {models.map(m => (
                <button key={m} style={itemStyle} onClick={() => { onModelChange(m.toLowerCase().replace('-', '_')); setModelOpen(false); }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#F1F5F9')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
