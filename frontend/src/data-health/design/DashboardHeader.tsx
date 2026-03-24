import React from "react";

export function DashboardHeader({
  lastUpdated = "3 min ago",
  onRefresh,
}: {
  lastUpdated?: string;
  onRefresh?: () => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        height: "56px",
        borderBottom: "1px solid #E2E8F0",
        background: "#FFFFFF",
        padding: "0 24px",
        position: "sticky",
        top: 0,
        zIndex: 60,
        flexShrink: 0,
      }}
    >
      <h1
        style={{
          fontSize: "20px",
          fontWeight: 800,
          color: "#0F172A",
          letterSpacing: "-0.01em",
          fontFamily: "var(--font-sans)",
          margin: 0,
        }}
      >
        Data Health
      </h1>
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <span
          style={{
            fontFamily: "'Inter', sans-serif",
            fontSize: "12px",
            fontWeight: 400,
            color: "#6B7280",
          }}
        >
          Updated {lastUpdated}
        </span>
        <button
          onClick={onRefresh}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "6px 12px",
            border: "1px solid #D1D5DB",
            borderRadius: "6px",
            background: "#FFFFFF",
            fontFamily: "'Inter', sans-serif",
            fontSize: "13px",
            fontWeight: 500,
            color: "#374151",
            cursor: "pointer",
            lineHeight: 1.4,
          }}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M1 7A6 6 0 0 1 11.83 3.5M13 7A6 6 0 0 1 2.17 10.5" />
            <path d="M11 1.5l.83 2-2 .5M3 12.5l-.83-2 2-.5" />
          </svg>
          Refresh All
        </button>
      </div>
    </div>
  );
}
