import React from 'react';
import { ProposedChangeRow } from '../../types/budgetScenarios';

function formatCurrency(cents: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

function ArrowUpIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="12" y1="19" x2="12" y2="5" />
      <polyline points="5 12 12 5 19 12" />
    </svg>
  );
}

function ArrowDownIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="12" y1="5" x2="12" y2="19" />
      <polyline points="19 12 12 19 5 12" />
    </svg>
  );
}

interface ProposedChangesTableProps {
  changes: ProposedChangeRow[];
}

export function ProposedChangesTable({ changes }: ProposedChangesTableProps) {
  const sorted = [...changes].sort((a, b) => b.change - a.change);

  return (
    <div className="pct-wrap">
      {/* Mobile cards */}
      <div className="pct-mobile">
        {sorted.map((row) => (
          <div key={row.channelId} className="pct-mobile-card">
            <div className="pct-mobile-header">
              <span className="pct-mobile-channel">{row.channelName}</span>
              <span className={`pct-change-pill ${row.change > 0 ? 'pct-change-pill--up' : row.change < 0 ? 'pct-change-pill--down' : 'pct-change-pill--flat'}`}>
                {row.change > 0 ? '+' : ''}{formatCurrency(row.change)}
              </span>
            </div>
            <div className="pct-mobile-grid">
              <span className="pct-mobile-kv">Current: <strong>{formatCurrency(row.currentSpend)}</strong></span>
              <span className="pct-mobile-kv">Proposed: <strong>{formatCurrency(row.proposedSpend)}</strong></span>
              <span className="pct-mobile-kv pct-mobile-kv--full">
                Expected ROAS: <strong>{row.expectedRoas ? row.expectedRoas.toFixed(2) : '—'}</strong>
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Desktop table */}
      <div className="pct-table-wrap">
        <table className="pct-table">
          <thead>
            <tr className="pct-thead-row">
              <th className="pct-th">Channel</th>
              <th className="pct-th pct-th--right">Current Spend</th>
              <th className="pct-th pct-th--right">Proposed Spend</th>
              <th className="pct-th pct-th--right">Change</th>
              <th className="pct-th pct-th--right">Expected ROAS</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={row.channelId} className="pct-tr">
                <td className="pct-td pct-td--name">{row.channelName}</td>
                <td className="pct-td pct-td--right pct-td--muted">{formatCurrency(row.currentSpend)}</td>
                <td className="pct-td pct-td--right pct-td--bold">{formatCurrency(row.proposedSpend)}</td>
                <td className="pct-td pct-td--right">
                  <span className={`pct-change-pill ${row.change > 0 ? 'pct-change-pill--up' : row.change < 0 ? 'pct-change-pill--down' : 'pct-change-pill--flat'}`}>
                    {row.change > 0 && <ArrowUpIcon />}
                    {row.change < 0 && <ArrowDownIcon />}
                    {row.change !== 0 ? formatCurrency(row.change) : '—'}
                    {row.changePercent !== 0 && (
                      <span className="pct-change-pct">({row.changePercent > 0 ? '+' : ''}{row.changePercent.toFixed(1)}%)</span>
                    )}
                  </span>
                </td>
                <td className="pct-td pct-td--right pct-td--muted">
                  {row.expectedRoas ? row.expectedRoas.toFixed(2) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
