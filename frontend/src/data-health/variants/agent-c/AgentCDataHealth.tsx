import React, { useMemo, useState } from "react";
import { computeMetricStatus } from "../../core/healthStatus";
import { formatRelativeTime } from "../../core/formatters";
import {
  METRICS,
  INTEGRATIONS,
  SEVERITY_ORDER,
  SEVERITY_TITLE,
  SEVERITY_IMPACT,
  SEVERITY_STATUS,
  SEVERITY_ACTION,
  metricConfidence,
  grouped,
} from "../../core/constants";
import type { DataHealthRendererProps, DataIssue } from "../../core/types";
import "./styles.css";

/* ── Agent C: Ledger Editorial ──
   Financial broadsheet aesthetic. Serif typography, horizontal rules,
   tabular integrations, footnote-style issues, text-link buttons. */

function IssueFootnotes({ issues }: { issues: DataIssue[] }) {
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  return (
    <div className="dhc-footnotes">
      {issues.map((issue) => {
        const hasGuide = (issue.fixGuide?.steps.length ?? 0) > 0;
        const isOpen = expandedRow === issue.id;

        return (
          <div key={issue.id} className={`dhc-footnote dhc-footnote-${issue.severity}`}>
            <div className="dhc-footnote-head">
              <span className={`dhc-dot dhc-dot-${issue.severity}`} aria-hidden="true" />
              <span className="dhc-footnote-sev">{SEVERITY_TITLE[issue.severity]}</span>
              <span className="dhc-footnote-title">{issue.title}</span>
              <span className="dhc-footnote-sep"> — </span>
              <span className="dhc-footnote-impact">{SEVERITY_IMPACT[issue.severity]}</span>
              <span className="dhc-footnote-status">{SEVERITY_STATUS[issue.severity]}</span>
            </div>
            <div className="dhc-footnote-meta">
              <small>{issue.affectedEntity}</small>
              <span className="dhc-footnote-actions">
                <button
                  type="button"
                  className="dhc-link-btn dhc-link-btn-primary"
                  role="button"
                >
                  {SEVERITY_ACTION[issue.severity]}
                </button>
                {hasGuide && (
                  <button
                    type="button"
                    className="dhc-link-btn"
                    role="button"
                    aria-expanded={isOpen}
                    onClick={() => setExpandedRow(isOpen ? null : issue.id)}
                  >
                    {isOpen ? "Hide Guide" : "Learn More"}
                  </button>
                )}
              </span>
            </div>
            {hasGuide && isOpen && (
              <div className="dhc-guide">
                <ol>
                  {(issue.fixGuide?.steps ?? []).map((step) => (
                    <li key={step.stepNumber}>
                      <p>{step.instruction}</p>
                      {step.codeSnippet && <pre><code>{step.codeSnippet}</code></pre>}
                      {step.resourceLink && (
                        <a href={step.resourceLink.url} target="_blank" rel="noopener noreferrer">
                          {step.resourceLink.text}
                        </a>
                      )}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function AgentCDataHealth({
  state,
  scenario,
  onRefresh,
  onNavigateToIntegrations,
  onRetry,
}: DataHealthRendererProps) {
  const [expanded, setExpanded] = useState<Record<DataIssue["severity"], boolean>>({
    critical: true,
    warning: false,
    info: false,
  });

  const issueGroups = useMemo(
    () => (state.type === "steady" ? grouped(state.data.issues) : { critical: [], warning: [], info: [] }),
    [state],
  );

  if (state.type === "initial_loading") {
    return (
      <section className="dhc-root dhc-state" aria-busy="true" role="status">
        <div className="dhc-skeleton dhc-skeleton-text" />
        <div className="dhc-skeleton dhc-skeleton-text dhc-skeleton-short" />
        <div className="dhc-skeleton dhc-skeleton-text" />
      </section>
    );
  }

  if (state.type === "error") {
    return (
      <section className="dhc-root dhc-state" role="alert">
        <h2>Unable to Load Data Health</h2>
        <p>{state.error.message}</p>
        <button type="button" className="dhc-link-btn dhc-link-btn-primary" onClick={() => void onRetry()}>
          Retry
        </button>
      </section>
    );
  }

  if (state.type === "no_data") {
    return (
      <section className="dhc-root dhc-state">
        <h2>No Data Health Metrics Available</h2>
        <p>Connect at least one platform to activate data health tracking.</p>
        <button type="button" className="dhc-link-btn dhc-link-btn-primary" onClick={onNavigateToIntegrations}>
          Connect Platform
        </button>
      </section>
    );
  }

  const { data, stale } = state;

  return (
    <section className={`dhc-root dhc-scenario-${scenario}`}>
      {/* ── Header ── */}
      <header className="dhc-header">
        <div>
          <h1 className="dhc-title">Data Health</h1>
          <p className="dhc-sync">Last sync: {formatRelativeTime(data.lastUpdated)}</p>
        </div>
        <button type="button" className="dhc-link-btn dhc-link-btn-primary" onClick={() => void onRefresh()}>
          Test All Connections
        </button>
      </header>

      <blockquote className="dhc-pullquote" aria-label="Iteration philosophy">
        <p>Separate evidence streams for score, integrations, and quality issue forensics.</p>
      </blockquote>

      {stale && (
        <div className="dhc-stale" role="status" aria-live="polite">
          <p>Data health last updated over 24 hours ago. Metrics may be outdated.</p>
          <button type="button" className="dhc-link-btn" onClick={() => void onRefresh()}>
            Refresh Now
          </button>
        </div>
      )}

      <hr className="dhc-rule" />

      {/* ── System Health — Editorial Columns ── */}
      <section className="dhc-section">
        <h3 className="dhc-section-title">System Health Overview Section</h3>
        <div className="dhc-columns">
          {METRICS.map((metric, idx) => {
            const value = data[metric.key];
            const status = computeMetricStatus(value, metric.target);
            const isLast = idx === METRICS.length - 1;
            return (
              <div key={metric.key} className={`dhc-column${isLast ? "" : " dhc-column-rule"}`}>
                <p className="dhc-metric-label">{metric.title}</p>
                <strong className="dhc-metric-value">
                  {metric.key === "utmConsistency" ? `${value}/100` : `${value}%`}
                </strong>
                <em className={`dhc-confidence dhc-confidence-${status}`}>{metricConfidence(status)}</em>
                <p className="dhc-metric-desc">{metric.description}</p>
              </div>
            );
          })}
        </div>
      </section>

      <hr className="dhc-rule" />

      {/* ── Platform Integrations — Ledger Table ── */}
      <section className="dhc-section">
        <h3 className="dhc-section-title">Platform Integrations Section</h3>
        <table className="dhc-ledger">
          <thead>
            <tr>
              <th>Platform</th>
              <th>Status</th>
              <th>Last Sync</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {INTEGRATIONS.map((integration) => (
              <tr key={integration.id}>
                <td className="dhc-ledger-platform">
                  <img src={integration.icon} alt={`${integration.name} logo`} width={20} height={20} />
                  <span>{integration.name}</span>
                </td>
                <td>
                  <span className={`dhc-dot dhc-dot-${integration.level}`} aria-hidden="true" />
                  {integration.status}
                </td>
                <td className="dhc-ledger-muted">{integration.detail}</td>
                <td>
                  <button type="button" className="dhc-link-btn">
                    {integration.primaryAction}
                  </button>
                  {integration.secondaryAction && (
                    <button type="button" className="dhc-link-btn dhc-link-btn-muted">
                      {integration.secondaryAction}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <hr className="dhc-rule" />

      {/* ── Data Quality — Footnote Style ── */}
      <section className="dhc-section">
        <h3 className="dhc-section-title">Data Quality Monitor Section</h3>
        {SEVERITY_ORDER.map((severity) => {
          const items = issueGroups[severity];
          if (items.length === 0) return null;
          const isOpen = expanded[severity];
          return (
            <div key={severity} className="dhc-issue-group">
              <button
                type="button"
                className="dhc-group-toggle"
                aria-expanded={isOpen}
                aria-controls={`dhc-group-${severity}`}
                onClick={() => setExpanded((p) => ({ ...p, [severity]: !p[severity] }))}
              >
                <strong>{SEVERITY_TITLE[severity]}</strong>
                <span>({items.length})</span>
              </button>
              <div id={`dhc-group-${severity}`} hidden={!isOpen} role="region" aria-label={`${severity} issues`}>
                <IssueFootnotes issues={items} />
              </div>
            </div>
          );
        })}
      </section>
    </section>
  );
}
