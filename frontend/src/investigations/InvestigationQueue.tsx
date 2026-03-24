import React, { useMemo, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  mockInvestigations,
  formatRelativeTime,
  formatCurrency,
  type Investigation,
  type InvestigationStatus,
  type InvestigationPriority,
} from "./mockInvestigations";

/* ── constants ── */
const ITEMS_PER_PAGE = 12;

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
];

const SORT_OPTIONS = [
  { value: "created_at-desc", label: "Newest" },
  { value: "created_at-asc", label: "Oldest" },
  { value: "cost-desc", label: "Highest cost" },
  { value: "cost-asc", label: "Lowest cost" },
];

const EXAMPLE_QUESTIONS = [
  "Why did verified revenue change week-over-week?",
  "Which channel drove the largest ROAS shift in the last 30 days?",
  "Did conversion volume drop because spend changed or efficiency changed?",
  "Explain the confidence level for the current ROAS estimate.",
  "What data-quality issue could explain a sudden performance anomaly?",
  "Summarize the top drivers of spend inefficiency this month.",
];

/* ── icons (inline SVG, except Alert which uses branded asset) ── */
function IconAlertTriangle({ className }: { className?: string }) {
  return (
    <img
      src="/warning-svgrepo-com.svg"
      className={className}
      width={14}
      height={14}
      alt="Pending"
      aria-hidden="true"
    />
  );
}

function IconClock({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function IconCheckCircle({ className }: { className?: string }) {
  return (
    <img
      src="/checkmark-svgrepo-com.svg"
      className={className}
      width={14}
      height={14}
      alt="Completed"
      aria-hidden="true"
    />
  );
}

function IconXCircle({ className }: { className?: string }) {
  return (
    <img
      src="/crossmark-svgrepo-com.svg"
      className={className}
      width={14}
      height={14}
      alt="Failed"
      aria-hidden="true"
    />
  );
}

function IconChevronRight() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}

function IconHelpCircle() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <path d="M12 17h.01" />
    </svg>
  );
}

function IconUser() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

/* ── Status Badge ── */
const STATUS_CONFIG: Record<InvestigationStatus, { Icon: React.FC<{ className?: string }>; label: string; anim: string }> = {
  pending: { Icon: IconAlertTriangle, label: "Pending", anim: "inv-status-icon--pulse" },
  processing: { Icon: IconClock, label: "Processing", anim: "inv-status-icon--spin" },
  completed: { Icon: IconCheckCircle, label: "Completed", anim: "" },
  failed: { Icon: IconXCircle, label: "Failed", anim: "" },
};

function StatusBadge({ status }: { status: InvestigationStatus }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <span className={`inv-status-badge inv-status-badge--${status}`}>
      <cfg.Icon className={`inv-status-icon ${cfg.anim}`} />
      {cfg.label}
    </span>
  );
}

/* ── Priority Badge ── */
function PriorityBadge({ priority }: { priority: InvestigationPriority }) {
  return (
    <span className={`inv-priority-badge inv-priority-badge--${priority}`}>
      <span className={`inv-priority-dot inv-priority-dot--${priority}`} />
      {priority === "user" ? "User" : "Auto"}
    </span>
  );
}

/* ── Filter Bar ── */
function FilterBar() {
  const [searchParams, setSearchParams] = useSearchParams();
  const currentStatus = searchParams.get("status") || "all";
  const currentSort = searchParams.get("sort") || "created_at";
  const currentDir = searchParams.get("dir") || "desc";
  const sortKey = `${currentSort}-${currentDir}`;

  const setFilter = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams);
    if ((key === "status" && value === "all") || !value) {
      params.delete(key);
    } else {
      params.set(key, value);
    }
    setSearchParams(params, { replace: true });
  };

  const handleSortChange = (value: string) => {
    const [sort, dir] = value.split("-");
    const params = new URLSearchParams(searchParams);
    params.set("sort", sort);
    params.set("dir", dir);
    setSearchParams(params, { replace: true });
  };

  return (
    <div className="inv-filter-bar">
      <div className="inv-filter-chips">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            className="inv-filter-chip"
            data-active={currentStatus === f.value}
            data-status={f.value}
            onClick={() => setFilter("status", f.value)}
          >
            {f.value === "pending" && currentStatus === "pending" && "\u26A0 "}
            {f.value === "completed" && currentStatus === "completed" && "\u2713 "}
            {f.label}
          </button>
        ))}
      </div>
      <div className="inv-filter-sort">
        <span className="inv-filter-sort-label">Sort</span>
        <select className="inv-sort-select" value={sortKey} onChange={(e) => handleSortChange(e.target.value)}>
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

