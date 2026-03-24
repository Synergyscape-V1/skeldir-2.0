import React from "react";
import type { DataHealthIssue } from "./types";

interface FixGuideProps {
  issue?: DataHealthIssue | null;
  onContactSupport?: () => void;
}

/* ── Inline SVG icons ─────────────────────────────────────── */

function HelpCircleIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="dhd-fix-empty-icon">
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function MessageCircleIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="dhd-icon-xs">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
    </svg>
  );
}

function AlertTriangleIcon() {
  return (
    <img
      src="/warning-svgrepo-com.svg"
      className="dhd-fix-alert-icon"
      width={20}
      height={20}
      alt="Warning"
      aria-hidden="true"
    />
  );
}

function ClockIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="dhd-fix-footer-icon">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function HashIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="dhd-fix-footer-icon">
      <line x1="4" y1="9" x2="20" y2="9" />
      <line x1="4" y1="15" x2="20" y2="15" />
      <line x1="10" y1="3" x2="8" y2="21" />
      <line x1="16" y1="3" x2="14" y2="21" />
    </svg>
  );
}

export function FixGuide({ issue, onContactSupport }: FixGuideProps) {
  /* ── Empty state ─────────────────────────────────────────── */
  if (!issue) {
    return (
      <div className="dhd-fix-panel">
        <div className="dhd-fix-panel-header">
          <h2 className="dhd-fix-panel-title">Fix Guide</h2>
          <button
            type="button"
            className="dhd-action-btn"
            onClick={onContactSupport}
          >
            <MessageCircleIcon />
            Contact Support
          </button>
        </div>
        <div className="dhd-fix-empty">
          <HelpCircleIcon />
          <h3 className="dhd-fix-empty-title">Select an Issue</h3>
          <p className="dhd-fix-empty-desc">
            Choose an issue from the list to see step-by-step troubleshooting and the fastest next action.
          </p>
        </div>
      </div>
    );
  }

  /* ── Issue detail state ──────────────────────────────────── */
  return (
    <div className="dhd-fix-panel">
      <div className="dhd-fix-panel-header">
        <h2 className="dhd-fix-panel-title">Fix Guide</h2>
        <button
          type="button"
          className="dhd-action-btn"
          onClick={onContactSupport}
        >
          <MessageCircleIcon />
          Contact Support
        </button>
      </div>

      <div className="dhd-fix-body">
        {/* Data quality alert banner */}
        <div className="dhd-fix-alert">
          <AlertTriangleIcon />
          <div>
            <p className="dhd-fix-alert-title">Data Quality Alert</p>
            <p className="dhd-fix-alert-desc">
              This issue may impact your revenue reporting accuracy.
            </p>
          </div>
        </div>

        {/* Problem */}
        <section>
          <h3 className="dhd-fix-section-label">Problem</h3>
          <p className="dhd-fix-section-text">{issue.problem}</p>
        </section>

        {/* Why */}
        <section>
          <h3 className="dhd-fix-section-label">Why this happened</h3>
          <p className="dhd-fix-section-text">{issue.why}</p>
        </section>

        {/* What to do */}
        <section>
          <h3 className="dhd-fix-section-label">What to do</h3>
          <ol className="dhd-fix-steps">
            {issue.whatToDo.map((step) => (
              <li key={step.stepId} className="dhd-fix-step">
                <span>{step.text}</span>
                {step.primaryAction && (
                  <button type="button" className="dhd-fix-step-action">
                    {step.primaryAction.label}
                  </button>
                )}
              </li>
            ))}
          </ol>
        </section>

        {/* Footer metadata */}
        <div className="dhd-fix-footer">
          {issue.fixBy && (
            <div className="dhd-fix-footer-row">
              <ClockIcon />
              <span className="dhd-fix-footer-label">Fix by:</span>
              <span className="dhd-fix-footer-value">{issue.fixBy}</span>
            </div>
          )}
          <div className="dhd-fix-footer-row">
            <HashIcon />
            <span className="dhd-fix-footer-label">Error ID:</span>
            <span className="dhd-fix-footer-value">{issue.correlationId ?? issue.id}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
