import React from "react";

export type MetricCardStatus = "success" | "warning" | "error" | "info";

interface MetricCardProps {
  label: string;
  value: string | number;
  delta?: number;
  deltaLabel?: string;
  status?: MetricCardStatus;
  badgeText?: string;
  onClick?: () => void;
}

/* Inline icons — Alert uses branded SVG asset, arrows remain inline */

function AlertTriangleIcon({ className }: { className?: string }) {
  return (
    <img
      src="/warning-svgrepo-com.svg"
      className={className}
      width={20}
      height={20}
      alt="Warning"
      aria-hidden="true"
    />
  );
}

function ArrowUpIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <line x1="12" y1="19" x2="12" y2="5" />
      <polyline points="5 12 12 5 19 12" />
    </svg>
  );
}

function ArrowDownIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <line x1="12" y1="5" x2="12" y2="19" />
      <polyline points="19 12 12 19 5 12" />
    </svg>
  );
}

export function MetricCard({
  label,
  value,
  delta,
  deltaLabel,
  status = "success",
  badgeText,
  onClick,
}: MetricCardProps) {
  const isPositive = delta !== undefined && delta > 0;
  const isNegative = delta !== undefined && delta < 0;

  const badgeClass =
    status === "error"
      ? "dhd-metric-badge dhd-metric-badge-error"
      : status === "warning"
      ? "dhd-metric-badge dhd-metric-badge-warning"
      : status === "info"
      ? "dhd-metric-badge dhd-metric-badge-info"
      : "dhd-metric-badge dhd-metric-badge-success";

  const alertIconClass =
    status === "error"
      ? "dhd-metric-alert-icon dhd-metric-alert-icon-error"
      : "dhd-metric-alert-icon dhd-metric-alert-icon-warning";

  const deltaClass = isPositive
    ? "dhd-metric-delta-positive"
    : isNegative
    ? "dhd-metric-delta-negative"
    : "dhd-metric-delta-neutral";

  return (
    <div className="dhd-metric-card" onClick={onClick} role={onClick ? "button" : undefined} tabIndex={onClick ? 0 : undefined}>
      <div className="dhd-metric-card-header">
        <span className="dhd-metric-label">{label}</span>
        {badgeText && (
          <span className={badgeClass}>{badgeText}</span>
        )}
      </div>

      <div className="dhd-metric-value-row">
        <span className="dhd-metric-value">{value}</span>
        {status !== "success" && status !== "info" && (
          <AlertTriangleIcon className={alertIconClass} />
        )}
      </div>

      {delta !== undefined && deltaLabel && (
        <div className="dhd-metric-delta">
          {isPositive ? (
            <ArrowUpIcon className="dhd-metric-delta-icon dhd-metric-delta-positive" />
          ) : isNegative ? (
            <ArrowDownIcon className="dhd-metric-delta-icon dhd-metric-delta-negative" />
          ) : null}
          <span className={deltaClass}>{Math.abs(delta)}%</span>
          <span className="dhd-metric-delta-label">{deltaLabel}</span>
        </div>
      )}
    </div>
  );
}