/* ── Investigation Row ── */
function InvestigationRow({ investigation }: { investigation: Investigation }) {
  const navigate = useNavigate();

  return (
    <button className="inv-row" onClick={() => navigate(`/investigations/${investigation.id}`)}>
      <div>
        <StatusBadge status={investigation.status} />
      </div>
      <div className="inv-row-question">
        <p className="inv-row-question-text">{investigation.question}</p>
        <div className="inv-row-meta">
          <span className="inv-row-meta-text">Created {formatRelativeTime(investigation.createdAt)}</span>
          {investigation.failureReason && <span className="inv-row-meta-error">Failed \u2014 {investigation.failureReason}</span>}
          {investigation.piiRemoved && (
            <span className="inv-row-meta-pii">
              <svg viewBox="0 0 16 16" fill="currentColor">
                <path d="M8 1a3.5 3.5 0 0 0-3.5 3.5V6H3.5A1.5 1.5 0 0 0 2 7.5v6A1.5 1.5 0 0 0 3.5 15h9a1.5 1.5 0 0 0 1.5-1.5v-6A1.5 1.5 0 0 0 12.5 6h-1V4.5A3.5 3.5 0 0 0 8 1zm2.5 5h-5V4.5a2.5 2.5 0 0 1 5 0V6z" />
              </svg>
              PII removed
            </span>
          )}
        </div>
      </div>
      <div className="inv-row-cost">{investigation.cost > 0 ? formatCurrency(investigation.cost) : "\u2014"}</div>
      <div>
        <PriorityBadge priority={investigation.priority} />
      </div>
      <div className="inv-row-action">
        {investigation.status === "failed" ? <span className="inv-row-retry">Retry</span> : <IconChevronRight />}
      </div>
    </button>
  );
}

/* ── Pagination ── */
function InvestigationPagination({ totalItems, itemsPerPage }: { totalItems: number; itemsPerPage: number }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const currentPage = parseInt(searchParams.get("page") || "1", 10);
  const totalPages = Math.ceil(totalItems / itemsPerPage);

  if (totalPages <= 1) return null;

  const setPage = (page: number) => {
    const params = new URLSearchParams(searchParams);
    params.set("page", String(page));
    setSearchParams(params, { replace: true });
  };

  return (
    <div className="inv-pagination">
      <span className="inv-pagination-info">Showing {Math.min(itemsPerPage, totalItems)} of {totalItems} investigations</span>
      <div className="inv-pagination-buttons">
        <button className="inv-pagination-btn" onClick={() => setPage(Math.max(1, currentPage - 1))} disabled={currentPage === 1}>
          Prev
        </button>
        {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
          <button key={page} className="inv-pagination-page" data-active={page === currentPage} onClick={() => setPage(page)}>
            {page}
          </button>
        ))}
        <button className="inv-pagination-btn" onClick={() => setPage(Math.min(totalPages, currentPage + 1))} disabled={currentPage === totalPages}>
          Next
        </button>
      </div>
    </div>
  );
}

