import React, { useState, useRef, useEffect } from "react";
import { X, Plus, ChevronDown, Search } from "lucide-react";
import PlatformIcon from "./PlatformIcon";
import { DATA_COLORS } from "./types";
import type { ChannelData, AvailableChannel } from "./types";
import { AVAILABLE_CHANNELS, MAX_COMPARISON_CHANNELS } from "./data";

const CHANNEL_BRAND_BORDERS: Record<string, string> = {
  google_ads: "var(--cc-chip-border-google-ads)",
  meta: "var(--cc-chip-border-meta)",
  tiktok: "var(--cc-chip-border-tiktok)",
  linkedin: "var(--cc-chip-border-linkedin)",
};

function ChannelChip({
  channel,
  color,
  onDeselect,
}: {
  channel: ChannelData;
  color: string;
  /** Unchecks table row; channel stays in workspace — unified selection (Interface 7). */
  onDeselect: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const brandBorder = CHANNEL_BRAND_BORDERS[channel.platform] ?? color;

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        height: 46,
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        paddingLeft: 18,
        paddingRight: 12,
        borderRadius: 9999,
        border: `2px solid ${brandBorder}`,
        background: hovered ? `color-mix(in srgb, ${brandBorder} 28%, white)` : "#FFFFFF",
        fontFamily: "DM Sans, sans-serif",
        fontSize: 14,
        fontWeight: 600,
        color: "#0F172A",
        cursor: "default",
        transition: "background 0.14s ease, box-shadow 0.14s ease, transform 0.14s ease",
        whiteSpace: "nowrap",
        userSelect: "none",
        boxShadow: hovered
          ? `0 10px 18px color-mix(in srgb, ${brandBorder} 18%, transparent)`
          : "none",
        transform: hovered ? "translateY(-0.5px)" : "translateY(0px)",
      }}
    >
      <span
        style={{
          width: 10,
          height: 10,
          borderRadius: "50%",
          background: brandBorder,
          flexShrink: 0,
        }}
      />
      <PlatformIcon platform={channel.platform} size={16} />
      <span>{channel.channelName}</span>
      <button
        type="button"
        title="Deselect — channel stays in comparison; use Add Channel → In comparison to remove entirely."
        onClick={(e) => {
          e.stopPropagation();
          onDeselect();
        }}
        style={{
          background: "none",
          border: "none",
          padding: 0,
          marginLeft: 4,
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 28,
          height: 28,
          borderRadius: 9999,
          color: "#475569",
          lineHeight: 1,
          transition: "background 0.14s ease, color 0.14s ease",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = `color-mix(in srgb, ${brandBorder} 35%, transparent)`;
          e.currentTarget.style.color = "#0F172A";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "transparent";
          e.currentTarget.style.color = "#475569";
        }}
      >
        <X size={14} aria-hidden />
      </button>
    </div>
  );
}

