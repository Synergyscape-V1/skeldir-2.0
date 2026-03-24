import React, { useCallback, useEffect, useMemo, useState } from "react";
import { FileText, HelpCircle, Settings } from "lucide-react";
import type {
  DataFreshnessTimelineProps,
  FreshnessHistoryPoint,
  FreshnessIntegration,
  FreshnessTimeWindow,
} from "./dataFreshnessTypes";
import { buildMockIntegrations } from "./dataFreshnessMock";
import "./data-freshness-timeline.css";

type SegmentVisual = "success" | "aging" | "stale" | "error" | "no_data";

const SEGMENT_H = 16;
const GAP = 2;

function getSegmentVisual(pt: FreshnessHistoryPoint): SegmentVisual {
  if (pt.status === "success") return "success";
  if (pt.status === "error") return "error";
  if (pt.status === "no_data") return "no_data";
  if (pt.status === "stale") {
    const d = pt.delayMinutes ?? 31;
    return d < 30 ? "aging" : "stale";
  }
  return "stale";
}

function maxConsecutiveStaleOrError(history: FreshnessHistoryPoint[]): number {
  let cur = 0;
  let max = 0;
  for (const pt of history) {
    if (pt.status === "stale" || pt.status === "error") {
      cur += 1;
      max = Math.max(max, cur);
    } else {
      cur = 0;
    }
  }
  return max;
}

function countSuccess(history: FreshnessHistoryPoint[]): number {
  return history.reduce((n, p) => n + (p.status === "success" ? 1 : 0), 0);
}

function sliceHistory(
  integration: FreshnessIntegration,
  window: FreshnessTimeWindow,
): FreshnessHistoryPoint[] {
  const h = integration.history;
  if (window === "7d") {
    return h.length >= 168 ? h.slice(-168) : h;
  }
  return h.length >= 24 ? h.slice(-24) : h;
}

function formatRelativeShort(iso: string, now: number): string {
  const m = Math.round((now - new Date(iso).getTime()) / 60000);
  if (m < 1) return "<1m";
  if (m < 60) return `${m}m`;
  const hours = Math.round(m / 60);
  if (hours < 48) return `${hours}h`;
  const days = Math.round(hours / 24);
  return `${days}d`;
}

function formatTooltipTime(iso: string): string {
  try {
    const d = new Date(iso);
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(d);
  } catch {
    return iso;
  }
}

function segmentTooltipText(pt: FreshnessHistoryPoint, visual: SegmentVisual): string {
  const t = formatTooltipTime(pt.timestamp);
  if (visual === "success" && pt.duration != null) {
    return `${t} — Synced in ${pt.duration.toFixed(1)}s`;
  }
  if (visual === "aging") {
    return `${t} — Delayed ${pt.delayMinutes ?? "?"}min`;
  }
  if (visual === "stale") {
    return `${t} — Stale (>30min)`;
  }
  if (visual === "error") {
    return `${t} — Failed (API error)`;
  }
  if (visual === "no_data") {
    return `${t} — No sync scheduled`;
  }
  return t;
}

function statusPrefix(state: FreshnessIntegration["currentStatus"]["state"]): string {
  if (state === "fresh") return "●";
  if (state === "aging") return "⚠";
  return "✕";
}

const COLORS: Record<SegmentVisual, string> = {
  success: "var(--dft-verified, #059669)",
  aging: "var(--dft-caution, #d97706)",
  stale: "var(--dft-critical, #dc2626)",
  error: "var(--dft-critical, #dc2626)",
  no_data: "var(--dft-inset, #f4f6f8)",
};

