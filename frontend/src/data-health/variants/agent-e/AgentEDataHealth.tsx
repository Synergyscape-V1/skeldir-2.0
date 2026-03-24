import React, { useMemo, useRef, useState } from "react";
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
import type { DataHealthRendererProps, DataIssue, MetricStatus } from "../../core/types";
import "./styles.css";

/* ── Agent E: Atmos Field ──
   Calm, atmospheric glass-morphism. Ambient halos react to confidence levels.
   Radial metric circles. Animated gradient background. Orb severity indicators. */

function haloClass(status: MetricStatus) {
  return `dhe-halo-${status}`;
}

function ExpandableGuide({ issue }: { issue: DataIssue }) {
  const [open, setOpen] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const hasGuide = (issue.fixGuide?.steps.length ?? 0) > 0;

  if (!hasGuide) return null;

  return (
    <>
      <button
        type="button"
        className="dhe-btn dhe-btn-link"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {open ? "Hide Guide" : "Learn More"}
      </button>
      <div
        ref={contentRef}
        className="dhe-guide-wrap"
        style={{ maxHeight: open ? `${contentRef.current?.scrollHeight ?? 400}px` : "0px" }}
      >
        <div className="dhe-guide">
          <ol>
            {(issue.fixGuide?.steps ?? []).map((step) => (
              <li key={step.stepNumber}>
                <span className="dhe-step-num">{step.stepNumber}</span>
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
      </div>
    </>
  );
}

export function AgentEDataHealth({
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
      <section className="dhe-root dhe-state" aria-busy="true" role="status">
        <div className="dhe-pulse-circles">
          <div className="dhe-pulse-circle" />
          <div className="dhe-pulse-circle" />
          <div className="dhe-pulse-circle" />
        </div>
      </section>
    );
  }

  if (state.type === "error") {
    return (
      <section className="dhe-root dhe-state" role="alert">
        <h2>Unable to Load Data Health</h2>
        <p>{state.error.message}</p>
        <button type="button" className="dhe-btn dhe-btn-primary" onClick={() => void onRetry()}>Retry</button>
      </section>
    );
  }

  if (state.type === "no_data") {
    return (
      <section className="dhe-root dhe-state">
        <h2>No Data Health Metrics Available</h2>
        <p>Connect at least one platform to activate data health tracking.</p>
        <button type="button" className="dhe-btn dhe-btn-primary" onClick={onNavigateToIntegrations}>
          Connect Platform
        </button>
      </section>
    );
  }

  const { data, stale } = state;

  return (
    <section className={`dhe-root dhe-scenario-${scenario}`}>
      <div className="dhe-atmos-bg" aria-hidden="true" />

      {/* ── Header ── */}
      <header className="dhe-header">
        <div>
          <h1 className="dhe-title">Data Health</h1>
          <p className="dhe-sync">Last sync: {formatRelativeTime(data.lastUpdated)}</p>
        </div>
        <button type="button" className="dhe-btn dhe-btn-primary" onClick={() => void onRefresh()}>
          Test All Connections
        </button>
      </header>

      {stale && (
        <div className="dhe-stale" role="status" aria-live="polite">
          <p>Data health last updated over 24 hours ago. Metrics may be outdated.</p>
          <button type="button" className="dhe-btn dhe-btn-secondary" onClick={() => void onRefresh()}>
            Refresh Now
          </button>
        </div>
      )}

      {/* ── System Health — Radial Metrics ── */}
      <section className="dhe-section">
        <h3 className="dhe-section-title">System Health Overview Section</h3>
        <div className="dhe-metric-grid">
          {METRICS.map((metric) => {
            const value = data[metric.key];
            const status = computeMetricStatus(value, metric.target);
            return (
              <article key={metric.key} className={`dhe-metric-card ${haloClass(status)}`}>
                <p className="dhe-metric-label">{metric.title}</p>
                <div className="dhe-radial-value">
                  <strong>{metric.key === "utmConsistency" ? `${value}/100` : `${value}%`}</strong>
                </div>
                <span className={`dhe-badge dhe-badge-${status}`}>{metricConfidence(status)}</span>
                <p className="dhe-metric-desc">{metric.description}</p>
              </article>
            );
          })}
        </div>
      </section>

      {/* ── Platform Integrations — Glass Cards ── */}
      <section className="dhe-section">
        <h3 className="dhe-section-title">Platform Integrations Section</h3>
        <div className="dhe-integration-grid">
          {INTEGRATIONS.map((integration) => {
            const isProblem = integration.level !== "connected";
            return (
              <article
                key={integration.id}
                className={`dhe-glass-card${isProblem ? " dhe-pulse" : ""}`}
              >
                <div className="dhe-integration-head">
                  <img src={integration.icon} alt={`${integration.name} logo`} width={22} height={22} />
                  <h4>{integration.name}</h4>
                </div>
                <span className={`dhe-badge dhe-badge-${integration.level}`}>{integration.status}</span>
                <p className="dhe-integration-detail">{integration.detail}</p>
                <div className="dhe-integration-actions">
                  <button type="button" className="dhe-btn dhe-btn-secondary">{integration.primaryAction}</button>
                  {integration.secondaryAction && (
                    <button type="button" className="dhe-btn dhe-btn-ghost">{integration.secondaryAction}</button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {/* ── Data Quality — Minimal Accordion ── */}
      <section className="dhe-section">
        <h3 className="dhe-section-title">Data Quality Monitor Section</h3>
        {SEVERITY_ORDER.map((severity) => {
          const items = issueGroups[severity];
          if (items.length === 0) return null;
          const isOpen = expanded[severity];
          return (
            <div key={severity} className="dhe-issue-group">
              <button
                type="button"
                className="dhe-group-toggle"
                aria-expanded={isOpen}
                aria-controls={`dhe-group-${severity}`}
                onClick={() => setExpanded((p) => ({ ...p, [severity]: !p[severity] }))}
              >
                <span className="dhe-group-title">
                  {SEVERITY_TITLE[severity]} <span className="dhe-group-count">{items.length}</span>
                </span>
              </button>
              <div id={`dhe-group-${severity}`} hidden={!isOpen} role="region" aria-label={`${severity} issues`}>
                <div className="dhe-issue-list">
                  {items.map((issue) => (
                    <div key={issue.id} className="dhe-issue-item">
                      <div className="dhe-issue-head">
                        <span className={`dhe-orb dhe-orb-${issue.severity}`} aria-hidden="true" />
                        <div className="dhe-issue-info">
                          <p className="dhe-issue-title">{issue.title}</p>
                          <small>{issue.affectedEntity}</small>
                        </div>
                        <span className="dhe-issue-impact">{SEVERITY_IMPACT[issue.severity]}</span>
                        <span className="dhe-issue-status">{SEVERITY_STATUS[issue.severity]}</span>
                        <div className="dhe-issue-actions">
                          <button type="button" className="dhe-btn dhe-btn-pill">
                            {SEVERITY_ACTION[issue.severity]}
                          </button>
                          <ExpandableGuide issue={issue} />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </section>
    </section>
  );
}
