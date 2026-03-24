import React from "react";
import { PlatformIcon } from "./PlatformIcon";

const STATUS_CONFIG: Record<
  string,
  { dotColor: string; textColor: string; icon: string }
> = {
  healthy: { dotColor: "#16A34A", textColor: "#16A34A", icon: "check" },
  stale: { dotColor: "#D97706", textColor: "#D97706", icon: "warn" },
  error: { dotColor: "#DC2626", textColor: "#DC2626", icon: "x" },
};

function StatusIcon({ type, color }: { type: string; color: string }) {
  if (type === "check")
    return (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <circle cx="7" cy="7" r="6.5" fill={color} fillOpacity="0.15" stroke={color} strokeWidth="1" />
        <path d="M4.5 7l1.8 1.8 3-3.6" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  if (type === "warn")
    return (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <circle cx="7" cy="7" r="6.5" fill={color} fillOpacity="0.15" stroke={color} strokeWidth="1" />
        <path d="M7 3.8v3.2l2.2 1.3" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <circle cx="7" cy="7" r="6.5" fill={color} fillOpacity="0.15" stroke={color} strokeWidth="1" />
      <path d="M4.5 4.5l5 5M9.5 4.5l-5 5" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export interface IntegrationCardButton {
  label: string;
  variant: "primary" | "secondary";
  flex?: boolean;
}

export interface IntegrationCardProps {
  platform: string;
  platformKey: string;
  statusType: "healthy" | "stale" | "error";
  statusLine: string;
  subLine?: string;
  eventLine?: string;
  buttons: IntegrationCardButton[];
}

export function IntegrationCard({ platform, platformKey, statusType, statusLine, subLine, eventLine, buttons, onButtonClick }: IntegrationCardProps & { onButtonClick?: (label: string) => void }) {
  const cfg = STATUS_CONFIG[statusType] || STATUS_CONFIG.healthy;
  const isAlert = statusType === "stale" || statusType === "error";
  const baseShadow = "0 2px 8px rgba(0,0,0,0.10)"; // shared depth for all cards
  const baseBorder = "1px solid #E5E7EB"; // shared base border for all cards
  const alertRingShadow = `0 0 0 2px ${cfg.dotColor}88, 0 0 22px ${cfg.dotColor}55, 0 0 40px ${cfg.dotColor}33`;

  return (
    <div
      style={{
        background: "#FFFFFF",
        border: baseBorder,
        borderRadius: "8px",
        boxShadow: isAlert ? `${baseShadow}, ${alertRingShadow}` : baseShadow,
        padding: "20px",
        position: "relative",
        display: "flex",
        flexDirection: "column",
        minHeight: "172px",
      }}
    >
      {/* Status dot */}
      <div
        style={{
          position: "absolute",
          top: "14px",
          right: "14px",
          width: "8px",
          height: "8px",
          borderRadius: "50%",
          background: cfg.dotColor,
          boxShadow: `0 0 0 2px ${cfg.dotColor}22`,
        }}
      />

      {/* Platform name row */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
        <PlatformIcon platform={platformKey} size={28} />
        <span
          style={{
            fontFamily: "'Inter', sans-serif",
            fontSize: "15px",
            fontWeight: 600,
            color: "#111827",
          }}
        >
          {platform}
        </span>
      </div>

      {/* Status line */}
      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "6px" }}>
        <StatusIcon type={cfg.icon} color={cfg.textColor} />
        <span
          style={{
            fontFamily: "'Inter', sans-serif",
            fontSize: "12.5px",
            fontWeight: 500,
            color: cfg.textColor,
          }}
        >
          {statusLine}
        </span>
      </div>

      {/* Sub line */}
      {subLine && (
        <p
          style={{
            fontFamily: "'Inter', sans-serif",
            fontSize: "12px",
            color: "#6B7280",
            margin: "0 0 4px 0",
            paddingLeft: "19px",
          }}
        >
          {subLine}
        </p>
      )}

      {/* Event line */}
      {eventLine && (
        <p
          style={{
            fontFamily: "'Inter', sans-serif",
            fontSize: "12px",
            color: "#6B7280",
            margin: "0",
            paddingLeft: "19px",
          }}
        >
          {eventLine}
        </p>
      )}

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Buttons */}
      <div
        style={{
          display: "flex",
          gap: "8px",
          marginTop: "14px",
          paddingTop: "8px",
          borderTop: "1px solid rgba(209, 213, 219, 0.6)", // subtle separator
        }}
      >
        {buttons.map((btn) => (
          <button
            key={btn.label}
            onClick={() => onButtonClick?.(btn.label)}
            style={{
              flex: btn.flex ? 1 : undefined,
              padding: "6px 12px",
              border: btn.variant === "primary" ? "none" : "1px solid #D1D5DB",
              borderRadius: "6px",
              background: btn.variant === "primary" ? "#1F2937" : "#FFFFFF",
              fontFamily: "'Inter', sans-serif",
              fontSize: "12.5px",
              fontWeight: 500,
              color: btn.variant === "primary" ? "#FFFFFF" : "#374151",
              cursor: "pointer",
              textAlign: "center",
            }}
          >
            {btn.label}
          </button>
        ))}
      </div>
    </div>
  );
}
