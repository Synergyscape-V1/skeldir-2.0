import React, { useCallback, useMemo, useState } from "react";
import { Check, Download, RefreshCw } from "lucide-react";
import type { MatchCategory, RevenueBreakdownRow, RevenueMatchingBreakdownProps } from "./revenueMatchingTypes";
import {
  DEFAULT_REVENUE_BREAKDOWN,
  DEFAULT_REVENUE_PERIOD,
  DEFAULT_REVENUE_SUMMARY,
  WATERFALL_COPY,
} from "./revenueMatchingMock";
import "./revenue-matching-breakdown.css";

function parsePct(s: string): number {
  if (s === "—" || !s.trim()) return Number.NaN;
  const n = parseFloat(s.replace(/%/g, ""));
  return Number.isFinite(n) ? n : Number.NaN;
}

function sortAbsPctDesc(a: RevenueBreakdownRow, b: RevenueBreakdownRow): number {
  const pa = Math.abs(parsePct(a.discrepancy.percentage));
  const pb = Math.abs(parsePct(b.discrepancy.percentage));
  if (Number.isNaN(pa) && Number.isNaN(pb)) return 0;
  if (Number.isNaN(pa)) return 1;
  if (Number.isNaN(pb)) return -1;
  return pb - pa;
}

const BADGE_META: Record<MatchCategory, { label: string; threshold: string; className: string }> = {
  matched: {
    label: "Matched",
    threshold: "<2% variance",
    className: "rmb-badge--matched",
  },
  flagged: {
    label: "Flagged",
    threshold: "2–10% variance",
    className: "rmb-badge--flagged",
  },
  severe: {
    label: "Severe",
    threshold: ">10% discrepancy",
    className: "rmb-badge--severe",
  },
  unmatched: {
    label: "Unmatched",
    threshold: "No verified data",
    className: "rmb-badge--unmatched",
  },
};

function StatusBadge({ category }: { category: MatchCategory }) {
  const m = BADGE_META[category];
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 2 }}>
      <span className={`rmb-badge ${m.className}`} title={`${m.label} · ${m.threshold}`}>
        {m.label}
      </span>
      <span style={{ fontSize: 10, color: "var(--rmb-text-tertiary)", fontWeight: 500 }}>{m.threshold}</span>
    </div>
  );
}

function WaterfallPanel({
  rowId,
  onViewDetails,
}: {
  rowId: string;
  onViewDetails: () => void;
}) {
  const w = WATERFALL_COPY[rowId];
  if (!w) {
    return (
      <div className="rmb-waterfall">
        <p style={{ margin: 0, fontSize: 12, color: "var(--rmb-text-secondary)" }}>
          Revenue verification waterfall data will load from the API for this channel.
        </p>
        <div className="rmb-wf-actions">
          <button type="button" onClick={onViewDetails}>
            View details
          </button>
        </div>
      </div>
    );
  }
  return (
    <div className="rmb-waterfall">
      <h4>Revenue verification waterfall</h4>
      <div className="rmb-wf-row">
        <span>Platform claimed</span>
        <strong>{w.platformClaimed}</strong>
      </div>
      <div className="rmb-wf-row">
        <span>Platform adjusted ({w.adjustedNote})</span>
        <strong>{w.platformAdjusted}</strong>
      </div>
      <div className="rmb-wf-row">
        <span>Verified via Stripe</span>
        <strong>{w.verified}</strong>
      </div>
      <div className="rmb-wf-row">
        <span>Verification gap</span>
        <strong style={{ color: "var(--rmb-critical)" }}>{w.gap}</strong>
      </div>
      <div className="rmb-wf-row">
        <span>Attribution overlap ({w.overlapNote})</span>
        <strong>{w.overlap}</strong>
      </div>
      <div className="rmb-wf-row">
        <span>Skeldir attributed (trusted)</span>
        <strong style={{ color: "var(--rmb-verified)" }}>{w.skeldirAttributed}</strong>
      </div>
      <p style={{ margin: "10px 0 0", fontSize: 12, fontWeight: 600, color: "var(--rmb-caution)" }}>
        Common causes
      </p>
      <ul className="rmb-wf-bullets">
        {w.bullets.map((b) => (
          <li key={b}>{b}</li>
        ))}
      </ul>
      <div className="rmb-wf-actions">
        <button type="button">Download reconciliation report</button>
        <button type="button">Adjust attribution settings</button>
        <button type="button">Dismiss alert</button>
      </div>
    </div>
  );
}

