import React, { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, Minus, TrendingDown, TrendingUp } from "lucide-react";
import PlatformIcon from "./PlatformIcon";
import { BucketBadge, VerificationBadge } from "../../command-center/components/Badges";
import { CC_ROAS_SCALE } from "./ciOverlapTypes";
import { DATA_COLORS } from "./types";
import type { ChannelData, ChannelROAS } from "./types";
import { MAX_COMPARISON_CHANNELS } from "./data";
import "./comparison-table.css";

/** Vivid two-tone palette for inline ROAS bars (original channel-comparison table). */
const VIVID_BAR: Record<number, { dark: string; light: string }> = {
  1: { dark: "#2563EB", light: "#38BDF8" },
  2: { dark: "#7C3AED", light: "#C084FC" },
  3: { dark: "#E11D48", light: "#FB7185" },
  4: { dark: "#16A34A", light: "#2DD4BF" },
  5: { dark: "#E60023", light: "#FF5A7A" },
  6: { dark: "#00A3CC", light: "#67E8F9" },
};

type ColId =
  | "channel"
  | "spend"
  | "revenue"
  | "roas"
  | "confidence"
  | "cpl"
  | "conversions"
  | "trend";

const COLUMNS: { id: ColId; header: string; sortable: boolean; align: "left" | "right" | "center" }[] = [
  { id: "channel", header: "CHANNEL", sortable: true, align: "left" },
  { id: "spend", header: "SPEND", sortable: true, align: "right" },
  { id: "revenue", header: "REVENUE (VERIFIED)", sortable: true, align: "right" },
  { id: "roas", header: "ROAS", sortable: true, align: "left" },
  { id: "confidence", header: "MODEL AGREE.", sortable: true, align: "center" },
  { id: "cpl", header: "CPL", sortable: true, align: "right" },
  { id: "conversions", header: "CONV.", sortable: true, align: "right" },
  { id: "trend", header: "TREND", sortable: true, align: "center" },
];

const COL_WIDTHS: Record<ColId, string> = {
  channel: "220px",
  spend: "112px",
  revenue: "148px",
  roas: "240px",
  confidence: "120px",
  cpl: "92px",
  conversions: "80px",
  trend: "80px",
};

function trendSortKey(ch: ChannelData): number {
  const m = ch.trend.value.match(/(\d+)/);
  const n = m ? parseInt(m[1], 10) : 0;
  if (ch.trend.direction === "down") return -n;
  if (ch.trend.direction === "up") return n;
  return 0;
}

function compareChannels(a: ChannelData, b: ChannelData, sortCol: ColId, sortDir: "asc" | "desc"): number {
  let cmp = 0;

  switch (sortCol) {
    case "channel":
      cmp = a.channelName.localeCompare(b.channelName);
      break;
    case "spend":
      cmp = a.spend - b.spend;
      break;
    case "revenue":
      cmp = a.verifiedRevenue - b.verifiedRevenue;
      break;
    case "roas":
      cmp = sortDir === "desc" ? a.roas.estimate - b.roas.estimate : a.roas.lower - b.roas.lower;
      return cmp;
    case "confidence":
      cmp = a.agreementScore - b.agreementScore;
      return sortDir === "desc" ? -cmp : cmp;
    case "cpl":
      cmp = a.cpl - b.cpl;
      break;
    case "conversions":
      cmp = a.conversions - b.conversions;
      break;
    case "trend":
      cmp = trendSortKey(a) - trendSortKey(b);
      break;
    default:
      cmp = 0;
  }

  return sortDir === "desc" ? -cmp : cmp;
}

