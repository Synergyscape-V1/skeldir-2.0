import React, { useState } from "react";
import type { DataHealthIssue } from "./types";

interface PriorityIssuesSectionProps {
  issues: DataHealthIssue[];
  onRefresh: () => void;
  onSelectIssue: (issue: DataHealthIssue) => void;
  onNavigateToIntegrations: () => void;
  selectedIssueId?: string;
}

type FilterType = "All" | "Critical" | "Warning" | "Info";

/* ── Inline SVG icons ─────────────────────────────────────── */

function RefreshIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="dhd-icon-xs">
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
    </svg>
  );
}

function CheckCircleIcon() {
  return (
    <img
      src="/checkmark-svgrepo-com.svg"
      className="dhd-issues-empty-icon"
      width={24}
      height={24}
      alt="No issues"
      aria-hidden="true"
    />
  );
}

export function PriorityIssuesSection({
  issues,
  onRefresh,
  onSelectIssue,
  onNavigateToIntegrations,
  selectedIssueId,
}: PriorityIssuesSectionProps) {
  const [filter, setFilter] = useState<FilterType>("All");

  const filteredIssues = issues.filter((issue) => {
    if (filter === "All") return true;
    return issue.severity === filter.toLowerCase();
  });

  const pillClass = (f: FilterType): string => {
    const isActive = filter === f;
    if (!isActive) return "dhd-filter-pill dhd-filter-pill-default";
    if (f === "All") return "dhd-filter-pill dhd-filter-pill-active-all";
    if (f === "Critical") return "dhd-filter-pill dhd-filter-pill-active-critical";
    if (f === "Warning") return "dhd-filter-pill dhd-filter-pill-active-warning";
    return "dhd-filter-pill dhd-filter-pill-active-info";
  };

  const itemClass = (issue: DataHealthIssue): string => {
    const severityClass = `dhd-issue-item-${issue.severity}`;
    const selectedClass = selectedIssueId === issue.id ? " dhd-issue-item-selected" : "";
    return `dhd-issue-item ${severityClass}${selectedClass}`;
  };

  return (
    <div className="dhd-issues-panel">
      {/* Header */}
      <div className="dhd-issues-panel-header">
        <div className="dhd-issues-title-row">
          <h2 className="dhd-issues-title">Priority Issues</h2>
          <div className="dhd-issues-header-actions">
            <button
              type="button"
              className="dhd-action-btn"
              onClick={onNavigateToIntegrations}
            >
              View Integrations
            </button>
            <button
              type="button"
              className="dhd-action-btn"
              onClick={onRefresh}
            >
              <RefreshIcon />
              Refresh
            </button>
          </div>
        </div>

        <div className="dhd-filter-pills">
          {(["All", "Critical", "Warning", "Info"] as FilterType[]).map((f) => (
            <button
              key={f}
              type="button"
              className={pillClass(f)}
              onClick={() => setFilter(f)}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Issue list */}
      <div className="dhd-issues-list">
        {filteredIssues.length === 0 ? (
          <div className="dhd-issues-empty">
            <CheckCircleIcon />
            <p className="dhd-issues-empty-text">
              No {filter !== "All" ? filter.toLowerCase() : ""} issues found
            </p>
          </div>
        ) : (
          <>
            {filteredIssues.map((issue) => (
              <div
                key={issue.id}
                className={itemClass(issue)}
                onClick={() => onSelectIssue(issue)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelectIssue(issue);
                  }
                }}
              >
                <div className="dhd-issue-item-inner">
                  <div className="dhd-issue-item-content">
                    <h3 className="dhd-issue-item-title">{issue.title}</h3>
                    <p className="dhd-issue-item-description">{issue.description}</p>
                    {issue.impact && (
                      <p className="dhd-issue-item-impact">{issue.impact}</p>
                    )}
                  </div>

                  <div className="dhd-issue-item-actions">
                    <button
                      type="button"
                      className="dhd-btn dhd-btn-primary"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectIssue(issue);
                      }}
                    >
                      Fix Now
                    </button>
                    <button
                      type="button"
                      className="dhd-btn dhd-btn-secondary"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectIssue(issue);
                      }}
                    >
                      Learn More
                    </button>
                  </div>
                </div>
              </div>
            ))}

            <button type="button" className="dhd-load-more-btn">
              Load more
            </button>
          </>
        )}
      </div>
    </div>
  );
}
