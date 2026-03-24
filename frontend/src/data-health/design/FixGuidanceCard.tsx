import React, { useCallback, useEffect, useState } from "react";
import { X } from "lucide-react";
import { PlatformIcon } from "./PlatformIcon";
import type { FixGuidanceCardProps, FixGuidanceSeverity } from "./fixGuidanceTypes";
import "./fix-guidance.css";

function formatRelativeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  const m = Math.round((Date.now() - then) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}

const SEVERITY_META: Record<
  FixGuidanceSeverity,
  { label: string; titleColor: string; badgeBg: string }
> = {
  critical: {
    label: "Critical",
    titleColor: "var(--fgc-critical, #dc2626)",
    badgeBg: "var(--fgc-critical, #dc2626)",
  },
  caution: {
    label: "Caution",
    titleColor: "var(--fgc-caution, #d97706)",
    badgeBg: "var(--fgc-caution, #d97706)",
  },
  info: {
    label: "Info",
    titleColor: "var(--fgc-info, #2563eb)",
    badgeBg: "var(--fgc-info, #2563eb)",
  },
};

export function FixGuidanceCard(props: FixGuidanceCardProps) {
  const {
    id,
    severity,
    issue,
    impact,
    remediation,
    timestamp,
    isDismissible,
    onDismiss,
    platformKey,
  } = props;

  const [dismissing, setDismissing] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const fn = () => setReducedMotion(mq.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);

  const meta = SEVERITY_META[severity];

  const handleDismissClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!onDismiss) return;
      setDismissing(true);
      const ms = reducedMotion ? 0 : 200;
      window.setTimeout(() => {
        onDismiss();
      }, ms);
    },
    [onDismiss, reducedMotion],
  );

  const secondaryIsGhost =
    remediation.secondary.type === "dismiss" || remediation.secondary.type === "defer";

  const cardTone =
    severity === "critical"
      ? "fgc-card fgc-card--critical"
      : severity === "caution"
        ? "fgc-card fgc-card--caution"
        : "fgc-card fgc-card--info";

  return (
    <article
      className={`${cardTone} ${dismissing ? "fgc-card--dismissing" : ""}`}
      aria-labelledby={`fgc-title-${id}`}
      data-reduced-motion={reducedMotion ? "true" : undefined}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 8,
          marginBottom: 6,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              fontFamily: "'DM Sans', system-ui, sans-serif",
              fontSize: 10,
              fontWeight: 600,
              color: "#fff",
              background: meta.badgeBg,
              padding: "2px 8px",
              borderRadius: 4,
              letterSpacing: "0.02em",
            }}
          >
            {meta.label}
          </span>
          {platformKey && (
            <span style={{ display: "inline-flex", alignItems: "center" }}>
              <PlatformIcon platform={platformKey} size={16} />
            </span>
          )}
        </div>
        {isDismissible && onDismiss && (
          <button
            type="button"
            onClick={handleDismissClick}
            className="fgc-btn-ghost"
            title="Dismiss"
            aria-label="Dismiss this guidance"
            style={{ minWidth: 28, flexShrink: 0, padding: "2px 4px" }}
          >
            <X size={15} strokeWidth={2} aria-hidden style={{ color: "#94a3b8" }} />
          </button>
        )}
      </div>

      <h3
        id={`fgc-title-${id}`}
        style={{
          margin: "0 0 2px 0",
          fontFamily: "'DM Sans', system-ui, sans-serif",
          fontSize: 15,
          fontWeight: 600,
          lineHeight: 1.3,
          color: meta.titleColor,
        }}
      >
        {issue.title}
      </h3>
      <p
        style={{
          margin: "0 0 6px 0",
          fontFamily: "'DM Sans', system-ui, sans-serif",
          fontSize: 12,
          fontWeight: 400,
          lineHeight: 1.4,
          color: "var(--fgc-text-secondary, #475569)",
        }}
      >
        {issue.description}
      </p>

      <p
        style={{
          margin: "0 0 6px 0",
          fontFamily: "'DM Sans', system-ui, sans-serif",
          fontSize: 12,
          fontWeight: 400,
          lineHeight: 1.45,
          color: "var(--fgc-text-primary, #0f172a)",
        }}
      >
        {impact.description}
      </p>
      {impact.affectedChannels && impact.affectedChannels.length > 0 && (
        <p style={{ margin: "0 0 4px 0", fontSize: 11, color: "#475569", lineHeight: 1.35 }}>
          Affected channels: {impact.affectedChannels.join(", ")}
        </p>
      )}
      {impact.monetaryRisk && (
        <p style={{ margin: "0 0 6px 0", fontSize: 12, color: "#0f172a" }}>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>
            {impact.monetaryRisk}
          </span>
        </p>
      )}

      <div
        className="fgc-actions"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          flexWrap: "wrap",
          marginTop: 2,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <button
            type="button"
            className="fgc-btn-primary"
            onClick={() => remediation.primary.action()}
          >
            {remediation.primary.label}
          </button>
          {remediation.primary.estimatedTime && (
            <span style={{ fontSize: 10, color: "#64748b", maxWidth: 120, lineHeight: 1.25 }}>
              {remediation.primary.estimatedTime}
            </span>
          )}
          {secondaryIsGhost ? (
            <button
              type="button"
              className="fgc-btn-ghost"
              onClick={() => remediation.secondary.action()}
            >
              {remediation.secondary.label}
            </button>
          ) : (
            <button
              type="button"
              className="fgc-btn-secondary"
              onClick={() => remediation.secondary.action()}
            >
              {remediation.secondary.label}
            </button>
          )}
        </div>
        <time
          dateTime={timestamp}
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
            fontWeight: 400,
            color: "var(--fgc-text-tertiary, #94a3b8)",
            flexShrink: 0,
          }}
        >
          {formatRelativeAgo(timestamp)}
        </time>
      </div>
    </article>
  );
}
