import React, { useState } from 'react';
import { ScenarioAudit } from '../../types/budgetScenarios';
import { Button } from '../ui/Button';

function ChevronDownIcon({ rotated }: { rotated: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      style={{ transform: rotated ? 'rotate(180deg)' : 'none', transition: 'transform 0.25s ease' }}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function DatabaseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

interface StrategicContextSectionProps {
  context: string;
  audit?: ScenarioAudit;
}

export function StrategicContextSection({ context, audit }: StrategicContextSectionProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="scs-card">
      <div className="scs-body">
        <h3 className="scs-title">Strategic Context (AI Analysis)</h3>
        <p className="scs-context">{context}</p>
        {audit && (
          <Button
            variant="ghost"
            size="small"
            onClick={() => setExpanded((v) => !v)}
            className="scs-expand-btn"
          >
            <ChevronDownIcon rotated={expanded} />
            Why these numbers?
          </Button>
        )}
      </div>

      {audit && (
        <div className={`scs-audit ${expanded ? 'scs-audit--expanded' : ''}`}>
          <div className="scs-audit-inner">
            <div className="scs-audit-row">
              <span className="scs-audit-icon"><DatabaseIcon /></span>
              <div>
                <h4 className="scs-audit-heading">Data Sources Verified</h4>
                <p className="scs-audit-text">
                  Analyzed {audit.transactionCount.toLocaleString()} transactions across 4 platforms.
                  Verified revenue: ${(audit.verifiedRevenue / 100).toLocaleString()}.
                </p>
              </div>
            </div>

            <div className="scs-audit-row">
              <span className="scs-audit-icon"><ShieldIcon /></span>
              <div>
                <h4 className="scs-audit-heading">Confidence Model: {audit.attributionModelId}</h4>
                <p className="scs-audit-text">{audit.confidenceExplanation}</p>
              </div>
            </div>

            <div className="scs-audit-row">
              <span className="scs-audit-icon"><EyeIcon /></span>
              <div className="scs-audit-query-col">
                <h4 className="scs-audit-heading">Query Preview</h4>
                <pre className="scs-sql">{audit.sqlPreview}</pre>
                <a href={audit.auditTrailHref} className="scs-audit-link">
                  View Full Audit Trail →
                </a>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