/** Original inline ROAS visualization: point on top, 5px track, two-tone HDI, tick, range + label row. */
function ROASMiniBar({ roas, colorIndex }: { roas: ChannelROAS; colorIndex: number }) {
  const { lower, upper, estimate } = roas;
  const barColors = VIVID_BAR[colorIndex] ?? {
    dark: DATA_COLORS[colorIndex] ?? "#64748B",
    light: "color-mix(in srgb, var(--border-default) 60%, white)",
  };

  const DOMAIN_MIN = CC_ROAS_SCALE.min;
  const DOMAIN_MAX = CC_ROAS_SCALE.max;
  const domainRange = DOMAIN_MAX - DOMAIN_MIN || 1;

  const pct = (value: number) =>
    Math.min(100, Math.max(0, ((value - DOMAIN_MIN) / domainRange) * 100));

  const lowerPct = pct(lower);
  const upperPct = pct(upper);
  const estPct = pct(estimate);

  const leftWidth = Math.max(1, estPct - lowerPct);
  const rightWidth = Math.max(1, upperPct - estPct);

  return (
    <div style={{ width: "100%" }}>
      <div
        style={{
          fontFamily: "JetBrains Mono, monospace",
          fontSize: 14,
          fontWeight: 600,
          color: "#0F172A",
          lineHeight: 1.2,
          marginBottom: 4,
        }}
      >
        {roas.formattedEstimate}
      </div>
      <div
        style={{
          width: "100%",
          height: 5,
          borderRadius: 2,
          position: "relative",
          marginBottom: 5,
          background: "color-mix(in srgb, var(--border-default) 72%, white)",
          boxShadow: "inset 0 0 0 1px color-mix(in srgb, var(--border-strong) 80%, transparent)",
        }}
      >
        <div
          style={{
            position: "absolute",
            left: `${lowerPct}%`,
            top: 0,
            width: `${leftWidth}%`,
            height: "100%",
            borderRadius: "2px 0 0 2px",
            background: barColors.dark,
          }}
        />
        <div
          style={{
            position: "absolute",
            left: `${estPct}%`,
            top: 0,
            width: `${rightWidth}%`,
            height: "100%",
            borderRadius: "0 2px 2px 0",
            background: barColors.light,
          }}
        />
        <div
          style={{
            position: "absolute",
            left: `${estPct}%`,
            top: -3,
            width: 1,
            height: 9,
            background: "#0F172A",
            transform: "translateX(-50%)",
          }}
        />
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          fontFamily: "DM Sans, sans-serif",
          fontSize: 11,
          color: "#94A3B8",
          flexWrap: "wrap",
        }}
      >
        <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10 }}>
          {roas.formattedLower} — {roas.formattedUpper}
        </span>
        <BucketBadge bucket={roas.bucket} size="sm" />
        <span style={{ fontSize: 10 }}>{roas.rangeLabel}</span>
      </div>
    </div>
  );
}

function ModelAgreementDots({ channel }: { channel: ChannelData }) {
  let dotColors: string[] = [];
  if (channel.channelId === "google_ads") {
    dotColors = [DATA_COLORS[1], DATA_COLORS[1], "#EF4444"];
  } else if (channel.channelId === "meta") {
    dotColors = [DATA_COLORS[2], "#EF4444"];
  } else if (channel.channelId === "tiktok") {
    dotColors = ["#EF4444"];
  } else if (channel.channelId === "linkedin") {
    dotColors = [DATA_COLORS[1], "#10B981"];
  } else {
    dotColors = ["#94A3B8"];
  }

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 5, marginTop: 6 }}>
      {dotColors.map((c, i) => (
        <div
          key={i}
          style={{
            width: 10,
            height: 10,
            borderRadius: "50%",
            background: c,
          }}
        />
      ))}
    </div>
  );
}

function TrendCell({ channel }: { channel: ChannelData }) {
  const { direction, value, period } = channel.trend;
  const color =
    direction === "up" ? "#059669" : direction === "down" ? "#DC2626" : "#64748B";
  const Icon = direction === "up" ? TrendingUp : direction === "down" ? TrendingDown : Minus;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 4,
        fontFamily: "JetBrains Mono, monospace",
        fontSize: 12,
        fontWeight: 500,
        color,
      }}
      title={period}
    >
      <Icon size={14} strokeWidth={2} aria-hidden />
      {value}
    </span>
  );
}

function RevenueCell({ channel }: { channel: ChannelData }) {
  const src = channel.revenueSource ?? "Stripe";
  const tip =
    channel.verificationStatus === "verified"
      ? [`Verified via ${src}`, channel.lastSyncLabel ? `Last sync: ${channel.lastSyncLabel}` : null]
          .filter(Boolean)
          .join(" · ")
      : undefined;

  return (
    <div style={{ display: "inline-block", textAlign: "right" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", flexWrap: "wrap", gap: 6 }}>
        <span
          style={{
            fontFamily: "JetBrains Mono, monospace",
            fontSize: 13,
            fontWeight: 500,
            color: "#0F172A",
          }}
        >
          {channel.verifiedRevenueFormatted}
        </span>
        <VerificationBadge
          status={channel.verificationStatus}
          source={src}
          lastSyncLabel={channel.lastSyncLabel}
          compact
        />
      </div>
      {channel.verificationStatus === "verified" && (
        <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 3 }} title={tip}>
          via {src}
        </div>
      )}
      {channel.verificationStatus === "partial" && (
        <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 3 }}>
          {channel.verificationPartialPct != null ? `Partial (${channel.verificationPartialPct}%)` : "Partially verified"} · {src}
        </div>
      )}
      {channel.verificationStatus === "unverified" && (
        <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 3 }}>
          Unverified · {src}
        </div>
      )}
    </div>
  );
}