export type RevenueMatchingProps = Partial<
  Pick<
    RevenueMatchingBreakdownProps,
    "period" | "summary" | "breakdown" | "filters" | "onRefresh"
  >
> & {
  onRowClick?: (platformId: string) => void;
  onExport?: () => void;
};

export function RevenueMatching({
  period = DEFAULT_REVENUE_PERIOD,
  summary = DEFAULT_REVENUE_SUMMARY,
  breakdown = DEFAULT_REVENUE_BREAKDOWN,
  filters: filtersProp,
  onRowClick,
  onExport,
  onRefresh,
}: RevenueMatchingProps = {}) {
  const [categoryFilter, setCategoryFilter] = useState<"all" | MatchCategory>(
    filtersProp?.category ?? "all",
  );
  const [minVariance, setMinVariance] = useState(filtersProp?.minDiscrepancy ?? "$0");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const parseMinDollars = useCallback((s: string): number => {
    const n = parseFloat(s.replace(/[^0-9.-]/g, ""));
    return Number.isFinite(n) ? Math.abs(n) : 0;
  }, []);

  const filteredRows = useMemo(() => {
    const min$ = parseMinDollars(minVariance);
    let rows = [...breakdown];
    if (categoryFilter !== "all") {
      rows = rows.filter((r) => r.category === categoryFilter);
    }
    if (min$ > 0) {
      rows = rows.filter((r) => {
        if (r.category === "unmatched") return true;
        const amt = r.discrepancy.amount.replace(/[^0-9.-]/g, "");
        const v = Math.abs(parseFloat(amt) || 0);
        return v >= min$;
      });
    }
    rows.sort(sortAbsPctDesc);
    return rows;
  }, [breakdown, categoryFilter, minVariance, parseMinDollars]);

  const hasSevere = useMemo(() => breakdown.some((r) => r.category === "severe"), [breakdown]);
  const firstSevere = useMemo(() => breakdown.find((r) => r.category === "severe"), [breakdown]);

  const handleRowActivate = useCallback(
    (row: RevenueBreakdownRow) => {
      setSelectedId(row.id);
      setExpandedId((prev) => (prev === row.id ? null : row.id));
    },
    [],
  );

  const handleKeyRow = useCallback(
    (e: React.KeyboardEvent, row: RevenueBreakdownRow) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleRowActivate(row);
      }
    },
    [handleRowActivate],
  );

  const exportCsv = useCallback(() => {
    onExport?.();
  }, [onExport]);

  return (
    <div className="rmb-root">
      <div className="rmb-header">
        <div className="rmb-title-block">
          <h2>Revenue Matching Breakdown — {period.label}</h2>
          <p className="rmb-sub">
            Platform-claimed revenue vs payment-processor verified amounts. Variance categories: Matched (≤2%),
            Flagged (2–10%), Severe (&gt;10%), Unmatched (no verified data).
          </p>
        </div>
        <button type="button" className="rmb-export" onClick={exportCsv}>
          <Download size={16} aria-hidden />
          Export CSV
        </button>
      </div>

      <div className="rmb-summary-grid">
        <div className="rmb-sum-card">
          <div className="rmb-sum-label">Total claimed</div>
          <div className="rmb-sum-value">{summary.totalClaimed}</div>
        </div>
        <div className="rmb-sum-card rmb-sum-card--verified">
          <div className="rmb-sum-label">Total verified</div>
          <div className="rmb-sum-value">
            {summary.totalVerified}
            <Check size={14} className="rmb-check" aria-hidden />
          </div>
          <div className="rmb-sum-sub">via Stripe</div>
        </div>
        <div className="rmb-sum-card rmb-sum-card--critical">
          <div className="rmb-sum-label">Discrepancy</div>
          <div className="rmb-sum-value">{summary.totalDiscrepancy}</div>
          <div className="rmb-sum-sub">vs claimed</div>
        </div>
        <div className="rmb-sum-card rmb-sum-card--caution">
          <div className="rmb-sum-label">Match rate</div>
          <div className="rmb-sum-value">{summary.matchRate}</div>
        </div>
      </div>

      {hasSevere && firstSevere && (
        <div className="rmb-alert" role="status">
          <div>
            <strong>Revenue discrepancy alert.</strong> {firstSevere.displayName} reported {firstSevere.claimed} in
            revenue. Verified revenue from Stripe: {firstSevere.verified}. Discrepancy:{" "}
            {firstSevere.discrepancy.percentage}.{" "}
            <button
              type="button"
              style={{
                background: "none",
                border: "none",
                padding: 0,
                color: "#1d4ed8",
                fontWeight: 600,
                cursor: "pointer",
                textDecoration: "underline",
              }}
              onClick={() => onRowClick?.(firstSevere.id)}
            >
              View details
            </button>
          </div>
        </div>
      )}

      <div className="rmb-filters">
        <label htmlFor="rmb-cat">Category</label>
        <select
          id="rmb-cat"
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value as typeof categoryFilter)}
        >
          <option value="all">All categories</option>
          <option value="matched">Matched</option>
          <option value="flagged">Flagged</option>
          <option value="severe">Severe</option>
          <option value="unmatched">Unmatched</option>
        </select>
        <label htmlFor="rmb-min">Min variance</label>
        <input
          id="rmb-min"
          type="text"
          value={minVariance}
          onChange={(e) => setMinVariance(e.target.value)}
          placeholder="$0"
          aria-label="Minimum variance in dollars"
        />
        {onRefresh && (
          <button type="button" className="rmb-refresh" onClick={() => onRefresh()}>
            <RefreshCw size={14} style={{ verticalAlign: "middle", marginRight: 4 }} aria-hidden />
            Refresh
          </button>
        )}
      </div>

      <div className="rmb-table-wrap">
        <table className="rmb-table">
          <thead>
            <tr>
              <th className="rmb-sticky" style={{ minWidth: 200 }}>
                Platform
              </th>
              <th className="rmb-num" style={{ minWidth: 120 }}>
                Claimed
              </th>
              <th className="rmb-num" style={{ minWidth: 120 }}>
                Verified
              </th>
              <th className="rmb-num" style={{ minWidth: 140 }}>
                Discrepancy
              </th>
              <th style={{ minWidth: 140 }}>Status</th>
              <th style={{ minWidth: 120 }}>Source</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => {
              const discColor =
                row.category === "matched"
                  ? "var(--rmb-verified)"
                  : row.category === "unmatched"
                    ? "var(--rmb-text-tertiary)"
                    : "var(--rmb-critical)";
              const dirLabel =
                row.discrepancy.direction === "over"
                  ? "Over-report"
                  : row.discrepancy.direction === "under"
                    ? "Under-report"
                    : "—";
              const expanded = expandedId === row.id;
              const selected = selectedId === row.id;
              return (
                <React.Fragment key={row.id}>
                  <tr
                    role="button"
                    tabIndex={0}
                    aria-expanded={expanded}
                    aria-label={`${row.displayName}: claimed ${row.claimed}, verified ${row.verified}. Status ${row.category}.`}
                    className={selected ? "rmb-row-selected" : undefined}
                    onClick={() => handleRowActivate(row)}
                    onKeyDown={(e) => handleKeyRow(e, row)}
                  >
                    <td className="rmb-sticky">
                      <div className="rmb-plat">
                        {row.platformIcon}
                        <span className="rmb-plat-name">{row.displayName}</span>
                      </div>
                    </td>
                    <td className="rmb-num rmb-mono">{row.claimed}</td>
                    <td className="rmb-num rmb-mono">
                      {row.verified}
                      {row.verified !== "—" && (
                        <Check size={12} className="rmb-check" aria-label="Verified" />
                      )}
                    </td>
                    <td className="rmb-num">
                      <div className="rmb-mono" style={{ color: discColor }}>
                        {row.discrepancy.amount}
                      </div>
                      <div className="rmb-mono rmb-mono-sm" style={{ color: discColor }}>
                        {row.discrepancy.percentage}
                      </div>
                      {row.category !== "unmatched" && (
                        <div className="rmb-dir">{dirLabel}</div>
                      )}
                    </td>
                    <td>
                      <StatusBadge category={row.category} />
                    </td>
                    <td className="rmb-meta">Stripe</td>
                  </tr>
                  {expanded && (
                    <tr>
                      <td colSpan={6} style={{ padding: 0, height: "auto", borderBottom: "none" }}>
                        <WaterfallPanel rowId={row.id} onViewDetails={() => onRowClick?.(row.id)} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
