import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { mockDetailData, formatCurrency } from "./mockInvestigations";

/* ── icons ── */
function IconArrowLeft() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m12 19-7-7 7-7" />
      <path d="M19 12H5" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function IconX() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  );
}

function IconFileText() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
      <path d="M10 9H8" />
      <path d="M16 13H8" />
      <path d="M16 17H8" />
    </svg>
  );
}

function IconChevronDown() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

function IconChevronRight() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}

function IconCopy() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </svg>
  );
}

/* ── Status Badge (reused from Queue but inlined here to keep self-contained) ── */
function StatusBadge({ status }: { status: string }) {
  const iconMap: Record<string, React.FC<{ className?: string }> | null> = {
    pending: null,
    processing: ({ className }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
      </svg>
    ),
    completed: ({ className }) => (
      <img
        src="/checkmark-svgrepo-com.svg"
        className={className}
        width={14}
        height={14}
        alt="Completed"
        aria-hidden="true"
      />
    ),
    failed: ({ className }) => (
      <img
        src="/crossmark-svgrepo-com.svg"
        className={className}
        width={14}
        height={14}
        alt="Failed"
        aria-hidden="true"
      />
    ),
  };

  const labels: Record<string, string> = { pending: "Pending", processing: "Processing", completed: "Completed", failed: "Failed" };
  const Icon = iconMap[status] ?? iconMap.pending;

  return (
    <span className={`inv-status-badge inv-status-badge--${status}`}>
      {Icon != null && <Icon className="inv-status-icon" />}
      {labels[status] || status}
    </span>
  );
}