/* ── Ask Skeldir ── */
function AskSkeldir() {
  const [question, setQuestion] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const estimatedCost = question.length === 0 ? 0 : question.length < 50 ? 0.2 : question.length < 150 ? 0.4 : 0.8;

  const handleSubmit = () => {
    if (!question.trim()) return;
    setIsSubmitting(true);
    setTimeout(() => {
      setIsSubmitting(false);
      setQuestion("");
    }, 1500);
  };

  return (
    <div className="inv-ask">
      <h2 className="inv-ask-title">Ask Skeldir</h2>

      <div className="inv-ask-field">
        <label className="inv-ask-label">Question Hypothesis</label>
        <textarea
          className="inv-ask-textarea"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Describe what you want explained. No names/emails\u2014Skeldir removes PII automatically."
        />
      </div>

      <div className="inv-ask-examples">
        {EXAMPLE_QUESTIONS.map((eq) => (
          <button key={eq} className="inv-ask-example" onClick={() => setQuestion(eq)}>
            {eq}
          </button>
        ))}
      </div>

      <div className="inv-ask-cost">
        <div className="inv-ask-cost-row">
          <span className="inv-ask-cost-label">Estimated investigation cost</span>
          <span className="inv-ask-cost-value">
            {question.length > 0 ? `$${estimatedCost.toFixed(2)}` : "\u2014"}
          </span>
        </div>
        <div className="inv-ask-cost-row">
          <span className="inv-ask-cost-label">Investigations remaining today:</span>
          <span className="inv-ask-cost-value inv-ask-cost-value--sm">18</span>
        </div>
      </div>

      <button className="inv-ask-submit" disabled={!question.trim() || isSubmitting} onClick={handleSubmit}>
        {isSubmitting ? (
          <span className="inv-ask-submit-spinner">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path style={{ opacity: 0.75 }} fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Submitting\u2026
          </span>
        ) : (
          "Submit Investigation"
        )}
      </button>

      <p className="inv-ask-footer">You'll review results in the Investigations list. No live chat.</p>
    </div>
  );
}

/* ══════════════════════════════════════ */
/*           MAIN PAGE COMPONENT         */
/* ══════════════════════════════════════ */
export function InvestigationQueue() {
  const [searchParams] = useSearchParams();
  const statusFilter = searchParams.get("status") || "all";
  const sort = searchParams.get("sort") || "created_at";
  const dir = searchParams.get("dir") || "desc";
  const page = parseInt(searchParams.get("page") || "1", 10);

  const filtered = useMemo(() => {
    let items = [...mockInvestigations];

    if (statusFilter !== "all") {
      items = items.filter((inv) => inv.status === statusFilter);
    }

    items.sort((a, b) => {
      if (sort === "cost") {
        return dir === "asc" ? a.cost - b.cost : b.cost - a.cost;
      }
      return dir === "asc" ? a.createdAt.getTime() - b.createdAt.getTime() : b.createdAt.getTime() - a.createdAt.getTime();
    });

    return items;
  }, [statusFilter, sort, dir]);

  const totalItems = 47; // mock total
  const paginated = filtered.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);

  return (
    <>
      {/* Page header */}
      <div className="inv-page-header">
        <h1>Investigations</h1>
        <div className="inv-page-header-actions">
          <button className="inv-header-btn">
            <IconHelpCircle />
          </button>
          <button className="inv-header-btn">
            <IconUser />
          </button>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="inv-grid">
        {/* Left: Queue list */}
        <div>
          <FilterBar />

          {/* Table header */}
          <div className="inv-table-header">
            <span>Status</span>
            <span>Question Hypothesis</span>
            <span className="inv-table-header-cost">Cost</span>
            <span>Priority</span>
            <span />
          </div>

          {/* Rows */}
          <div>
            {paginated.map((inv) => (
              <InvestigationRow key={inv.id} investigation={inv} />
            ))}
          </div>

          {/* Pagination */}
          <InvestigationPagination totalItems={totalItems} itemsPerPage={ITEMS_PER_PAGE} />
        </div>

        {/* Right: Ask Skeldir */}
        <div>
          <AskSkeldir />
        </div>
      </div>
    </>
  );
}