export function DataFreshnessTimeline({
  integrations,
  timeWindow: timeWindowProp = "7d",
  onIntegrationClick,
  onSyncNow,
  maxHeight = 320,
  onHelpClick,
  onLogsClick,
}: DataFreshnessTimelineProps) {
  const [timeWindow, setTimeWindow] = useState<FreshnessTimeWindow>(timeWindowProp);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedFixId, setExpandedFixId] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [tip, setTip] = useState<{ x: number; y: number; label: string } | null>(null);

  useEffect(() => {
    setTimeWindow(timeWindowProp);
  }, [timeWindowProp]);

  useEffect(() => {
    const id = window.setInterval(() => setTick((x) => x + 1), 30000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const fn = () => setReducedMotion(mq.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);

  const now = useMemo(() => Date.now(), [tick]);

  const openRow = useCallback(
    (row: FreshnessIntegration, history: FreshnessHistoryPoint[]) => {
      onIntegrationClick(row.id);
      setSelectedId(row.id);
      const bad = maxConsecutiveStaleOrError(history);
      if (bad >= 3) {
        setExpandedFixId((prev) => {
          if (prev === row.id) return null;
          return row.id;
        });
      } else {
        setExpandedFixId(null);
      }
    },
    [onIntegrationClick],
  );

  const segWidth = timeWindow === "7d" ? 4 : 8;

  const axisLabels =
    timeWindow === "7d"
      ? ["7d ago", "6d", "5d", "4d", "3d", "2d", "1d", "Now"]
      : ["24h", "18h", "12h", "6h", "Now"];

  return (
    <div
      className="dft-root"
      data-reduced-motion={reducedMotion ? "true" : undefined}
      style={{
        background: "#FFFFFF",
        border: "1px solid #E2E8F0",
        borderRadius: 8,
        boxShadow: "0 2px 8px rgba(0,0,0,0.10)",
        padding: "var(--dft-space-5, 20px)",
        paddingBottom: 16,
        fontFamily: "'DM Sans', 'Inter', system-ui, sans-serif",
        color: "var(--dft-text-primary, #0f172a)",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 12,
          marginBottom: 12,
          flexWrap: "wrap",
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <h2
              style={{
                margin: 0,
                fontSize: 16,
                fontWeight: 600,
                color: "var(--dft-text-primary, #0f172a)",
              }}
            >
              Data Freshness Timeline
            </h2>
            <span style={{ fontSize: 12, color: "var(--dft-text-tertiary, #64748b)" }}>
              — Last {timeWindow === "7d" ? "7 Days" : "24 Hours"}
            </span>
          </div>
          <p style={{ margin: "6px 0 0", fontSize: 12, fontWeight: 400, color: "#64748b" }}>
            Visual sync history per platform.
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
          <label
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              fontWeight: 500,
              color: "#475569",
            }}
          >
            <span className="sr-only">Time window</span>
            <select
              value={timeWindow}
              onChange={(e) => setTimeWindow(e.target.value as FreshnessTimeWindow)}
              style={{
                fontFamily: "'DM Sans', sans-serif",
                fontSize: 12,
                fontWeight: 600,
                padding: "6px 28px 6px 10px",
                borderRadius: 6,
                border: "1px solid #E2E8F0",
                background: "#fff",
                cursor: "pointer",
                appearance: "none",
                backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23475569' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`,
                backgroundRepeat: "no-repeat",
                backgroundPosition: "right 8px center",
              }}
            >
              <option value="7d">7 Days</option>
              <option value="24h">24 Hours</option>
            </select>
          </label>
          <button
            type="button"
            className="dft-icon-btn"
            title="Help"
            onClick={() => onHelpClick?.()}
            style={iconBtnStyle}
          >
            <HelpCircle size={18} strokeWidth={2} aria-hidden />
            <span className="sr-only">Help</span>
          </button>
          <button
            type="button"
            className="dft-icon-btn"
            title="Logs"
            onClick={() => onLogsClick?.()}
            style={iconBtnStyle}
          >
            <FileText size={18} strokeWidth={2} aria-hidden />
            <span className="sr-only">Logs</span>
          </button>
        </div>
      </div>

      {/* Column headers */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          minHeight: 28,
          borderBottom: "1px solid #EEF2F7",
          marginBottom: 4,
          paddingBottom: 4,
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          color: "#64748b",
        }}
      >
        <div style={{ width: 140, flexShrink: 0 }}>Platform</div>
        <div style={{ flex: 1, minWidth: 0, textAlign: "center" }}>
          Sync health timeline ({timeWindow === "7d" ? "168 hrs" : "24 hrs"})
        </div>
        <div style={{ width: 80, flexShrink: 0, textAlign: "left" }}>Status</div>
        <div style={{ width: 40, flexShrink: 0 }} aria-hidden />
      </div>

      {/* Rows */}
      <div
        style={{
          maxHeight,
          overflowY: "auto",
          marginLeft: -4,
          marginRight: -4,
          paddingLeft: 4,
          paddingRight: 4,
        }}
      >
        {integrations.map((row) => {
          const history = sliceHistory(row, timeWindow);
          const streak = maxConsecutiveStaleOrError(history);
          const successes = countSuccess(history);
          const total = history.length;
          const srSummary = `${row.displayName}: ${successes} of ${total} ${
            timeWindow === "7d" ? "hours" : "hours"
          } successful. Current status ${row.currentStatus.state}, last sync ${formatRelativeShort(
            row.currentStatus.lastSyncAt,
            now,
          )} ago.`;

          const healthTint =
            row.healthScore < 50
              ? "rgba(220, 38, 38, 0.04)"
              : row.healthScore < 75
                ? "rgba(217, 119, 6, 0.05)"
                : "transparent";

          return (
            <div key={row.id}>
              <div
                role="row"
                tabIndex={0}
                aria-label={srSummary}
                className={`dft-row ${selectedId === row.id ? "dft-row--selected" : ""}`}
                onClick={() => openRow(row, history)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    openRow(row, history);
                  }
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  minHeight: 56,
                  borderRadius: 6,
                  cursor: "pointer",
                  background: healthTint,
                  outline: "none",
                }}
              >
                {/* Platform */}
                <div
                  style={{
                    width: 140,
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    paddingRight: 8,
                  }}
                >
                  <span aria-hidden style={{ display: "inline-flex" }}>
                    {row.icon}
                  </span>
                  <span
                    style={{
                      fontSize: 14,
                      fontWeight: 500,
                      color: "var(--dft-text-primary, #0f172a)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {row.displayName}
                  </span>
                </div>

                {/* Timeline */}
                <div
                  className="dft-timeline-scroll"
                  style={{
                    flex: 1,
                    minWidth: 0,
                    overflowX: "auto",
                    paddingTop: "var(--dft-space-2, 8px)",
                    paddingBottom: "var(--dft-space-2, 8px)",
                    position: "relative",
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: GAP,
                      width: "max-content",
                      paddingRight: 12,
                      position: "relative",
                    }}
                  >
                    {history.map((pt, idx) => {
                      const visual = getSegmentVisual(pt);
                      const label = segmentTooltipText(pt, visual);
                      const isError = visual === "error";
                      return (
                        <button
                          key={`${row.id}-${pt.timestamp}-${idx}`}
                          type="button"
                          aria-label={label}
                          className={`dft-segment ${idx === history.length - 1 ? "dft-segment--enter" : ""}`}
                          style={{
                            width: segWidth,
                            height: SEGMENT_H,
                            borderRadius: "var(--dft-radius-sm, 2px)",
                            border: "none",
                            padding: 0,
                            flexShrink: 0,
                            cursor: "pointer",
                            background: COLORS[visual],
                            position: "relative",
                            boxSizing: "border-box",
                          }}
                          onMouseEnter={(e) => {
                            setTip({
                              x: e.clientX,
                              y: e.clientY,
                              label,
                            });
                          }}
                          onMouseMove={(e) => {
                            setTip((prev) =>
                              prev ? { ...prev, x: e.clientX, y: e.clientY } : prev,
                            );
                          }}
                          onMouseLeave={() => setTip(null)}
                          onClick={() => onIntegrationClick(row.id)}
                        >
                          {isError && (
                            <span
                              className="dft-error-stripes"
                              style={{
                                position: "absolute",
                                inset: 0,
                                borderRadius: "var(--dft-radius-sm, 2px)",
                                pointerEvents: "none",
                              }}
                              aria-hidden
                            />
                          )}
                          {visual === "aging" && (
                            <span
                              style={{
                                position: "absolute",
                                inset: 0,
                                borderRadius: "var(--dft-radius-sm, 2px)",
                                boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.25)",
                              }}
                              aria-hidden
                            />
                          )}
                        </button>
                      );
                    })}
                    {/* Now line */}
                    <div
                      aria-hidden
                      title="Now"
                      style={{
                        position: "absolute",
                        right: 4,
                        top: 4,
                        bottom: 4,
                        width: 1,
                        background: "var(--dft-border-strong, rgba(15,23,42,0.22))",
                        borderLeft: "1px dashed var(--dft-border-strong, rgba(15,23,42,0.35))",
                        pointerEvents: "none",
                      }}
                    />
                  </div>
                </div>

                {/* Status */}
                <div
                  style={{
                    width: 80,
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <span
                    title={`Last sync ${formatRelativeShort(row.currentStatus.lastSyncAt, now)} ago`}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSyncNow?.(row.id);
                    }}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      cursor: onSyncNow ? "pointer" : "default",
                    }}
                    role={onSyncNow ? "button" : undefined}
                  >
                    <span
                      style={{
                        fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                        fontSize: 12,
                        fontWeight: 400,
                        color: "var(--dft-text-secondary, #475569)",
                      }}
                    >
                      {statusPrefix(row.currentStatus.state)}{" "}
                      {formatRelativeShort(row.currentStatus.lastSyncAt, now)}
                    </span>
                  </span>
                </div>

                {/* Quick action */}
                <div
                  style={{
                    width: 40,
                    flexShrink: 0,
                    display: "flex",
                    justifyContent: "center",
                  }}
                  className="dft-action-wrap"
                >
                  <button
                    type="button"
                    title="Integration settings / retry"
                    onClick={(e) => {
                      e.stopPropagation();
                      onIntegrationClick(row.id);
                    }}
                    style={{
                      ...gearStyle,
                      opacity: 0,
                      transition: "opacity var(--dft-duration-normal, 200ms) ease",
                    }}
                    className="dft-gear"
                  >
                    <Settings size={18} strokeWidth={2} aria-hidden />
                    <span className="sr-only">Open integration</span>
                  </button>
                </div>
              </div>

              {/* Fix guidance inline */}
              {expandedFixId === row.id && streak >= 3 && (
                <div
                  role="region"
                  aria-label={`Fix guidance for ${row.displayName}`}
                  style={{
                    marginLeft: 140,
                    marginBottom: 8,
                    padding: "12px 14px",
                    borderRadius: 8,
                    border: "1px solid #FDE68A",
                    background: "#FFFBEB",
                    fontSize: 13,
                  }}
                >
                  <div style={{ fontWeight: 600, color: "#92400E", marginBottom: 6 }}>
                    ⚠ Fix Guidance: {row.displayName} sync is degraded
                  </div>
                  <div style={{ color: "#78350F", marginBottom: 10, lineHeight: 1.45 }}>
                    Last successful sync window shows {streak}+ consecutive stale or error hours. This
                    affects attribution accuracy.
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onIntegrationClick(row.id);
                      }}
                      style={fixBtnPrimary}
                    >
                      Reconnect {row.displayName}
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onLogsClick?.();
                      }}
                      style={fixBtnGhost}
                    >
                      View Sync Logs
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setExpandedFixId(null);
                      }}
                      style={fixBtnGhost}
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* X-axis */}
      <div
        style={{
          display: "flex",
          paddingLeft: 140,
          marginTop: 8,
          position: "relative",
        }}
      >
        <div style={{ flex: 1, display: "flex", justifyContent: "space-between", minWidth: 0 }}>
          {axisLabels.map((label, i) => (
            <span
              key={i}
              style={{
                fontFamily: "'DM Sans', sans-serif",
                fontSize: 10,
                color: "#94A3B8",
                whiteSpace: "nowrap",
              }}
            >
              {label}
            </span>
          ))}
        </div>
      </div>

      {tip && (
        <div
          role="tooltip"
          style={{
            position: "fixed",
            left: Math.min(tip.x + 12, typeof window !== "undefined" ? window.innerWidth - 280 : 0),
            top: tip.y + 16,
            zIndex: 2000,
            maxWidth: 260,
            padding: "8px 10px",
            borderRadius: 6,
            background: "#0f172a",
            color: "#f8fafc",
            fontSize: 11,
            fontFamily: "'JetBrains Mono', monospace",
            pointerEvents: "none",
            boxShadow: "0 8px 24px rgba(0,0,0,0.2)",
          }}
        >
          <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
            Sync segment
          </div>
          {tip.label}
        </div>
      )}

      <style>{`
        .dft-row:hover .dft-gear { opacity: 1 !important; }
        .dft-row:focus-visible { box-shadow: inset 0 0 0 2px var(--dft-brand-primary, #2563eb); }
        .sr-only {
          position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
          overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0;
        }
      `}</style>
    </div>
  );
}

const iconBtnStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: 36,
  height: 36,
  borderRadius: 8,
  border: "1px solid #E2E8F0",
  background: "#fff",
  cursor: "pointer",
  color: "#475569",
};

const gearStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: 36,
  height: 36,
  borderRadius: 8,
  border: "1px solid transparent",
  background: "transparent",
  cursor: "pointer",
  color: "#475569",
};

const fixBtnPrimary: React.CSSProperties = {
  fontFamily: "'DM Sans', sans-serif",
  fontSize: 12,
  fontWeight: 600,
  padding: "8px 12px",
  borderRadius: 6,
  border: "none",
  background: "#D97706",
  color: "#fff",
  cursor: "pointer",
};

const fixBtnGhost: React.CSSProperties = {
  fontFamily: "'DM Sans', sans-serif",
  fontSize: 12,
  fontWeight: 600,
  padding: "8px 12px",
  borderRadius: 6,
  border: "1px solid #E2E8F0",
  background: "#fff",
  color: "#475569",
  cursor: "pointer",
};

/** Default Data Health dashboard entry — mock API payload. */
export function DataFreshness(
  props: Partial<Omit<DataFreshnessTimelineProps, "integrations">> & {
    integrations?: DataFreshnessTimelineProps["integrations"];
  },
) {
  const [mock] = useState(() => buildMockIntegrations());
  const integrations = props.integrations ?? mock;
  return (
    <DataFreshnessTimeline
      integrations={integrations}
      timeWindow={props.timeWindow}
      onIntegrationClick={props.onIntegrationClick ?? (() => {})}
      onSyncNow={props.onSyncNow}
      maxHeight={props.maxHeight}
      onHelpClick={props.onHelpClick}
      onLogsClick={props.onLogsClick}
    />
  );
}