/* ══════════════════════════════════════ */
/*           MAIN PAGE COMPONENT         */
/* ══════════════════════════════════════ */
export function InvestigationDetail() {
  const { investigationId } = useParams();
  const navigate = useNavigate();

  const [timelineExpanded, setTimelineExpanded] = useState(true);
  const [sqlExpanded, setSqlExpanded] = useState(false);
  const [confirmAction, setConfirmAction] = useState<"approve" | "reject" | null>(null);
  const [reviewStatus, setReviewStatus] = useState(mockDetailData.reviewStatus);
  const [toast, setToast] = useState<string | null>(null);

  const data = mockDetailData;
  const shortId = investigationId?.slice(-4) || "a7f3";

  const handleConfirm = () => {
    if (confirmAction === "approve") {
      setReviewStatus("approved");
      showToast("\u2713 Investigation approved and saved");
    } else {
      setReviewStatus("rejected");
      showToast("Investigation rejected");
    }
    setConfirmAction(null);
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  return (
    <>
      {/* Back nav */}
      <div className="inv-back-nav">
        <button className="inv-back-btn" onClick={() => navigate("/investigations")}>
          <IconArrowLeft />
          Back to Investigations
        </button>
      </div>

      <div className="inv-grid">
        {/* Main content */}
        <div style={{ paddingBottom: 48 }}>
          {/* Header */}
          <div className="inv-detail-header">
            <div>
              <h1 className="inv-detail-title">Investigation #{shortId}</h1>
              <p className="inv-detail-meta">
                Cost: {formatCurrency(data.cost)} | Created:{" "}
                {data.createdAt.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })} at{" "}
                {data.createdAt.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true })}
              </p>
            </div>
            <StatusBadge status={data.status} />
          </div>

          {/* Question card */}
          <div className="inv-question-card">
            <span className="inv-question-label">Original Question</span>
            <p className="inv-question-text">&ldquo;{data.question}&rdquo;</p>
          </div>

          {/* Executive Summary */}
          <div className="inv-summary-card">
            <h2>Executive Summary</h2>
            <p className="inv-summary-text">{data.summary}</p>
            <ol className="inv-findings-list">
              {data.findings?.map((f, i) => (
                <li key={i}>
                  <span className="inv-finding-title">
                    {i + 1}. {f.title}:
                  </span>{" "}
                  {f.detail}
                  <br />
                  <span className={`inv-finding-confidence inv-finding-confidence--${f.confidence.toLowerCase()}`}>
                    Confidence: {f.confidence} ({f.confidencePercent})
                  </span>
                </li>
              ))}
            </ol>
            <div className="inv-summary-footer">
              Overall Confidence: {data.overallConfidence} | Data period: {data.dataPeriod}
            </div>
          </div>

          {/* Timeline */}
          <div className="inv-collapsible">
            <button className="inv-collapsible-header" onClick={() => setTimelineExpanded(!timelineExpanded)}>
              <h2>What happened</h2>
              <span className="inv-collapsible-chevron">{timelineExpanded ? <IconChevronDown /> : <IconChevronRight />}</span>
            </button>
            {timelineExpanded && (
              <div className="inv-collapsible-body">
                <div className="inv-timeline">
                  <div className="inv-timeline-line" />
                  {data.timeline?.map((event, i) => (
                    <div key={i} className="inv-timeline-event">
                      <div className="inv-timeline-dot" />
                      <div className="inv-timeline-row">
                        <span className="inv-timeline-time">{event.timestamp}</span>
                        <span className="inv-timeline-label">{event.label}</span>
                      </div>
                      <p className="inv-timeline-detail">{event.detail}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* SQL Audit */}
          <div className="inv-collapsible">
            <button className="inv-collapsible-header" onClick={() => setSqlExpanded(!sqlExpanded)}>
              <h2>SQL Audit Trail</h2>
              <div className="inv-collapsible-header-right">
                <span className="inv-collapsible-count">{data.sqlQueries?.length} queries</span>
                <span className="inv-collapsible-chevron">{sqlExpanded ? <IconChevronDown /> : <IconChevronRight />}</span>
              </div>
            </button>
            {sqlExpanded && (
              <div className="inv-collapsible-body">
                <p className="inv-sql-intro">Sanitized SQL queries used to produce this result.</p>
                {data.sqlQueries?.map((query, i) => (
                  <div key={i} className="inv-sql-block">
                    <div className="inv-sql-block-header">
                      <span className="inv-sql-block-title">
                        Query {i + 1}: {query.title}
                      </span>
                      <button className="inv-sql-copy-btn">
                        <IconCopy /> Copy
                      </button>
                    </div>
                    <pre className="inv-sql-pre">{query.sql}</pre>
                    <p className="inv-sql-meta">
                      Rows returned: {query.rows} | Execution time: {query.executionTime}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right rail */}
        <div>
          <div className="inv-detail-rail">
            {/* Review actions */}
            <div className="inv-rail-card">
              <h3>Review</h3>
              <p>Review before approving. Skeldir will not auto-apply actions.</p>
              {reviewStatus === "pending" ? (
                <div className="inv-review-actions">
                  <button className="inv-btn-approve" onClick={() => setConfirmAction("approve")}>
                    <IconCheck /> Approve Finding
                  </button>
                  <button className="inv-btn-reject" onClick={() => setConfirmAction("reject")}>
                    <IconX /> Reject
                  </button>
                </div>
              ) : (
                <div className={`inv-review-result inv-review-result--${reviewStatus}`}>
                  {reviewStatus === "approved" ? "\u2713 Approved" : "\u2717 Rejected"}
                </div>
              )}
            </div>

            {/* Export */}
            <div className="inv-rail-card">
              <button className="inv-btn-export">
                <IconFileText /> Export PDF
              </button>
            </div>

            {/* Cost & metadata */}
            <div className="inv-rail-card inv-cost-limits">
              <h3>Cost & Limits</h3>
              <div className="inv-cost-row">
                <span className="inv-cost-row-label">Investigation cost</span>
                <span className="inv-cost-row-value">{formatCurrency(data.cost)}</span>
              </div>
              <div className="inv-cost-row">
                <span className="inv-cost-row-label">Budget remaining</span>
                <span className="inv-cost-row-value">$124.60</span>
              </div>
              <div className="inv-cost-row">
                <span className="inv-cost-row-label">Remaining today</span>
                <span className="inv-cost-row-value">18</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Confirm dialog */}
      {confirmAction && (
        <div className="inv-dialog-overlay" onClick={() => setConfirmAction(null)}>
          <div className="inv-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Confirm decision</h3>
            <p>This records your review decision for this investigation. No changes are applied automatically.</p>
            <div className="inv-dialog-actions">
              <button className="inv-dialog-cancel" onClick={() => setConfirmAction(null)}>
                Cancel
              </button>
              <button className={`inv-dialog-confirm inv-dialog-confirm--${confirmAction}`} onClick={handleConfirm}>
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && <div className="inv-toast">{toast}</div>}
    </>
  );
}