export default function ChannelChipBar({
  rosterChannels,
  selectedIds,
  onDeselect,
  onRemoveFromRoster,
  onAdd,
}: {
  /** All channels in the comparison workspace (table rows). */
  rosterChannels: ChannelData[];
  /** Unified selection — subset of roster; synced with table checkboxes (max 6). */
  selectedIds: string[];
  onDeselect: (channelId: string) => void;
  onRemoveFromRoster: (channelId: string) => void;
  onAdd: (channel: AvailableChannel) => void;
}) {
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [search, setSearch] = useState("");
  const popoverRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  const rosterIds = new Set(rosterChannels.map((c) => c.channelId));
  const isAtMaxRoster = rosterChannels.length >= MAX_COMPARISON_CHANNELS;
  const selectedSet = new Set(selectedIds);

  const chipChannels = rosterChannels.filter((c) => selectedSet.has(c.channelId));

  const filtered = AVAILABLE_CHANNELS.filter(
    (c) =>
      !rosterIds.has(c.channelId) &&
      c.channelName.toLowerCase().includes(search.toLowerCase())
  );

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        btnRef.current &&
        !btnRef.current.contains(e.target as Node)
      ) {
        setPopoverOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div
      style={{
        width: "100%",
        background: "#FFFFFF",
        border: "1px solid #E2E8F0",
        borderRadius: 8,
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        padding: "16px 16px",
      }}
    >
      <div
        style={{
          fontSize: 14,
          fontWeight: 700,
          color: "var(--text-primary)",
          marginBottom: 12,
          fontFamily: "DM Sans, sans-serif",
          letterSpacing: "-0.01em",
        }}
      >
        Channels
      </div>
      {selectedIds.length === 0 && (
        <div
          style={{
            fontSize: 12,
            fontWeight: 500,
            color: "#D97706",
            marginBottom: 10,
            fontFamily: "DM Sans, sans-serif",
          }}
        >
          Select up to {MAX_COMPARISON_CHANNELS} channels to compare (table checkboxes stay in sync).
        </div>
      )}
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
        {chipChannels.map((ch) => (
          <ChannelChip
            key={ch.channelId}
            channel={ch}
            color={DATA_COLORS[ch.colorIndex]}
            onDeselect={() => onDeselect(ch.channelId)}
          />
        ))}

        <div style={{ position: "relative" }}>
          <button
            ref={btnRef}
            onClick={() => !isAtMaxRoster && setPopoverOpen((v) => !v)}
            disabled={isAtMaxRoster}
            title={isAtMaxRoster ? `Maximum ${MAX_COMPARISON_CHANNELS} channels in comparison workspace` : undefined}
            style={{
              height: 46,
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              paddingLeft: 16,
              paddingRight: 16,
              borderRadius: 9999,
              border: `2px dashed ${isAtMaxRoster ? "#CBD5E1" : "#94A3B8"}`,
              background: isAtMaxRoster ? "#F8FAFC" : "#FFFFFF",
              color: isAtMaxRoster ? "#94A3B8" : "#0F172A",
              fontFamily: "DM Sans, sans-serif",
              fontSize: 14,
              fontWeight: 600,
              cursor: isAtMaxRoster ? "not-allowed" : "pointer",
              transition: "background 0.14s ease, border-color 0.14s ease, transform 0.14s ease",
              whiteSpace: "nowrap",
            }}
            onMouseEnter={(e) => {
              if (isAtMaxRoster) return;
              e.currentTarget.style.background = "#F8FAFC";
              e.currentTarget.style.transform = "translateY(-0.5px)";
            }}
            onMouseLeave={(e) => {
              if (isAtMaxRoster) return;
              e.currentTarget.style.background = "#FFFFFF";
              e.currentTarget.style.transform = "translateY(0px)";
            }}
          >
            <Plus size={16} />
            <span>Add Channel</span>
            <ChevronDown size={14} />
          </button>

          {popoverOpen && (
            <div
              ref={popoverRef}
              style={{
                position: "absolute",
                top: 36,
                left: 0,
                width: 260,
                maxHeight: 280,
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                borderRadius: 8,
                boxShadow: "0 4px 16px rgba(0,0,0,0.1)",
                zIndex: 100,
                overflow: "hidden",
                fontFamily: "DM Sans, sans-serif",
              }}
            >
              <div style={{ padding: "8px", borderBottom: "1px solid #F1F5F9" }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    background: "#F8FAFC",
                    borderRadius: 4,
                    padding: "4px 8px",
                  }}
                >
                  <Search size={12} color="#94A3B8" />
                  <input
                    autoFocus
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search channels..."
                    style={{
                      border: "none",
                      background: "transparent",
                      fontSize: 12,
                      color: "#0F172A",
                      outline: "none",
                      width: "100%",
                      fontFamily: "DM Sans, sans-serif",
                    }}
                  />
                </div>
              </div>
              <div style={{ overflowY: "auto", maxHeight: 200 }}>
                {filtered.length === 0 && (
                  <div style={{ padding: "12px 16px", fontSize: 12, color: "#94A3B8" }}>
                    No channels available
                  </div>
                )}
                {filtered.map((ch) => (
                  <button
                    key={ch.channelId}
                    onClick={() => {
                      onAdd(ch);
                      setPopoverOpen(false);
                      setSearch("");
                    }}
                    style={{
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "8px 12px",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      textAlign: "left",
                      fontSize: 13,
                      color: "#0F172A",
                      fontFamily: "DM Sans, sans-serif",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#F8FAFC")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
                  >
                    <PlatformIcon platform={ch.platform} size={14} />
                    <span>{ch.channelName}</span>
                  </button>
                ))}
                {rosterChannels.length > 0 && (
                  <div>
                    <div
                      style={{
                        padding: "6px 12px 4px",
                        fontSize: 11,
                        color: "#94A3B8",
                        fontWeight: 500,
                        textTransform: "uppercase",
                        letterSpacing: "0.06em",
                      }}
                    >
                      In comparison
                    </div>
                    {rosterChannels.map((ch) => (
                      <div
                        key={ch.channelId}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          padding: "6px 8px 6px 12px",
                          opacity: 0.92,
                        }}
                      >
                        <PlatformIcon platform={ch.platform} size={14} />
                        <span
                          style={{
                            fontSize: 13,
                            color: "#0F172A",
                            fontFamily: "DM Sans, sans-serif",
                            flex: 1,
                            minWidth: 0,
                          }}
                        >
                          {ch.channelName}
                        </span>
                        {rosterChannels.length > 1 && (
                          <button
                            type="button"
                            title="Remove channel from comparison workspace"
                            onClick={() => {
                              onRemoveFromRoster(ch.channelId);
                              setPopoverOpen(false);
                            }}
                            style={{
                              flexShrink: 0,
                              fontSize: 11,
                              fontWeight: 600,
                              color: "#B91C1C",
                              background: "transparent",
                              border: "none",
                              cursor: "pointer",
                              padding: "4px 6px",
                              borderRadius: 4,
                              fontFamily: "DM Sans, sans-serif",
                            }}
                          >
                            Remove
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
