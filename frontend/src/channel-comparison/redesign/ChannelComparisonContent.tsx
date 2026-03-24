import React, { useState, useCallback, useEffect } from "react";
import { Download, Calendar } from "lucide-react";
import ChannelChipBar from "./ChannelChipBar";
import ComparisonTable from "./ComparisonTable";
import CIOverlapChart from "./CIOverlapChart";
import { INITIAL_CHANNELS, NEXT_COLOR_INDICES, MAX_COMPARISON_CHANNELS } from "./data";
import type { ChannelData, AvailableChannel } from "./types";

export default function ChannelComparisonContent() {
  const [channels, setChannels] = useState<ChannelData[]>(INITIAL_CHANNELS);
  const [nextColorIdx, setNextColorIdx] = useState(0);
  const [ciOverlaySignal, setCiOverlaySignal] = useState(0);
  /** Single source of truth — chip bar + table checkboxes (Interface 7, max 6). */
  const [selectedIds, setSelectedIds] = useState<string[]>(() => INITIAL_CHANNELS.map((c) => c.channelId));

  const handleCompareSelected = useCallback(() => {
    setCiOverlaySignal((n) => n + 1);
    requestAnimationFrame(() => {
      document.getElementById("cc-roas-ci")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, []);

  const toggleChannel = useCallback((channelId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(channelId)) next.delete(channelId);
      else if (next.size < MAX_COMPARISON_CHANNELS) next.add(channelId);
      return [...next];
    });
  }, []);

  const handleDeselect = useCallback((channelId: string) => {
    setSelectedIds((prev) => prev.filter((id) => id !== channelId));
  }, []);

  const handleRemoveFromRoster = useCallback((channelId: string) => {
    setChannels((prev) => prev.filter((c) => c.channelId !== channelId));
    setSelectedIds((prev) => prev.filter((id) => id !== channelId));
  }, []);

  useEffect(() => {
    const valid = new Set(channels.map((c) => c.channelId));
    setSelectedIds((prev) => prev.filter((id) => valid.has(id)));
  }, [channels]);

  const filteredForChart =
    selectedIds.length >= 2 ? channels.filter((c) => selectedIds.includes(c.channelId)) : null;
  const chartChannels =
    filteredForChart != null && filteredForChart.length >= 2 ? filteredForChart : channels;

  const handleAdd = (availableChannel: AvailableChannel) => {
    const colorIndex = NEXT_COLOR_INDICES[nextColorIdx % NEXT_COLOR_INDICES.length] || 5;
    const newChannel: ChannelData = {
      channelId: availableChannel.channelId,
      channelName: availableChannel.channelName,
      platform: availableChannel.platform,
      colorIndex,
      spend: 14200,
      spendFormatted: "$14,200",
      verifiedRevenue: 38500,
      verifiedRevenueFormatted: "$38,500",
      discrepancyPct: 3.2,
      verificationStatus: "verified",
      attributionWeight: 0.1,
      attributionMethod: "bayesian",
      roas: {
        estimate: 2.71,
        lower: 1.9,
        upper: 3.5,
        bucket: "medium",
        formattedEstimate: "2.71",
        formattedLower: "1.90",
        formattedUpper: "3.50",
        rangeLabel: "80% HDI",
      },
      agreementScore: 0.74,
      divergenceFlag: false,
      revenueSource: "Stripe",
      lastSyncLabel: "8 min ago",
      cpl: 41,
      cplFormatted: "$41.00",
      conversions: 342,
      trend: { direction: "up", value: "↑ 5%", period: "vs last 30 days" },
    };
    setChannels((prev) => [...prev, newChannel]);
    setSelectedIds((prev) => {
      if (prev.includes(newChannel.channelId)) return prev;
      if (prev.length >= MAX_COMPARISON_CHANNELS) return prev;
      return [...prev, newChannel.channelId];
    });
    setNextColorIdx((i) => i + 1);
  };

  return (
    <div
      style={{
        minHeight: "100%",
        background: "transparent",
        fontFamily: "DM Sans, sans-serif",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Top Bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          height: 56,
          borderBottom: "1px solid #E2E8F0",
          background: "#FFFFFF",
          padding: "0 24px",
          position: "sticky",
          top: 0,
          zIndex: 60,
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <h1
            style={{
              fontSize: 20,
              fontWeight: 800,
              color: "#0F172A",
              letterSpacing: "-0.01em",
              margin: 0,
              fontFamily: "var(--font-sans)",
            }}
          >
            Channel Comparison
          </h1>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              borderRadius: 6,
              border: "1px solid #E2E8F0",
              background: "#FFFFFF",
              color: "#0F172A",
              fontSize: 14,
              fontWeight: 500,
              cursor: "pointer",
              fontFamily: "var(--font-sans)",
              transition: "background 150ms ease",
            }}
          >
            <Calendar size={13} />
            <span>Mar 1 – Mar 31, 2026</span>
          </button>
          <button
            disabled={channels.length < 2}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              borderRadius: 6,
              border: "1px solid #E2E8F0",
              background: "#FFFFFF",
              color: channels.length >= 2 ? "#0F172A" : "#CBD5E1",
              fontSize: 14,
              fontWeight: 500,
              cursor: channels.length >= 2 ? "pointer" : "not-allowed",
              fontFamily: "var(--font-sans)",
              transition: "background 150ms ease",
            }}
          >
            <Download size={13} /> <span>Export</span>
          </button>
        </div>
      </div>

      <div
        style={{
          maxWidth: "100%",
          margin: "0 auto",
          padding: "24px 16px 24px",
          display: "flex",
          flexDirection: "column",
          gap: 28,
          width: "100%",
          boxSizing: "border-box",
        }}
      >
        <ChannelChipBar
          rosterChannels={channels}
          selectedIds={selectedIds}
          onDeselect={handleDeselect}
          onRemoveFromRoster={handleRemoveFromRoster}
          onAdd={handleAdd}
        />
        {channels.length >= 2 ? (
          <>
            <ComparisonTable
              channels={channels}
              selectedIds={selectedIds}
              onToggleChannel={toggleChannel}
              onCompareSelected={handleCompareSelected}
            />
            <CIOverlapChart
              channels={chartChannels}
              periodLabel="Mar 1 – Mar 31, 2026"
              openOverlaySignal={ciOverlaySignal}
            />
          </>
        ) : (
          <div
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              borderRadius: 8,
              padding: 48,
              textAlign: "center",
              color: "#94A3B8",
              fontSize: 14,
              fontFamily: "DM Sans, sans-serif",
            }}
          >
            Select at least 2 channels to begin comparison.
          </div>
        )}
      </div>
    </div>
  );
}