function SortIcon({
  colId,
  sortColumn,
  sortDirection,
}: {
  colId: ColId;
  sortColumn: ColId;
  sortDirection: "asc" | "desc";
}) {
  const active = colId === sortColumn;
  const color = active ? "#4F46E5" : "#CBD5E1";
  if (!active) return <ArrowUpDown size={12} color={color} aria-hidden />;
  return sortDirection === "desc" ? (
    <ArrowDown size={12} color={color} aria-hidden />
  ) : (
    <ArrowUp size={12} color={color} aria-hidden />
  );
}

export interface ComparisonTableProps {
  channels: ChannelData[];
  /** Single source of truth with chip bar (max `MAX_COMPARISON_CHANNELS`). */
  selectedIds: string[];
  onToggleChannel: (channelId: string) => void;
  loading?: boolean;
  /** Fires when user chooses “Compare selected” (≥2 rows checked). */
  onCompareSelected?: () => void;
}

export default function ComparisonTable({
  channels,
  selectedIds,
  onToggleChannel,
  loading = false,
  onCompareSelected,
}: ComparisonTableProps) {
  const [sortCol, setSortCol] = useState<ColId>("roas");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [hoverRow, setHoverRow] = useState<string | null>(null);

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const handleSort = (colId: ColId) => {
    const col = COLUMNS.find((c) => c.id === colId);
    if (!col?.sortable) return;
    if (colId === sortCol) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortCol(colId);
      if (colId === "confidence") setSortDir("desc");
      else if (colId === "channel") setSortDir("asc");
      else setSortDir("desc");
    }
  };

  const sorted = useMemo(() => {
    const arr = [...channels];
    arr.sort((a, b) => compareChannels(a, b, sortCol, sortDir));
    return arr;
  }, [channels, sortCol, sortDir]);

  const canCompare = selectedIds.length >= 2;

  if (!loading && channels.length === 0) {
    return (
      <div
        style={{
          background: "#FFFFFF",
          border: "1px solid #E2E8F0",
          borderRadius: 8,
          boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "16px 18px 10px", fontSize: 14, fontWeight: 700, color: "#0F172A" }}>Comparison</div>
        <div style={{ padding: 48, textAlign: "center", color: "#94A3B8", fontSize: 14 }}>No channels selected for comparison.</div>
      </div>
    );
  }

  return (
    <div
      style={{
        background: "#FFFFFF",
        border: "1px solid #E2E8F0",
        borderRadius: 8,
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "16px 18px 10px",
          fontSize: 14,
          fontWeight: 700,
          color: "#0F172A",
          fontFamily: "DM Sans, sans-serif",
          letterSpacing: "-0.01em",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <span>Comparison</span>
          {canCompare && (
            <button
              type="button"
              onClick={() => onCompareSelected?.()}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid var(--brand-primary, #1e40af)",
                background: "var(--brand-primary-light, #dbeafe)",
                color: "var(--brand-primary, #1e40af)",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
                fontFamily: "DM Sans, sans-serif",
              }}
            >
              Compare selected ({selectedIds.length})
            </button>
          )}
        </div>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            minWidth: 1020,
            borderCollapse: "collapse",
            fontFamily: "DM Sans, sans-serif",
          }}
          role="table"
          aria-label="Channel comparison table"
        >
          <thead>
            <tr
              style={{
                borderBottom: "1px solid #E2E8F0",
                height: 56,
                background: "color-mix(in srgb, var(--border-default) 42%, white)",
              }}
            >
              {COLUMNS.map((col) => (
                <th
                  key={col.id}
                  scope="col"
                  onClick={() => col.sortable && handleSort(col.id)}
                  style={{
                    padding: "0 18px",
                    textAlign: col.align,
                    fontSize: 11,
                    fontWeight: 600,
                    color: "#0F172A",
                    letterSpacing: "0.06em",
                    whiteSpace: "nowrap",
                    cursor: col.sortable ? "pointer" : "default",
                    width: COL_WIDTHS[col.id],
                    userSelect: "none",
                  }}
                  title={
                    col.id === "roas"
                      ? sortDir === "desc"
                        ? "Sorted by posterior median (high to low)"
                        : "Sorted by lower bound (conservative)"
                      : col.id === "confidence"
                        ? sortDir === "desc"
                          ? "Highest model agreement first"
                          : "Lowest model agreement first"
                        : undefined
                  }
                >
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                    {col.header}
                    {col.sortable && <SortIcon colId={col.id} sortColumn={sortCol} sortDirection={sortDir} />}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 6 }).map((_, i) => (
                  <tr key={`sk-${i}`} style={{ borderBottom: "1px solid #F1F5F9" }}>
                    {COLUMNS.map((col) => (
                      <td key={col.id} style={{ padding: "16px 18px", textAlign: col.align }}>
                        <div
                          style={{
                            height: 10,
                            borderRadius: 4,
                            background: "linear-gradient(90deg, #f1f5f9 0%, #e2e8f0 50%, #f1f5f9 100%)",
                            backgroundSize: "200% 100%",
                            opacity: 0.9,
                          }}
                        />
                      </td>
                    ))}
                  </tr>
                ))
              : sorted.map((ch, idx) => {
                  const color = DATA_COLORS[ch.colorIndex] ?? "#64748B";
                  const isSel = selectedSet.has(ch.channelId);
                  const isHover = hoverRow === ch.channelId;
                  const isLast = idx === sorted.length - 1;
                  const rowBg = isSel ? "#EFF6FF" : isHover ? "#F8FAFC" : "#FFFFFF";
                  const leftAccent = isSel ? "#1E40AF" : color;
                  return (
                    <tr
                      key={ch.channelId}
                      className={`cc-cmp-row${isSel ? " cc-cmp-row--selected" : ""}`}
                      onMouseEnter={() => setHoverRow(ch.channelId)}
                      onMouseLeave={() => setHoverRow(null)}
                      style={{
                        borderBottom: isLast ? "none" : "1px solid #F1F5F9",
                        background: rowBg,
                        transition: "background 0.1s",
                        cursor: "pointer",
                        minHeight: 76,
                      }}
                      onClick={() => onToggleChannel(ch.channelId)}
                    >
                      <td
                        style={{
                          padding: "16px 18px",
                          borderLeft: `3px solid ${leftAccent}`,
                          minWidth: 160,
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <input
                            type="checkbox"
                            className="cc-cmp-cb"
                            checked={isSel}
                            disabled={!isSel && selectedIds.length >= MAX_COMPARISON_CHANNELS}
                            title={
                              !isSel && selectedIds.length >= MAX_COMPARISON_CHANNELS
                                ? `Max ${MAX_COMPARISON_CHANNELS} channels for comparison`
                                : isSel
                                  ? `Selected for comparison (${selectedIds.length} of ${MAX_COMPARISON_CHANNELS})`
                                  : `Select ${ch.channelName} for batch comparison`
                            }
                            onChange={(e) => {
                              e.stopPropagation();
                              onToggleChannel(ch.channelId);
                            }}
                            onClick={(e) => e.stopPropagation()}
                            aria-label={`Select ${ch.channelName} for comparison`}
                          />
                          <div
                            style={{
                              width: 8,
                              height: 8,
                              borderRadius: "50%",
                              background: color,
                              flexShrink: 0,
                            }}
                          />
                          <PlatformIcon platform={ch.platform} size={18} />
                          <div style={{ fontSize: 14, fontWeight: 600, color: "#0F172A", lineHeight: 1.35 }}>
                            {ch.channelName}
                          </div>
                        </div>
                      </td>
                      <td style={{ padding: "16px 18px", textAlign: "right" }}>
                        <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 13, fontWeight: 500, color: "#0F172A" }}>
                          {ch.spendFormatted}
                        </span>
                      </td>
                      <td style={{ padding: "16px 18px", textAlign: "right" }}>
                        <RevenueCell channel={ch} />
                      </td>
                      <td style={{ padding: "16px 18px" }}>
                        <ROASMiniBar roas={ch.roas} colorIndex={ch.colorIndex} />
                      </td>
                      <td style={{ padding: "16px 18px", textAlign: "center" }}>
                        <div
                          style={{
                            fontFamily: "JetBrains Mono, monospace",
                            fontSize: 14,
                            fontWeight: 600,
                            color: "#0F172A",
                          }}
                        >
                          {Math.round(ch.agreementScore * 100)}%
                        </div>
                        <ModelAgreementDots channel={ch} />
                      </td>
                      <td style={{ padding: "16px 18px", textAlign: "right" }}>
                        <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 14, color: "#0F172A" }}>
                          {ch.cplFormatted}
                        </span>
                      </td>
                      <td style={{ padding: "16px 18px", textAlign: "right" }}>
                        <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 14, color: "#0F172A" }}>
                          {ch.conversions.toLocaleString("en-US")}
                        </span>
                      </td>
                      <td style={{ padding: "16px 18px", textAlign: "center" }}>
                        <TrendCell channel={ch} />
                      </td>
                    </tr>
                  );
                })}
          </tbody>
        </table>
      </div>

      {loading && (
        <div style={{ padding: "10px 18px", fontSize: 12, color: "#64748b", borderTop: "1px solid #e2e8f0" }}>
          Loading channel data…
        </div>
      )}
    </div>
  );
}
