import React, { useMemo } from "react";
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

/* ── Agent A: Northstar Grid ──
   Oversized cross-card numerals. Numbers ARE the architecture.
   No accordion — everything visible. Horizontal integration strips. */

function IssueRows({ issues }: { issues: DataIssue[] }) {
  return (
    <div className="dha-rows" role="table" aria-label="Issue rows">
      {issues.map((issue) => {
        const hasGuide = (issue.fixGuide?.steps.length ?? 0) > 0;
        return (
          <div key={issue.id} className={`dha-row dha-row-${issue.severity}`} role="row">
            <div className="dha-cell dha-issue-cell" role="cell">
              <span className={`dha-severity dha-severity-${issue.severity}`}>
                {SEVERITY_TITLE[issue.severity]}
              </span>
              <div>
                <p>{issue.title}</p>
                <small>{issue.affectedEntity}</small>
              </div>
            </div>
            <div className="dha-cell" role="cell">{SEVERITY_IMPACT[issue.severity]}</div>
            <div className="dha-cell" role="cell">{SEVERITY_STATUS[issue.severity]}</div>
            <div className="dha-cell dha-actions" role="cell">
              <button type="button" className="dha-btn dha-btn-primary">
                {SEVERITY_ACTION[issue.severity]}
              </button>
              {hasGuide && (
                <span className="dha-btn dha-btn-link">Learn More</span>
              )}
            </div>
            {hasGuide && (
              <div className="dha-fix" role="row">
                <ol role="list">
                  {(issue.fixGuide?.steps ?? []).map((step) => (
                    <li key={step.stepNumber} role="listitem">
                      <span>{step.stepNumber}</span>
                      <div>
                        <p>{step.instruction}</p>
                        {step.codeSnippet && <pre><code>{step.codeSnippet}</code></pre>}
                        {step.resourceLink && (
                          <a href={step.resourceLink.url} target="_blank" rel="noopener noreferrer">
                            {step.resourceLink.text}
                          </a>
                        )}
                      </div>
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

export function AgentADataHealth({
  state,
  scenario,
  onRefresh,
  onNavigateToIntegrations,
  onRetry,
}: DataHealthRendererProps) {
  const issueGroups = useMemo(
    () => (state.type === "steady" ? grouped(state.data.issues) : { critical: [], warning: [], info: [] }),
    [state],
  );

  if (state.type === "initial_loading") {
    return (
      <section className="dha-root dha-state" aria-busy="true" role="status">
        <div className="dha-skeleton dha-skeleton-hero" />
        <div className="dha-skeleton dha-skeleton-strip" />
        <div className="dha-skeleton dha-skeleton-strip" />
        <div className="dha-skeleton dha-skeleton-strip" />
      </section>
    );
  }

  if (state.type === "error") {
    return (
      <section className="dha-root dha-state" role="alert">
        <h2>Unable to Load Data Health</h2>
        <p>{state.error.message}</p>
        <button type="button" className="dha-btn dha-btn-primary" onClick={() => void onRetry()}>
          Retry
        </button>
      </section>
    );
  }

  if (state.type === "no_data") {
    return (
      <section className="dha-root dha-state">
        <h2>No Data Health Metrics Available</h2>
        <p>Connect at least one platform to activate data health tracking.</p>
        <button type="button" className="dha-btn dha-btn-primary" onClick={onNavigateToIntegrations}>
          Connect Platform
        </button>
      </section>
    );
  }

  const { data, stale } = state;

  return (
    <section className={`dha-root dha-scenario-${scenario}`}>
      {/* ── Header ── */}
      <header className="dha-header">
        <div>
          <h1 className="dha-title">Data Health</h1>
          <p className="dha-sync">Last sync: {formatRelativeTime(data.lastUpdated)}</p>
        </div>
        <button type="button" className="dha-btn dha-btn-primary" onClick={() => void onRefresh()}>
          Test All Connections
        </button>
      </header>

      {stale && (
        <div className="dha-stale" role="status" aria-live="polite">
          <p>Data health last updated over 24 hours ago. Metrics may be outdated.</p>
          <button type="button" className="dha-btn dha-btn-secondary" onClick={() => void onRefresh()}>
            Refresh Now
          </button>
        </div>
      )}

      {/* ── System Health Overview — Triptych ── */}
      <section className="dha-section">
        <div className="dha-section-head">
          <h3>System Health Overview Section</h3>
        </div>
        <div className="dha-triptych">
          {METRICS.map((metric, idx) => {
            const value = data[metric.key];
            const status = computeMetricStatus(value, metric.target);
            const isLast = idx === METRICS.length - 1;
            return (
              <article
                key={metric.key}
                className={`dha-triptych-panel dha-metric-${status}${isLast ? "" : " dha-triptych-seam"}`}
              >
                <p className="dha-metric-label">{metric.title}</p>
                <div className="dha-numeral-hero">
                  <strong>{metric.key === "utmConsistency" ? `${value}/100` : `${value}%`}</strong>
                </div>
                <span className={`dha-badge dha-badge-${status}`}>{metricConfidence(status)}</span>
                <p className="dha-metric-desc">{metric.description}</p>
              </article>
            );
          })}
        </div>
      </section>

      {/* ── Platform Integrations — Horizontal Strips ── */}
      <section className="dha-section">
        <div className="dha-section-head">
          <h3>Platform Integrations Section</h3>
        </div>
        <ul className="dha-strip-list">
          {INTEGRATIONS.map((integration) => (
            <li key={integration.id} className={`dha-strip dha-strip-${integration.level}`}>
              <img src={integration.icon} alt={`${integration.name} logo`} width={24} height={24} />
              <span className="dha-strip-name">{integration.name}</span>
              <span className={`dha-badge dha-badge-${integration.level}`}>{integration.status}</span>
              <span className="dha-strip-detail">{integration.detail}</span>
              <div className="dha-strip-actions">
                <button type="button" className="dha-btn dha-btn-secondary">
                  {integration.primaryAction}
                </button>
                {integration.secondaryAction && (
                  <button type="button" className="dha-btn dha-btn-ghost">
                    {integration.secondaryAction}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>

      {/* ── Data Quality Monitor — Always Visible ── */}
      <section className="dha-section">
        <div className="dha-section-head">
          <h3>Data Quality Monitor Section</h3>
        </div>
        <article className="dha-issues-card">
          <h4>Issue Prioritization Table</h4>
          {SEVERITY_ORDER.map((severity) => {
            const items = issueGroups[severity];
            if (items.length === 0) return null;
            return (
              <section key={severity} className="dha-group">
                <div className="dha-group-header">
                  <span className={`dha-severity-label dha-severity-label-${severity}`}>
                    {SEVERITY_TITLE[severity]}
                  </span>
                  <span className="dha-group-count">{items.length}</span>
                </div>
                <IssueRows issues={items} />
              </section>
            );
          })}
        </article>
      </section>
    </section>
  );
}
