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

/* ── Agent D: Modular Atlas ──
   Blueprint lattice grid. Zero-radius docking cards. Progress bars.
   Tabbed severity groups. Module-label section headings. */

function IssueRows({ issues }: { issues: DataIssue[] }) {
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  return (
    <div className="dhd-rows" role="table" aria-label="Issue rows">
      {issues.map((issue) => {
        const hasGuide = (issue.fixGuide?.steps.length ?? 0) > 0;
        const isOpen = expandedRow === issue.id;
        return (
          <div key={issue.id} className={`dhd-row dhd-row-${issue.severity}`} role="row">
            <div className="dhd-cell dhd-issue-cell" role="cell">
              <span className={`dhd-severity dhd-severity-${issue.severity}`}>
                {SEVERITY_TITLE[issue.severity]}
              </span>
              <div>
                <p>{issue.title}</p>
                <small>{issue.affectedEntity}</small>
              </div>
            </div>
            <div className="dhd-cell" role="cell">{SEVERITY_IMPACT[issue.severity]}</div>
            <div className="dhd-cell" role="cell">{SEVERITY_STATUS[issue.severity]}</div>
            <div className="dhd-cell dhd-actions" role="cell">
              <button type="button" className="dhd-btn dhd-btn-primary">
                {SEVERITY_ACTION[issue.severity]}
              </button>
              {hasGuide && (
                <button
                  type="button"
                  className="dhd-btn dhd-btn-link"
                  aria-expanded={isOpen}
                  onClick={() => setExpandedRow(isOpen ? null : issue.id)}
                >
                  {isOpen ? "Hide Guide" : "Learn More"}
                </button>
              )}
            </div>
            {hasGuide && isOpen && (
              <div className="dhd-fix" role="row">
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

export function AgentDDataHealth({
  state,
  scenario,
  onRefresh,
  onNavigateToIntegrations,
  onRetry,
}: DataHealthRendererProps) {
  const [activeTab, setActiveTab] = useState<DataIssue["severity"]>("critical");

  const issueGroups = useMemo(
    () => (state.type === "steady" ? grouped(state.data.issues) : { critical: [], warning: [], info: [] }),
    [state],
  );

  if (state.type === "initial_loading") {
    return (
      <section className="dhd-root dhd-state" aria-busy="true" role="status">
        <div className="dhd-lattice-skeleton">
          <div className="dhd-skeleton" />
          <div className="dhd-skeleton" />
          <div className="dhd-skeleton" />
        </div>
      </section>
    );
  }

  if (state.type === "error") {
    return (
      <section className="dhd-root dhd-state" role="alert">
        <h2>Unable to Load Data Health</h2>
        <p>{state.error.message}</p>
        <button type="button" className="dhd-btn dhd-btn-primary" onClick={() => void onRetry()}>Retry</button>
      </section>
    );
  }

  if (state.type === "no_data") {
    return (
      <section className="dhd-root dhd-state">
        <h2>No Data Health Metrics Available</h2>
        <p>Connect at least one platform to activate data health tracking.</p>
        <button type="button" className="dhd-btn dhd-btn-primary" onClick={onNavigateToIntegrations}>
          Connect Platform
        </button>
      </section>
    );
  }

  const { data, stale } = state;

  const availableTabs = SEVERITY_ORDER.filter((s) => issueGroups[s].length > 0);
  const effectiveTab = availableTabs.includes(activeTab) ? activeTab : (availableTabs[0] ?? "critical");

  return (
    <section className={`dhd-root dhd-scenario-${scenario}`}>
      {/* ── Header ── */}
      <header className="dhd-header dhd-module">
        <div>
          <h1 className="dhd-title">Data Health</h1>
          <p className="dhd-sync">Last sync: {formatRelativeTime(data.lastUpdated)}</p>
        </div>
        <button type="button" className="dhd-btn dhd-btn-primary" onClick={() => void onRefresh()}>
          Test All Connections
        </button>
      </header>

      {stale && (
        <div className="dhd-stale dhd-module" role="status" aria-live="polite">
          <p>Data health last updated over 24 hours ago. Metrics may be outdated.</p>
          <button type="button" className="dhd-btn dhd-btn-secondary" onClick={() => void onRefresh()}>
            Refresh Now
          </button>
        </div>
      )}

      {/* ── Metrics Lattice ── */}
      <div className="dhd-module-label">System Health Overview Section</div>
      <div className="dhd-lattice-metrics">
        {METRICS.map((metric) => {
          const value = data[metric.key];
          const status = computeMetricStatus(value, metric.target);
          return (
            <article key={metric.key} className="dhd-metric-module dhd-module">
              <p className="dhd-metric-label">{metric.title}</p>
              <div className="dhd-metric-row">
                <strong className="dhd-metric-value">
                  {metric.key === "utmConsistency" ? `${value}/100` : `${value}%`}
                </strong>
                <span className={`dhd-badge dhd-badge-${status}`}>{metricConfidence(status)}</span>
              </div>
              <div className="dhd-progress">
                <div
                  className={`dhd-progress-fill dhd-progress-${status}`}
                  style={{ width: `${value}%` }}
                />
              </div>
              <p className="dhd-metric-desc">{metric.description}</p>
            </article>
          );
        })}
      </div>

      {/* ── Integration Lattice ── */}
      <div className="dhd-module-label">Platform Integrations Section</div>
      <div className="dhd-lattice-integrations">
        {INTEGRATIONS.map((integration) => (
          <article key={integration.id} className="dhd-integration-module dhd-module">
            <div className={`dhd-status-strip dhd-strip-${integration.level}`} />
            <div className="dhd-integration-body">
              <div className="dhd-integration-head">
                <img src={integration.icon} alt={`${integration.name} logo`} width={22} height={22} />
                <h4>{integration.name}</h4>
              </div>
              <span className={`dhd-badge dhd-badge-${integration.level}`}>{integration.status}</span>
              <p className="dhd-integration-detail">{integration.detail}</p>
              <div className="dhd-integration-actions">
                <button type="button" className="dhd-btn dhd-btn-secondary">{integration.primaryAction}</button>
                {integration.secondaryAction && (
                  <button type="button" className="dhd-btn dhd-btn-ghost">{integration.secondaryAction}</button>
                )}
              </div>
            </div>
          </article>
        ))}
      </div>

      {/* ── Issues — Tabbed ── */}
      <div className="dhd-module-label">Data Quality Monitor Section</div>
      <article className="dhd-issues-module dhd-module">
        <div className="dhd-tab-bar" role="tablist" aria-label="Issue severity tabs">
          {SEVERITY_ORDER.map((severity) => {
            const count = issueGroups[severity].length;
            if (count === 0) return null;
            const isActive = effectiveTab === severity;
            return (
              <button
                key={severity}
                type="button"
                role="tab"
                aria-selected={isActive}
                aria-controls={`dhd-tabpanel-${severity}`}
                className={`dhd-tab${isActive ? " dhd-tab-active" : ""}`}
                onClick={() => setActiveTab(severity)}
              >
                {SEVERITY_TITLE[severity]}
                <span className={`dhd-tab-count dhd-tab-count-${severity}`}>{count}</span>
              </button>
            );
          })}
        </div>
        {SEVERITY_ORDER.map((severity) => {
          const items = issueGroups[severity];
          if (items.length === 0 || effectiveTab !== severity) return null;
          return (
            <div
              key={severity}
              id={`dhd-tabpanel-${severity}`}
              role="tabpanel"
              aria-label={`${severity} issues`}
            >
              <IssueRows issues={items} />
            </div>
          );
        })}
      </article>
    </section>
  );
}
