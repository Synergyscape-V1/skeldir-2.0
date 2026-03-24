import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  RefreshCw,
  AlertCircle,
  Clock,
  Plug,
  Copy,
  Check,
  Settings,
  Loader2,
  XCircle,
  Circle,
  ChevronDown,
  X,
  ExternalLink,
  MessageSquare,
} from "lucide-react";
import type { PlatformIntegrationsRendererProps } from "../../core/types";
import "./styles.css";

/* ══════════════════════════════════════════════════════════════
   Platform Integrations — Source of Truth Design
   Faithful translation of the standalone design build.
   ══════════════════════════════════════════════════════════════ */

/* ── Types ── */

interface IntegrationError {
  errorType: string;
  errorMessage: string;
  correlationId: string;
  occurredAt: string;
  occurrenceCount: number;
  firstOccurredAt: string;
  remediationSteps: RemediationStep[];
}

interface RemediationStep {
  stepNumber: number;
  instruction: string;
  actionType: string;
  actionLabel?: string;
  actionUrl?: string;
}

interface ConnectionHealth {
  syncSuccessRateFormatted: string | null;
  lastSuccessfulSyncAt: string;
  failedSyncsLast7d: number;
  totalSyncsLast7d: number;
}

interface AuthMetadata {
  authMethod: string;
  connectedByUserEmail: string;
  connectedAt: string;
  tokenExpiresInDays: number | null;
  scopesGranted: string[];
}

interface SyncProgress {
  percent: number;
  currentOperation: string;
  estimatedSecondsRemaining: number;
}

type IntegrationStatus =
  | "connected"
  | "error"
  | "needs_reauth"
  | "not_connected"
  | "syncing"
  | "connecting";

interface Integration {
  platformId: string;
  displayName: string;
  platformType: string;
  status: IntegrationStatus;
  lastSyncRelative: string | null;
  nextSyncRelative: string | null;
  dataFreshness: string | null;
  syncProgress: SyncProgress | null;
  error: IntegrationError | null;
  connectionHealth: ConnectionHealth | null;
  authMetadata: AuthMetadata | null;
}

interface CardAction {
  type: string;
  platformId: string;
}

interface SortState {
  field: string;
  direction: string;
}

interface FilterState {
  status: string;
  type: string;
}

/* ── Mock Data ── */

const MOCK_INTEGRATIONS: Integration[] = [
  {
    platformId: "meta",
    displayName: "Meta Ads",
    platformType: "ad_platform",
    status: "error",
    lastSyncRelative: "3 hours ago",
    nextSyncRelative: null,
    dataFreshness: "stale",
    syncProgress: null,
    error: {
      errorType: "oauth_token_expired",
      errorMessage:
        "Your OAuth token has expired. Meta Ads requires re-authentication to resume syncing.",
      correlationId: "SKL-ERR-A3F9B21C",
      occurredAt: "2026-03-09T02:41:00Z",
      occurrenceCount: 3,
      firstOccurredAt: "2026-03-08T14:00:00Z",
      remediationSteps: [
        {
          stepNumber: 1,
          instruction:
            "Go to Meta Business Manager \u2192 Business Settings \u2192 Integrations",
          actionType: "navigate_third_party",
          actionLabel: "Open Meta Business Manager",
          actionUrl: "https://business.facebook.com/settings/integrations",
        },
        {
          stepNumber: 2,
          instruction: "Revoke the existing Skeldir OAuth connection",
          actionType: "click_cta",
        },
        {
          stepNumber: 3,
          instruction:
            "Click Reconnect below to re-authorize Skeldir\u2019s access",
          actionType: "click_cta",
        },
      ],
    },
    connectionHealth: {
      syncSuccessRateFormatted: "62.0%",
      lastSuccessfulSyncAt: "2026-03-08T23:00:00Z",
      failedSyncsLast7d: 4,
      totalSyncsLast7d: 28,
    },
    authMetadata: {
      authMethod: "oauth2",
      connectedByUserEmail: "admin@company.com",
      connectedAt: "2025-09-01T10:00:00Z",
      tokenExpiresInDays: 0,
      scopesGranted: ["ads.read"],
    },
  },
  {
    platformId: "linkedin",
    displayName: "LinkedIn Ads",
    platformType: "ad_platform",
    status: "needs_reauth",
    lastSyncRelative: "3h ago",
    nextSyncRelative: null,
    dataFreshness: "stale",
    syncProgress: null,
    error: {
      errorType: "oauth_token_expired",
      errorMessage:
        "OAuth token expires in 7 days. Re-authenticate to prevent data gaps.",
      correlationId: "SKL-WARN-B2C8D3E4",
      occurredAt: "2026-03-09T00:00:00Z",
      occurrenceCount: 1,
      firstOccurredAt: "2026-03-09T00:00:00Z",
      remediationSteps: [
        {
          stepNumber: 1,
          instruction:
            "Click Reconnect to re-authorize LinkedIn Ads access.",
          actionType: "click_cta",
        },
        {
          stepNumber: 2,
          instruction:
            "Authorize with the LinkedIn account that has Campaign Manager access.",
          actionType: "click_cta",
        },
      ],
    },
    connectionHealth: {
      syncSuccessRateFormatted: "94.0%",
      lastSuccessfulSyncAt: "2026-03-09T06:00:00Z",
      failedSyncsLast7d: 2,
      totalSyncsLast7d: 33,
    },
    authMetadata: {
      authMethod: "oauth2",
      connectedByUserEmail: "admin@company.com",
      connectedAt: "2025-10-15T09:00:00Z",
      tokenExpiresInDays: 7,
      scopesGranted: ["ads.read", "ads.write"],
    },
  },
  {
    platformId: "stripe",
    displayName: "Stripe",
    platformType: "revenue_source",
    status: "connected",
    lastSyncRelative: "2 min ago",
    nextSyncRelative: "Real-time webhook",
    dataFreshness: "fresh",
    syncProgress: null,
    error: null,
    connectionHealth: {
      syncSuccessRateFormatted: "98.2%",
      lastSuccessfulSyncAt: "2026-03-09T08:58:00Z",
      failedSyncsLast7d: 1,
      totalSyncsLast7d: 52,
    },
    authMetadata: {
      authMethod: "webhook",
      connectedByUserEmail: "admin@company.com",
      connectedAt: "2025-06-01T08:00:00Z",
      tokenExpiresInDays: null,
      scopesGranted: [],
    },
  },
  {
    platformId: "google_ads",
    displayName: "Google Ads",
    platformType: "ad_platform",
    status: "connected",
    lastSyncRelative: "5 min ago",
    nextSyncRelative: "Hourly",
    dataFreshness: "fresh",
    syncProgress: null,
    error: null,
    connectionHealth: {
      syncSuccessRateFormatted: null,
      lastSuccessfulSyncAt: "2026-03-09T08:55:00Z",
      failedSyncsLast7d: 0,
      totalSyncsLast7d: 168,
    },
    authMetadata: {
      authMethod: "oauth2",
      connectedByUserEmail: "admin@company.com",
      connectedAt: "2025-07-10T14:00:00Z",
      tokenExpiresInDays: null,
      scopesGranted: ["ads.read"],
    },
  },
  {
    platformId: "paypal",
    displayName: "PayPal",
    platformType: "revenue_source",
    status: "connected",
    lastSyncRelative: "45 min ago",
    nextSyncRelative: "Hourly",
    dataFreshness: "aging",
    syncProgress: null,
    error: null,
    connectionHealth: {
      syncSuccessRateFormatted: "96.5%",
      lastSuccessfulSyncAt: "2026-03-09T08:15:00Z",
      failedSyncsLast7d: 1,
      totalSyncsLast7d: 47,
    },
    authMetadata: {
      authMethod: "api_key",
      connectedByUserEmail: "admin@company.com",
      connectedAt: "2025-08-22T11:00:00Z",
      tokenExpiresInDays: null,
      scopesGranted: [],
    },
  },
  {
    platformId: "tiktok",
    displayName: "TikTok Ads",
    platformType: "ad_platform",
    status: "connected",
    lastSyncRelative: "5 min ago",
    nextSyncRelative: "Hourly",
    dataFreshness: "fresh",
    syncProgress: null,
    error: null,
    connectionHealth: {
      syncSuccessRateFormatted: "99.1%",
      lastSuccessfulSyncAt: "2026-03-09T08:55:00Z",
      failedSyncsLast7d: 0,
      totalSyncsLast7d: 168,
    },
    authMetadata: {
      authMethod: "oauth2",
      connectedByUserEmail: "admin@company.com",
      connectedAt: "2025-11-01T10:00:00Z",
      tokenExpiresInDays: null,
      scopesGranted: ["ads.read"],
    },
  },
  {
    platformId: "woocommerce",
    displayName: "WooCommerce",
    platformType: "revenue_source",
    status: "connected",
    lastSyncRelative: "2 min ago",
    nextSyncRelative: "Hourly",
    dataFreshness: "fresh",
    syncProgress: null,
    error: null,
    connectionHealth: {
      syncSuccessRateFormatted: "99.0%",
      lastSuccessfulSyncAt: "2026-03-09T08:58:00Z",
      failedSyncsLast7d: 0,
      totalSyncsLast7d: 168,
    },
    authMetadata: {
      authMethod: "api_key",
      connectedByUserEmail: "admin@company.com",
      connectedAt: "2025-05-15T12:00:00Z",
      tokenExpiresInDays: null,
      scopesGranted: [],
    },
  },
  {
    platformId: "bigcommerce",
    displayName: "BigCommerce",
    platformType: "revenue_source",
    status: "not_connected",
    lastSyncRelative: null,
    nextSyncRelative: null,
    dataFreshness: null,
    syncProgress: null,
    error: null,
    connectionHealth: null,
    authMetadata: null,
  },
];

/* ── Platform Logos: use canonical asset SVGs for consistency ── */

function PlatformAssetLogo({
  src,
  alt,
  size = 24,
}: {
  src: string;
  alt: string;
  size?: number;
}) {
  return (
    <img
      src={src}
      alt={alt}
      width={size}
      height={size}
      style={{ display: "block", flexShrink: 0 }}
      loading="lazy"
      decoding="async"
    />
  );
}

function MetaLogo({ size = 24 }: { size?: number }) {
  return (
    <PlatformAssetLogo
      src="/assets/platform-icons/meta-ads.svg"
      alt="Meta Ads"
      size={size}
    />
  );
}

function LinkedInLogo({ size = 24 }: { size?: number }) {
  return (
    <PlatformAssetLogo
      src="/assets/platform-icons/linkedin-ads.svg"
      alt="LinkedIn Ads"
      size={size}
    />
  );
}

function StripeLogo({ size = 24 }: { size?: number }) {
  return (
    <PlatformAssetLogo
      src="/assets/platform-icons/stripe.svg"
      alt="Stripe"
      size={size}
    />
  );
}

function GoogleAdsLogo({ size = 24 }: { size?: number }) {
  return (
    <PlatformAssetLogo
      src="/assets/platform-icons/google-ads.svg"
      alt="Google Ads"
      size={size}
    />
  );
}

function PayPalLogo({ size = 24 }: { size?: number }) {
  return (
    <PlatformAssetLogo
      src="/assets/platform-icons/paypal.svg"
      alt="PayPal"
      size={size}
    />
  );
}

function TikTokLogo({ size = 24 }: { size?: number }) {
  return (
    <PlatformAssetLogo
      src="/assets/platform-icons/tiktok-ads.svg"
      alt="TikTok Ads"
      size={size}
    />
  );
}

function WooCommerceLogo({ size = 24 }: { size?: number }) {
  return (
    <PlatformAssetLogo
      src="/assets/platform-icons/woocommerce.svg"
      alt="WooCommerce"
      size={size}
    />
  );
}

function BigCommerceLogo({
  size = 24,
  dimmed = false,
}: {
  size?: number;
  dimmed?: boolean;
}) {
  return (
    <img
      src="/assets/platform-icons/bigcommerce.svg"
      alt="BigCommerce"
      width={size}
      height={size}
      style={{ display: "block", flexShrink: 0, opacity: dimmed ? 0.4 : 1 }}
      loading="lazy"
      decoding="async"
    />
  );
}

function getPlatformLogo(
  platformId: string,
  size = 24,
  dimmed = false
): React.ReactNode {
  const effectiveSize = platformId === "stripe" ? size * 1.4 : size;
  const logos: Record<string, React.ReactNode> = {
    meta: <MetaLogo size={size} />,
    linkedin: <LinkedInLogo size={size} />,
    stripe: <StripeLogo size={effectiveSize} />,
    google_ads: <GoogleAdsLogo size={size} />,
    paypal: <PayPalLogo size={size} />,
    tiktok: <TikTokLogo size={size} />,
    woocommerce: <WooCommerceLogo size={size} />,
    bigcommerce: <BigCommerceLogo size={size} dimmed={dimmed} />,
  };
  return logos[platformId] || null;
}

/* ── StatusBadge ── */

const STATUS_CONFIG: Record<
  string,
  {
    label: string;
    icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>;
    color: string;
    border?: string;
    spin?: boolean;
  }
> = {
  connected: {
    label: "Connected",
    icon: Check,
    color: "var(--status-verified)",
  },
  needs_reauth: {
    label: "Needs Re-auth",
    icon: Clock,
    color: "var(--status-caution)",
  },
  error: {
    label: "Error",
    icon: XCircle,
    color: "var(--status-critical)",
  },
  not_connected: {
    label: "Not Connected",
    icon: Circle,
    color: "var(--text-tertiary)",
    border: "1px solid var(--border-default)",
  },
  syncing: {
    label: "Syncing...",
    icon: Loader2,
    color: "var(--status-info)",
    spin: true,
  },
  connecting: {
    label: "Connecting...",
    icon: Loader2,
    color: "var(--status-info)",
    spin: true,
  },
};

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.not_connected;
  const Icon = cfg.icon;
  const isSolid = status !== "not_connected" && status !== "error";
  const isError = status === "error";
  const isConnected = status === "connected";
  const isNeedsReauth = status === "needs_reauth";

  return (
    <span
      role="status"
      aria-live="polite"
      aria-atomic="true"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        padding: "3px 8px",
        backgroundColor: isConnected
          ? "rgba(16,185,129,0.22)"
          : isNeedsReauth
            ? "rgba(245,158,11,0.30)"
          : isSolid
            ? cfg.color
            : "transparent",
        border:
          cfg.border ||
          (isError
            ? "1px solid var(--status-critical)"
            : isNeedsReauth
              ? "none"
              : isSolid
              ? "none"
              : "1px solid var(--border-default)"),
        borderRadius: "var(--radius-full)",
        color: isConnected
          ? "var(--status-verified)"
          : isNeedsReauth
            ? "var(--status-caution)"
          : isSolid
            ? "#FFFFFF"
            : isError
              ? "var(--status-critical)"
              : "var(--text-secondary)",
        fontSize: "11px",
        fontWeight: 600,
        letterSpacing: "0.01em",
        whiteSpace: "nowrap",
      }}
    >
      {isConnected ? (
        <span
          aria-hidden="true"
          style={{
            width: 14,
            height: 14,
            borderRadius: "9999px",
            backgroundColor: "var(--status-verified)",
            color: "#FFFFFF",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 10,
            fontWeight: 800,
            lineHeight: 1,
            flexShrink: 0,
          }}
        >
          ✓
        </span>
      ) : isError ? (
        <span
          aria-hidden="true"
          style={{
            width: 14,
            height: 14,
            borderRadius: "9999px",
            backgroundColor: "var(--status-critical)",
            color: "#FFFFFF",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 10,
            fontWeight: 800,
            lineHeight: 1,
            flexShrink: 0,
          }}
        >
          ✕
        </span>
      ) : isNeedsReauth ? (
        <AlertCircle size={11} aria-hidden="true" />
      ) : (
        <Icon
          size={12}
          aria-hidden="true"
          style={cfg.spin ? { animation: "pi-spin 1s linear infinite" } : undefined}
        />
      )}
      {cfg.label}
    </span>
  );
}

/* ── IntegrationsTopBar ── */

function IntegrationsTopBar({
  isResyncing,
  onResyncAll,
}: {
  isResyncing: boolean;
  onResyncAll: () => void;
}) {
  return (
    <div
      style={{
        position: "sticky",
        top: 0,
        zIndex: 30,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        height: 56,
        borderBottom: "1px solid #E2E8F0",
        background: "transparent",
        padding: "0 24px",
        flexShrink: 0,
      }}
    >
      <h1
        style={{
          fontSize: 20,
          fontWeight: 800,
          color: "#0F172A",
          letterSpacing: "-0.01em",
          fontFamily: "var(--font-sans)",
          margin: 0,
        }}
      >
        Integrations
      </h1>

      <button
        onClick={!isResyncing ? onResyncAll : undefined}
        disabled={isResyncing}
        aria-label={
          isResyncing
            ? "Re-syncing all platforms — in progress"
            : "Re-sync all platforms"
        }
        aria-busy={isResyncing}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          height: 36,
          padding: "0 14px",
          backgroundColor: "#FFFFFF",
          border: "1px solid #E2E8F0",
          borderRadius: 6,
          color: "#0F172A",
          fontSize: 13,
          fontWeight: 500,
          cursor: isResyncing ? "not-allowed" : "pointer",
          opacity: isResyncing ? 0.7 : 1,
          transition: "background 150ms ease, border-color 150ms ease",
          fontFamily: "var(--font-sans)",
        }}
        onMouseEnter={(e) => {
          if (!isResyncing) {
            e.currentTarget.style.backgroundColor = "#F8FAFC";
            e.currentTarget.style.borderColor = "#CBD5E1";
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = "#FFFFFF";
          e.currentTarget.style.borderColor = "#E2E8F0";
        }}
      >
        {isResyncing ? (
          <Loader2
            size={14}
            style={{ animation: "pi-spin 1s linear infinite" }}
          />
        ) : (
          <RefreshCw size={14} />
        )}
        {isResyncing ? "Syncing..." : "Re-sync All"}
      </button>
    </div>
  );
}

/* ── ConnectionHealthBand ── */

function SkeletonBar({
  width = 60,
  height = 14,
}: {
  width?: number;
  height?: number;
}) {
  return (
    <div
      style={{
        width,
        height,
        borderRadius: 4,
        background:
          "linear-gradient(90deg, #e8ecf0 25%, #f4f6f8 50%, #e8ecf0 75%)",
        backgroundSize: "400px 100%",
        animation: "pi-shimmer 1.5s ease-in-out infinite",
      }}
    />
  );
}

function StatCell({
  iconColor,
  count,
  label,
  isLast,
  isLoading,
}: {
  iconColor: string;
  count: number;
  label: string;
  isLast?: boolean;
  isLoading?: boolean;
}) {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "2px",
        padding: "14px var(--space-4)",
        // Keep this deterministic so the whole band appears as one continuous
        // darker-gray overlay across all 4 stats.
        backgroundColor: "#EFF2F5",
        // Subtle separator between the 4 horizontal stat cells.
        borderRight: isLast
          ? "none"
          : "1px solid rgba(148,163,184,0.35)",
      }}
    >
      {isLoading ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <SkeletonBar width={22} height={22} />
          <SkeletonBar width={28} height={20} />
          <SkeletonBar width={70} height={11} />
        </div>
      ) : (
        <>
          {/* Filled vs hollow status glyphs */}
          <span
            aria-hidden="true"
            style={{
              width: 22,
              height: 22,
              borderRadius: "999px",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: label === "Error" ? 14 : 13,
              fontWeight: 700,
              color: label === "Not Connected" ? iconColor : "#FFFFFF",
              backgroundColor:
                label === "Not Connected" ? "transparent" : iconColor,
              border:
                label === "Not Connected"
                  ? `2px solid ${iconColor}`
                  : "none",
            }}
          >
            {label === "Connected" && "✓"}
            {label === "Error" && "✕"}
            {label === "Needs Attention" && (
              <AlertCircle size={14} color="#FFFFFF" strokeWidth={2} />
            )}
          </span>
          <span
            style={{
              fontSize: "28px",
              fontWeight: 700,
              lineHeight: 1.15,
              color: "var(--text-primary)",
              marginTop: "1px",
            }}
          >
            {count}
          </span>
          <span
            style={{
              fontSize: "12px",
              fontWeight: 400,
              color: "var(--text-secondary)",
              marginTop: "1px",
            }}
          >
            {label}
          </span>
        </>
      )}
    </div>
  );
}

function ConnectionHealthBand({
  connected,
  needsAttention,
  errors,
  notConnected,
  isLoading,
}: {
  connected: number;
  needsAttention: number;
  errors: number;
  notConnected: number;
  isLoading: boolean;
}) {
  return (
    <section
      role="region"
      aria-label="Platform connection health overview"
      aria-live="polite"
      style={{
        display: "flex",
        // Slightly lighter gray than the previous iteration (less visually heavy),
        // while still remaining a darker overlay than the original surface.
        backgroundColor: "#EFF2F5",
        borderBottom: "1px solid var(--border-subtle)",
        borderTop: "1px solid var(--border-subtle)",
        // Full-bleed across the interface (independent of the maxWidth wrapper).
        width: "100vw",
        marginTop: "var(--space-5)",
        marginBottom: "var(--space-5)",
        // This component is rendered inside a container with `padding: 0 var(--space-8)`,
        // so subtract that padding to ensure the band is truly edge-to-edge.
        marginLeft: "calc(50% - 50vw - var(--space-8))",
        marginRight: "calc(50% - 50vw - var(--space-8))",
        boxSizing: "border-box",
      }}
    >
      <StatCell
        iconColor="var(--status-verified)"
        count={connected}
        label="Connected"
        isLoading={isLoading}
      />
      <StatCell
        iconColor="var(--status-caution)"
        count={needsAttention}
        label="Needs Attention"
        isLoading={isLoading}
      />
      <StatCell
        iconColor="var(--status-critical)"
        count={errors}
        label="Error"
        isLoading={isLoading}
      />
      <StatCell
        iconColor="var(--text-tertiary)"
        count={notConnected}
        label="Not Connected"
        isLast
        isLoading={isLoading}
      />
    </section>
  );
}

/* ── SortFilterBar ── */

function DropdownButton({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: string; label: string }[];
  value: string;
  onChange: (val: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const selectedLabel =
    options.find((o) => o.value === value)?.label || label;
  const isActive = value !== "all" && value !== options[0]?.value;

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen(!open)}
        aria-haspopup="listbox"
        aria-expanded={open}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "4px",
          height: "32px",
          padding: "0 10px",
          backgroundColor: isActive
            ? "var(--brand-primary-light)"
            : "var(--bg-surface)",
          border: `1px solid ${isActive ? "var(--brand-primary)" : "var(--border-default)"}`,
          borderRadius: "var(--radius-full)",
          color: isActive ? "var(--brand-primary)" : "var(--text-secondary)",
          fontSize: "12px",
          fontWeight: 500,
          cursor: "pointer",
          fontFamily: "inherit",
          transition: "all var(--duration-fast)",
          whiteSpace: "nowrap",
        }}
        onMouseEnter={(e) => {
          if (!isActive)
            e.currentTarget.style.borderColor = "var(--border-strong)";
        }}
        onMouseLeave={(e) => {
          if (!isActive)
            e.currentTarget.style.borderColor = "var(--border-default)";
        }}
      >
        {selectedLabel}
        <ChevronDown size={12} />
      </button>
      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            backgroundColor: "var(--bg-surface)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-md)",
            zIndex: 60,
            minWidth: "160px",
            overflow: "hidden",
          }}
        >
          {options.map((opt) => (
            <button
              key={opt.value}
              onClick={() => {
                onChange(opt.value);
                setOpen(false);
              }}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "8px 12px",
                border: "none",
                backgroundColor:
                  value === opt.value ? "var(--bg-selected)" : "transparent",
                color:
                  value === opt.value
                    ? "var(--brand-primary)"
                    : "var(--text-primary)",
                fontSize: "13px",
                fontWeight: value === opt.value ? 500 : 400,
                cursor: "pointer",
                fontFamily: "inherit",
              }}
              onMouseEnter={(e) => {
                if (value !== opt.value)
                  e.currentTarget.style.backgroundColor = "var(--bg-hover)";
              }}
              onMouseLeave={(e) => {
                if (value !== opt.value)
                  e.currentTarget.style.backgroundColor = "transparent";
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const STATUS_OPTIONS = [
  { value: "all", label: "All Status" },
  { value: "error", label: "Error" },
  { value: "needs_reauth", label: "Needs Reconnect" },
  { value: "connected", label: "Connected" },
  { value: "syncing", label: "Syncing" },
  { value: "not_connected", label: "Not Connected" },
];

const TYPE_OPTIONS = [
  { value: "all", label: "All Types" },
  { value: "revenue_source", label: "Revenue Sources" },
  { value: "ad_platform", label: "Ad Platforms" },
];

const SORT_OPTIONS = [
  { value: "status-asc", label: "Sort: Status" },
  { value: "name-asc", label: "Sort: Name (A\u2013Z)" },
  { value: "name-desc", label: "Sort: Name (Z\u2013A)" },
  { value: "lastSync-desc", label: "Sort: Last Synced (Newest)" },
  { value: "type-asc", label: "Sort: Type" },
];

function SortFilterBar({
  sort,
  filters,
  onSortChange,
  onFilterChange,
}: {
  sort: SortState;
  filters: FilterState;
  onSortChange: (s: SortState) => void;
  onFilterChange: (f: FilterState) => void;
}) {
  const sortValue = `${sort.field}-${sort.direction}`;
  const hasActiveFilter = filters.status !== "all" || filters.type !== "all";

  const handleSortChange = (val: string) => {
    const [field, direction] = val.split("-");
    onSortChange({ field, direction });
  };

  return (
    <div
      style={{
        position: "sticky",
        top: "56px",
        zIndex: 20,
        backgroundColor: "var(--bg-canvas)",
        paddingTop: "2px",
        paddingBottom: "12px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          height: "44px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
            flexWrap: "wrap",
          }}
        >
          <DropdownButton
            label="All Status"
            options={STATUS_OPTIONS}
            value={filters.status}
            onChange={(val) => onFilterChange({ ...filters, status: val })}
          />
          <DropdownButton
            label="All Types"
            options={TYPE_OPTIONS}
            value={filters.type}
            onChange={(val) => onFilterChange({ ...filters, type: val })}
          />

          {filters.status !== "all" && (
            <span
              style={{
                display: "flex",
                alignItems: "center",
                gap: "4px",
                padding: "0 8px 0 10px",
                height: "28px",
                backgroundColor: "var(--brand-primary-light)",
                color: "var(--brand-primary)",
                borderRadius: "var(--radius-full)",
                fontSize: "12px",
                fontWeight: 500,
              }}
            >
              {STATUS_OPTIONS.find((o) => o.value === filters.status)?.label}
              <button
                onClick={() =>
                  onFilterChange({ ...filters, status: "all" })
                }
                aria-label={`Remove filter: Status equals ${filters.status}`}
                style={{
                  border: "none",
                  background: "none",
                  padding: "0",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  color: "var(--brand-primary)",
                }}
              >
                <X size={12} />
              </button>
            </span>
          )}
          {filters.type !== "all" && (
            <span
              style={{
                display: "flex",
                alignItems: "center",
                gap: "4px",
                padding: "0 8px 0 10px",
                height: "28px",
                backgroundColor: "var(--brand-primary-light)",
                color: "var(--brand-primary)",
                borderRadius: "var(--radius-full)",
                fontSize: "12px",
                fontWeight: 500,
              }}
            >
              {TYPE_OPTIONS.find((o) => o.value === filters.type)?.label}
              <button
                onClick={() =>
                  onFilterChange({ ...filters, type: "all" })
                }
                style={{
                  border: "none",
                  background: "none",
                  padding: "0",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  color: "var(--brand-primary)",
                }}
              >
                <X size={12} />
              </button>
            </span>
          )}
          {hasActiveFilter && (
            <button
              onClick={() => onFilterChange({ status: "all", type: "all" })}
              style={{
                border: "none",
                background: "none",
                padding: "0 4px",
                cursor: "pointer",
                color: "var(--text-secondary)",
                fontSize: "12px",
                fontFamily: "inherit",
                textDecoration: "underline",
              }}
            >
              Clear all
            </button>
          )}
        </div>

        <DropdownButton
          label="Sort: Status"
          options={SORT_OPTIONS}
          value={sortValue}
          onChange={handleSortChange}
        />
      </div>
    </div>
  );
}

/* ── SkeletonCard ── */

function Skel({
  width,
  height = 12,
  radius = 4,
  mb = 0,
}: {
  width: string | number;
  height?: number;
  radius?: number;
  mb?: number;
}) {
  return (
    <div
      style={{
        width,
        height,
        borderRadius: radius,
        background:
          "linear-gradient(90deg, #e8ecf0 25%, #f0f4f8 50%, #e8ecf0 75%)",
        backgroundSize: "400px 100%",
        animation: "pi-shimmer 1.4s ease-in-out infinite",
        marginBottom: mb,
      }}
    />
  );
}

function SkeletonCard() {
  return (
    <div
      style={{
        backgroundColor: "var(--bg-surface)",
        borderRadius: "var(--radius-lg)",
        border: "1px solid var(--border-subtle)",
        boxShadow: "var(--shadow-sm)",
        padding: "var(--space-5)",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        // Match PlatformCard height so the grid doesn't jump between
        // loading and loaded states.
        minHeight: "240px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: "50%",
            background:
              "linear-gradient(90deg, #e8ecf0 25%, #f0f4f8 50%, #e8ecf0 75%)",
            backgroundSize: "400px 100%",
            animation: "pi-shimmer 1.4s ease-in-out infinite",
            flexShrink: 0,
          }}
        />
        <div style={{ flex: 1 }}>
          <Skel width="55%" mb={6} />
          <Skel width="35%" height={10} />
        </div>
        <Skel width={70} height={22} radius={9999} />
      </div>
      <div>
        <Skel width="90%" mb={6} />
        <Skel width="70%" />
      </div>
      <div style={{ display: "flex", gap: "6px", marginTop: "auto" }}>
        <Skel width={80} height={30} radius={6} />
      </div>
    </div>
  );
}

/* ── CardButton ── */

function CardButton({
  variant = "secondary",
  size = "sm",
  icon: Icon,
  children,
  onClick,
  disabled,
  fullWidth,
}: {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "iconOnly";
  size?: "sm" | "icon";
  icon?: React.ComponentType<{ size?: number }>;
  children?: React.ReactNode;
  onClick?: React.MouseEventHandler;
  disabled?: boolean;
  fullWidth?: boolean;
}) {
  const [hovered, setHovered] = useState(false);

  const styles: Record<
    string,
    { bg: string; hoverBg: string; border: string; color: string }
  > = {
    primary: {
      bg: "var(--brand-primary)",
      hoverBg: "var(--brand-primary-hover)",
      border: "none",
      color: "var(--text-inverse)",
    },
    secondary: {
      bg: hovered ? "var(--bg-hover)" : "var(--bg-surface)",
      hoverBg: "var(--bg-hover)",
      border: "1px solid var(--border-default)",
      color: "var(--text-primary)",
    },
    danger: {
      bg: "var(--status-critical)",
      hoverBg: "#B91C1C",
      border: "none",
      color: "var(--text-inverse)",
    },
    ghost: {
      bg: "transparent",
      hoverBg: "var(--bg-hover)",
      border: "none",
      color: "var(--text-secondary)",
    },
    iconOnly: {
      bg: hovered ? "var(--bg-hover)" : "transparent",
      hoverBg: "var(--bg-hover)",
      border: "1px solid var(--border-default)",
      color: "var(--text-secondary)",
    },
  };

  const cfg = styles[variant] || styles.secondary;

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "5px",
        height: variant === "danger" && fullWidth ? "40px" : "30px",
        width: size === "icon" ? "30px" : fullWidth ? "100%" : "auto",
        padding:
          size === "icon"
            ? "0"
            : variant === "danger" && fullWidth
            ? "0 16px"
            : "0 11px",
        backgroundColor: hovered ? cfg.hoverBg || cfg.bg : cfg.bg,
        border: cfg.border || "none",
        borderRadius: "var(--radius-md)",
        color: cfg.color,
        fontSize: "12px",
        fontWeight: 500,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "all var(--duration-fast)",
        fontFamily: "inherit",
        whiteSpace: "nowrap",
      }}
    >
      {Icon && <Icon size={13} aria-hidden="true" />}
      {children}
    </button>
  );
}

/* ── CopyButton ── */

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <button
      onClick={handleCopy}
      aria-label={`Copy error correlation ID ${value} to clipboard`}
      aria-live="polite"
      style={{
        border: "none",
        background: "none",
        padding: "2px",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        color: copied ? "var(--status-verified)" : "var(--text-tertiary)",
        transition: "color var(--duration-fast)",
      }}
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
    </button>
  );
}

/* ── PlatformCard ── */

function getCardBorderStyle(status: string): React.CSSProperties {
  switch (status) {
    case "error":
      return {
        border: "3px solid var(--status-critical)",
      };
    case "needs_reauth":
      return { border: "2px solid var(--status-caution)" };
    case "connected":
      return { border: "2px solid var(--status-verified)" };
    case "syncing":
      return { border: "2px solid var(--status-info)" };
    case "not_connected":
      return { border: "1px dashed var(--border-default)" };
    default:
      return { border: "1px solid var(--border-subtle)" };
  }
}

function getCardTintStyle(status: string): React.CSSProperties {
  switch (status) {
    case "error":
      return { backgroundColor: "rgba(239,68,68,0.10)" }; // rose tint
    case "needs_reauth":
      return { backgroundColor: "rgba(245,158,11,0.10)" }; // amber tint
    case "connected":
      return { backgroundColor: "rgba(34,197,94,0.08)" }; // green tint
    case "syncing":
      return { backgroundColor: "rgba(59,130,246,0.08)" }; // info tint
    default:
      return { backgroundColor: "var(--bg-surface)" };
  }
}

function PlatformCard({
  integration,
  isSelected,
  onAction,
}: {
  integration: Integration;
  isSelected: boolean;
  onAction: (action: CardAction) => void;
}) {
  const {
    platformId,
    displayName,
    platformType,
    status,
    lastSyncRelative,
    nextSyncRelative,
    dataFreshness,
    error,
    connectionHealth,
    syncProgress,
  } = integration;

  const logo = getPlatformLogo(platformId, 32, status === "not_connected");
  const typeLabel =
    platformType === "ad_platform" ? "Ad Platform" : "Revenue Source";
  const borderStyle = getCardBorderStyle(status);

  const handleViewDetails = (e: React.MouseEvent) => {
    e.stopPropagation();
    onAction({ type: "view_details", platformId });
  };

  const handleFix = (e: React.MouseEvent) => {
    e.stopPropagation();
    onAction({ type: "fix", platformId });
  };

  return (
    <article
      role="article"
      aria-label={`${displayName} \u2014 ${status.replace(/_/g, " ")}`}
      style={{
        ...getCardTintStyle(status),
        borderRadius: "var(--radius-lg)",
        ...borderStyle,
        boxShadow: "var(--shadow-sm)",
        padding: "var(--space-5)",
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        cursor: "pointer",
        transition:
          "box-shadow var(--duration-fast), transform var(--duration-fast)",
        outline: isSelected ? "2px solid var(--brand-primary)" : "none",
        outlineOffset: "2px",
        // Taller tile aspect ratio to shift the visual feel from
        // "wide" to "slightly vertical" rectangle.
        minHeight: "240px",
      }}
      onClick={handleViewDetails}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = "var(--shadow-md)";
        e.currentTarget.style.transform = "translateY(-1px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = "var(--shadow-sm)";
        e.currentTarget.style.transform = "translateY(0)";
      }}
    >
      {/* Header: Logo + Name + Status */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: "10px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            flex: 1,
            minWidth: 0,
          }}
        >
          <div
            style={{
              width: "56px",
              height: "56px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              opacity: status === "not_connected" ? 0.5 : 1,
            }}
          >
            {logo}
          </div>
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: "14px",
                fontWeight: 600,
                color: "var(--text-primary)",
                lineHeight: 1.3,
                whiteSpace: "normal",
                overflow: "visible",
                textOverflow: "clip",
              }}
            >
              {displayName}
            </div>
            <div
              style={{
                fontSize: "11px",
                color: "var(--text-tertiary)",
                marginTop: "2px",
                fontWeight: 500,
              }}
            >
              {typeLabel}
            </div>
          </div>
        </div>
        <StatusBadge status={status} />
      </div>

      {/* Content region */}
      <div style={{ flex: 1 }}>
        {status === "error" && error && (
          <div>
            <p
              style={{
                fontSize: "12px",
                color: "var(--text-primary)",
                margin: "0 0 8px",
                lineHeight: 1.4,
              }}
            >
              {error.errorMessage.length > 80
                ? error.errorMessage.slice(0, 80) + "\u2026"
                : error.errorMessage}
            </p>
          </div>
        )}

        {status === "needs_reauth" && error && (
          <div>
            <p
              style={{
                fontSize: "11px",
                color: "var(--text-secondary)",
                margin: "0",
                lineHeight: 1.4,
              }}
            >
              {error.errorMessage.length > 90
                ? error.errorMessage.slice(0, 90) + "\u2026"
                : error.errorMessage}
            </p>
          </div>
        )}

        {status === "connected" && connectionHealth && (
          <div>
            {dataFreshness === "aging" && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  fontSize: "11px",
                  color: "var(--status-caution)",
                  marginBottom: "4px",
                }}
              >
                <AlertCircle size={11} />
                <span>Sync aging</span>
              </div>
            )}
            {connectionHealth.syncSuccessRateFormatted && (
              <div
                style={{ fontSize: "12px", color: "var(--text-secondary)" }}
              >
                Match rate:{" "}
                <strong style={{ color: "var(--text-primary)" }}>
                  {connectionHealth.syncSuccessRateFormatted}
                </strong>
              </div>
            )}
            {!connectionHealth.syncSuccessRateFormatted && (
              <div
                style={{
                  fontSize: "11px",
                  color: "var(--text-tertiary)",
                  fontStyle: "italic",
                }}
              >
                No match rate (ad platform)
              </div>
            )}
          </div>
        )}

        {status === "syncing" && syncProgress && (
          <div>
            <div
              style={{
                height: "4px",
                backgroundColor: "var(--bg-inset)",
                borderRadius: "var(--radius-full)",
                overflow: "hidden",
                marginBottom: "6px",
              }}
            >
              <div
                role="progressbar"
                aria-valuenow={syncProgress.percent}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Syncing ${displayName} data`}
                style={{
                  height: "100%",
                  width: `${syncProgress.percent}%`,
                  backgroundColor: "var(--brand-primary)",
                  borderRadius: "var(--radius-full)",
                  transition: "width 600ms cubic-bezier(0.4,0,0.2,1)",
                }}
              />
            </div>
            <div
              style={{ fontSize: "11px", color: "var(--text-secondary)" }}
            >
              {syncProgress.currentOperation}
            </div>
          </div>
        )}

        {status === "not_connected" && (
          <div
            style={{ fontSize: "12px", color: "var(--text-tertiary)" }}
          >
            Connect to start tracking data
          </div>
        )}
      </div>

      {/* Sync metadata — uniform template */}
      {(status === "connected" ||
        status === "syncing" ||
        status === "needs_reauth") &&
        lastSyncRelative && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              marginTop: "10px",
            }}
          >
            <span
              aria-hidden="true"
              style={{
                fontSize: "11px",
                color: "var(--text-tertiary)",
              }}
            >
              ↻
            </span>
            <span
              style={{
                fontSize: "11px",
                color: "var(--text-tertiary)",
                fontFamily: '"JetBrains Mono", monospace',
              }}
            >
              Last sync {lastSyncRelative}
            </span>
            {nextSyncRelative && (
              <>
                <span
                  style={{
                    width: "1px",
                    height: "10px",
                    backgroundColor: "var(--border-default)",
                    alignSelf: "center",
                  }}
                />
                <span
                  style={{
                    fontSize: "11px",
                    color: "var(--text-tertiary)",
                    fontFamily: '"JetBrains Mono", monospace',
                  }}
                >
                  {nextSyncRelative}
                </span>
              </>
            )}
          </div>
        )}

      {/* Action Footer */}
      <div
        style={{
          display: "flex",
          gap: "6px",
          alignItems: "center",
          marginTop: "auto",
        }}
      >
        {status === "not_connected" && (
          <CardButton
            variant="primary"
            icon={Plug}
            fullWidth
            onClick={(e) => {
              e.stopPropagation();
              onAction({ type: "connect", platformId });
            }}
          >
            Connect
          </CardButton>
        )}

        {status === "connected" && (
          <>
            <CardButton
              variant="secondary"
              icon={RefreshCw}
              onClick={(e) => {
                e.stopPropagation();
                onAction({ type: "resync", platformId });
              }}
            >
              Re-sync
            </CardButton>
            <CardButton
              variant="iconOnly"
              size="icon"
              icon={Settings}
              onClick={(e) => e.stopPropagation()}
            />
          </>
        )}

        {status === "needs_reauth" && (
          <>
            <CardButton
              variant="secondary"
              onClick={(e) => {
                e.stopPropagation();
                onAction({ type: "reconnect", platformId });
              }}
            >
              Reconnect
            </CardButton>
            <CardButton
              variant="iconOnly"
              size="icon"
              icon={RefreshCw}
              onClick={(e) => e.stopPropagation()}
            />
            <CardButton
              variant="iconOnly"
              size="icon"
              icon={Settings}
              onClick={(e) => e.stopPropagation()}
            />
          </>
        )}

        {status === "error" && (
          <CardButton
            variant="danger"
            fullWidth
            onClick={handleFix}
          >
            <span
              aria-hidden="true"
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 18,
                height: 18,
                marginRight: 4,
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path
                  fill="#FFFFFF"
                  d="M21.774 6.146a.75.75 0 0 0-1.205-.693l-2.634 1.98a2.25 2.25 0 0 1-2.879-.176l-.313-.313a2.25 2.25 0 0 1-.176-2.879l1.98-2.634a.75.75 0 0 0-.693-1.205 7.5 7.5 0 0 0-6.606 9.997L2.47 17a2.652 2.652 0 1 0 3.75 3.75l6.777-6.777a7.5 7.5 0 0 0 8.777-7.827Zm-17.304 13.18a1.152 1.152 0 1 1-1.63-1.63 1.152 1.152 0 0 1 1.63 1.63Z"
                />
              </svg>
            </span>
            Fix Connection
          </CardButton>
        )}

        {status === "syncing" && (
          <CardButton variant="secondary" disabled fullWidth>
            Syncing...
          </CardButton>
        )}
      </div>
    </article>
  );
}

/* ── PlatformGrid ── */

const STATUS_ORDER = [
  "error",
  "needs_reauth",
  "syncing",
  "connected",
  "not_connected",
];

function sortIntegrations(
  integrations: Integration[],
  sort: SortState
): Integration[] {
  const sorted = [...integrations];
  if (sort.field === "status") {
    sorted.sort((a, b) => {
      const ai = STATUS_ORDER.indexOf(a.status);
      const bi = STATUS_ORDER.indexOf(b.status);
      if (ai !== bi) return ai - bi;
      return a.displayName.localeCompare(b.displayName);
    });
  } else if (sort.field === "name") {
    sorted.sort((a, b) => {
      const cmp = a.displayName.localeCompare(b.displayName);
      return sort.direction === "asc" ? cmp : -cmp;
    });
  } else if (sort.field === "type") {
    sorted.sort((a, b) => a.platformType.localeCompare(b.platformType));
  }
  return sorted;
}

function filterIntegrations(
  integrations: Integration[],
  filters: FilterState
): Integration[] {
  return integrations.filter((i) => {
    const statusMatch =
      filters.status === "all" || i.status === filters.status;
    const typeMatch =
      filters.type === "all" || i.platformType === filters.type;
    return statusMatch && typeMatch;
  });
}

function PlatformGrid({
  integrations,
  sort,
  filters,
  isLoading,
  openDrawerPlatformId,
  onCardAction,
}: {
  integrations: Integration[];
  sort: SortState;
  filters: FilterState;
  isLoading: boolean;
  openDrawerPlatformId: string | null;
  onCardAction: (action: CardAction) => void;
}) {
  const filtered = filterIntegrations(integrations, filters);
  const sorted = sortIntegrations(filtered, sort);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(4, minmax(300px, 1fr))",
        gap: "20px",
      }}
    >
      {isLoading
        ? Array(8)
            .fill(0)
            .map((_, i) => <SkeletonCard key={i} />)
        : sorted.map((integration) => (
            <PlatformCard
              key={integration.platformId}
              integration={integration}
              isSelected={
                openDrawerPlatformId === integration.platformId
              }
              onAction={onCardAction}
            />
          ))}

      {!isLoading && sorted.length === 0 && (
        <div
          style={{
            gridColumn: "1 / -1",
            textAlign: "center",
            padding: "60px 24px",
            color: "var(--text-tertiary)",
          }}
        >
          <div style={{ fontSize: "32px", marginBottom: "12px" }}>
            {"\uD83D\uDD0D"}
          </div>
          <div
            style={{
              fontSize: "16px",
              fontWeight: 600,
              color: "var(--text-primary)",
              marginBottom: "6px",
            }}
          >
            No integrations match your filters
          </div>
          <div style={{ fontSize: "13px" }}>
            Try adjusting your status or type filters to see more platforms.
          </div>
        </div>
      )}
    </div>
  );
}

/* ── ErrorDetailsDrawer ── */

const ERROR_TYPE_LABELS: Record<string, string> = {
  oauth_token_expired: "Authorization Expired",
  oauth_permission_insufficient: "Insufficient Permissions",
  webhook_endpoint_unreachable: "Webhook Unreachable",
  api_key_invalid: "Invalid API Key",
  rate_limit_exceeded: "Rate Limit Exceeded",
  account_access_revoked: "Account Access Revoked",
  ssl_certificate_invalid: "SSL Certificate Error",
  network_timeout: "Connection Timeout",
  schema_mismatch: "Data Format Mismatch",
  platform_api_error: "Platform API Error",
  unknown: "Unknown Error",
};

function CopyIDButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const handle = () => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <button
      onClick={handle}
      aria-label="Copy error correlation ID to clipboard"
      aria-live="polite"
      style={{
        border: "none",
        background: "none",
        padding: "4px",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        color: copied ? "var(--status-verified)" : "var(--text-tertiary)",
        borderRadius: "var(--radius-sm)",
        transition: "color var(--duration-fast)",
      }}
    >
      {copied ? <Check size={15} /> : <Copy size={15} />}
    </button>
  );
}

function DrawerSection({
  label,
  children,
  noBorder,
}: {
  label?: string;
  children: React.ReactNode;
  noBorder?: boolean;
}) {
  return (
    <div
      style={{
        padding: "20px 24px",
        borderTop: noBorder ? "none" : "1px solid var(--border-subtle)",
      }}
    >
      {label && (
        <div
          style={{
            fontSize: "12px",
            fontWeight: 700,
            letterSpacing: "0.06em",
            textTransform: "uppercase" as const,
            color: "var(--text-primary)",
            marginBottom: "12px",
          }}
        >
          {label}
        </div>
      )}
      {children}
    </div>
  );
}

function ErrorDetailsDrawer({
  isOpen,
  integration,
  onClose,
  onReconnect,
  onResync,
}: {
  isOpen: boolean;
  integration: Integration | null;
  onClose: () => void;
  onReconnect: (id: string) => void;
  onResync: (id: string) => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const prevFocusRef = useRef<Element | null>(null);

  useEffect(() => {
    if (isOpen) {
      prevFocusRef.current = document.activeElement;
      setTimeout(() => closeRef.current?.focus(), 50);
    } else {
      (prevFocusRef.current as HTMLElement)?.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  if (!integration) return null;

  const {
    platformId,
    displayName,
    status,
    error,
    connectionHealth,
    authMetadata,
    lastSyncRelative,
  } = integration;
  const logo = getPlatformLogo(platformId, 31);

  const statusHeadlines: Record<string, string> = {
    error: "Connection Error \u2014 Action Required",
    needs_reauth: "Authorization Expired \u2014 Reconnect to Resume",
    connected: "Connected and Syncing Normally",
  };

  const isPrimaryReconnect =
    error &&
    [
      "oauth_token_expired",
      "oauth_permission_insufficient",
      "account_access_revoked",
      "webhook_endpoint_unreachable",
      "api_key_invalid",
      "ssl_certificate_invalid",
    ].includes(error.errorType);

  const primaryLabel =
    status === "needs_reauth" || (status === "error" && isPrimaryReconnect)
      ? `Reconnect ${displayName}`
      : `Re-sync ${displayName}`;

  const primaryAction =
    status === "needs_reauth" || (status === "error" && isPrimaryReconnect)
      ? () => onReconnect(platformId)
      : () => onResync(platformId);

  const failedAt = error?.occurredAt
    ? new Date(error.occurredAt).toLocaleDateString("en-US", {
        month: "long",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          backgroundColor: "var(--bg-overlay)",
          zIndex: 45,
          opacity: isOpen ? 1 : 0,
          pointerEvents: isOpen ? "all" : "none",
          transition: "opacity var(--duration-slow) cubic-bezier(0.4,0,0.2,1)",
        }}
        aria-hidden="true"
      />

      {/* Drawer */}
      <aside
        role="complementary"
        aria-label={`${displayName} integration details`}
        aria-modal="true"
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: "400px",
          backgroundColor: "var(--bg-surface)",
          borderLeft: "1px solid var(--border-subtle)",
          boxShadow: "var(--shadow-lg)",
          zIndex: 50,
          display: "flex",
          flexDirection: "column",
          transform: isOpen ? "translateX(0)" : "translateX(400px)",
          transition:
            "transform var(--duration-slow) cubic-bezier(0.4,0,0.2,1)",
          overflowY: "auto",
        }}
      >
        {/* Header */}
        <div
          style={{
            position: "sticky",
            top: 0,
            zIndex: 5,
            backgroundColor: "var(--bg-surface)",
            borderBottom: "1px solid var(--border-subtle)",
            padding: "14px 24px 12px",
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
          }}
        >
          <div
            style={{ display: "flex", alignItems: "center", gap: "12px" }}
          >
            <div
              style={{
                width: "42px",
                height: "42px",
                borderRadius: "var(--radius-full)",
                backgroundColor: "var(--bg-inset)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                border:
                  platformId === "meta"
                    ? "2px solid rgba(20,184,166,0.35)"
                    : "1px solid rgba(148,163,184,0.35)",
              }}
            >
              {logo}
            </div>
            <div>
              <div
                style={{
                  fontSize: "20px",
                  fontWeight: 600,
                  color: "var(--text-primary)",
                  lineHeight: 1.2,
                  fontFamily: "'DM Sans', var(--font-sans)",
                }}
              >
                {displayName}
              </div>
            </div>
          </div>
          <button
            ref={closeRef}
            onClick={onClose}
            aria-label={`Close ${displayName} integration details`}
            style={{
              border: "none",
              background: "none",
              width: "32px",
              height: "32px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "var(--radius-md)",
              cursor: "pointer",
              color: "var(--text-secondary)",
              transition: "background-color var(--duration-fast)",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.backgroundColor = "var(--bg-hover)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.backgroundColor = "transparent")
            }
          >
            <X size={18} />
          </button>
        </div>

        {/* Status row */}
        {failedAt && (
          <div
            style={{
              padding: "10px 24px 14px",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              borderBottom: "1px solid var(--border-subtle)",
              backgroundColor: "var(--bg-surface)",
            }}
          >
            <span
              style={{
                fontSize: "12px",
                color: "var(--text-secondary)",
                fontFamily: "var(--font-sans)",
              }}
            >
              {status === "error" ? "\u2297 Error" : status === "needs_reauth" ? "\u26A0 Authorization" : "\u2713 Connected"}
              {" \u2022 "}Failed {failedAt}
            </span>
          </div>
        )}

        {/* Section 1: Status headline */}
        <DrawerSection noBorder={!failedAt}>
          <div
            style={{
              fontSize: "15px",
              fontWeight: 600,
              color:
                status === "error"
                  ? "var(--status-critical)"
                  : status === "needs_reauth"
                    ? "var(--status-caution)"
                    : "var(--status-verified)",
              marginBottom: "12px",
            }}
          >
            {statusHeadlines[status] || statusHeadlines.connected}
          </div>

          {authMetadata && (
            <div
              style={{
                backgroundColor: "var(--bg-inset)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-subtle)",
                padding: "10px 12px",
              }}
            >
              <div
                style={{
                  fontSize: "12px",
                  color: "var(--text-secondary)",
                  lineHeight: 1.8,
                }}
              >
                <div>
                  Connected by:{" "}
                  <strong>{authMetadata.connectedByUserEmail}</strong>
                </div>
                <div>
                  Auth method:{" "}
                  <strong>
                    {authMetadata.authMethod === "oauth2"
                      ? "OAuth 2.0"
                      : authMetadata.authMethod === "api_key"
                        ? "API Key"
                        : "Webhook"}
                  </strong>
                </div>
              </div>
            </div>
          )}
        </DrawerSection>

        {/* Section 2: Error Details */}
        {(status === "error" || status === "needs_reauth") && error && (
          <DrawerSection label="Error Details">
            <div
              style={{
                fontSize: "11px",
                fontWeight: 500,
                textTransform: "uppercase" as const,
                letterSpacing: "0.06em",
                color: "var(--text-primary)",
                marginBottom: "8px",
              }}
            >
              WHAT WENT WRONG
            </div>
            <p
              style={{
                fontSize: "13px",
                color: "var(--text-primary)",
                margin: "0 0 14px",
                lineHeight: 1.5,
              }}
            >
              {error.errorMessage}
            </p>

            <div
              style={{
                fontSize: "11px",
                fontWeight: 500,
                textTransform: "uppercase" as const,
                letterSpacing: "0.06em",
                color: "var(--text-tertiary)",
                marginBottom: "6px",
              }}
            >
              SUPPORT ID
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                backgroundColor: "var(--bg-inset)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "9px 12px",
                marginBottom: "12px",
              }}
            >
              <span
                style={{
                  fontFamily: '"JetBrains Mono", monospace',
                  fontSize: "13px",
                  color: "var(--text-primary)",
                  userSelect: "all",
                  letterSpacing: "0.02em",
                }}
              >
                {error.correlationId}
              </span>
              <CopyIDButton value={error.correlationId} />
            </div>

            {error.occurrenceCount > 1 && (
              <div
                style={{
                  fontSize: "12px",
                  color: "var(--text-primary)",
                  marginBottom: "4px",
                }}
              >
                Recurred {error.occurrenceCount} times in the last 24 hours
              </div>
            )}
          </DrawerSection>
        )}

        {/* Section 3: Remediation Steps */}
        {error && error.remediationSteps && error.remediationSteps.length > 0 && (
          <DrawerSection label="HOW TO FIX THIS">
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "16px",
              }}
            >
              {error.remediationSteps.map((step) => (
                <div
                  key={step.stepNumber}
                  style={{
                    display: "flex",
                    gap: "12px",
                    alignItems: "flex-start",
                  }}
                >
                  <div
                    style={{
                      width: "24px",
                      height: "24px",
                      borderRadius: "var(--radius-full)",
                      backgroundColor: "rgba(37, 99, 235, 0.14)",
                      border: "1px solid rgba(37, 99, 235, 0.22)",
                      color: "var(--brand-primary)",
                      fontSize: "11px",
                      fontWeight: 700,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                      marginTop: "1px",
                    }}
                  >
                    {step.stepNumber}
                  </div>
                  <div style={{ flex: 1 }}>
                    <p
                      style={{
                        fontSize: "13px",
                        color: "var(--text-primary)",
                        margin: 0,
                        lineHeight: 1.5,
                      }}
                    >
                      {step.instruction}
                    </p>
                    {step.actionType === "navigate_third_party" &&
                      step.actionUrl && (
                        <a
                          href={step.actionUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                            marginTop: "6px",
                            fontSize: "12px",
                            color: "var(--brand-primary)",
                            textDecoration: "none",
                          }}
                          onMouseEnter={(e) =>
                            (e.currentTarget.style.textDecoration =
                              "underline")
                          }
                          onMouseLeave={(e) =>
                            (e.currentTarget.style.textDecoration = "none")
                          }
                        >
                          {step.actionLabel || "Open external link"}
                          <ExternalLink size={11} />
                        </a>
                      )}
                  </div>
                </div>
              ))}
            </div>

            <a
              href="#"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                marginTop: "16px",
                fontSize: "12px",
                color: "var(--brand-primary)",
                textDecoration: "none",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.textDecoration = "underline")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.textDecoration = "none")
              }
            >
              <ExternalLink size={11} />
              View {displayName} integration documentation
            </a>
          </DrawerSection>
        )}

        {/* Section 4: Sync Health */}
        {connectionHealth && (
          <DrawerSection label="SYNC HEALTH (LAST 7 DAYS)">
            {connectionHealth.syncSuccessRateFormatted && (
              <div style={{ marginBottom: "10px" }}>
                <div
                  style={{
                    fontSize: "22px",
                    fontWeight: 700,
                    fontFamily: '"JetBrains Mono", monospace',
                    color:
                      parseFloat(
                        connectionHealth.syncSuccessRateFormatted
                      ) >= 95
                        ? "var(--status-verified)"
                        : parseFloat(
                              connectionHealth.syncSuccessRateFormatted
                            ) >= 75
                          ? "var(--status-caution)"
                          : "var(--status-critical)",
                  }}
                >
                  {connectionHealth.syncSuccessRateFormatted}
                </div>
                <div
                  style={{
                    fontSize: "11px",
                    textTransform: "uppercase" as const,
                    letterSpacing: "0.06em",
                    color: "var(--text-tertiary)",
                  }}
                >
                  Sync Success Rate
                </div>
              </div>
            )}
            <div
              style={{
                fontSize: "12px",
                color: "var(--text-secondary)",
                lineHeight: 1.8,
              }}
            >
              {connectionHealth.failedSyncsLast7d > 0 && (
                <div style={{ color: "var(--text-primary)" }}>
                  Failed syncs: {connectionHealth.failedSyncsLast7d}
                </div>
              )}
              <div>
                Total syncs (7d): {connectionHealth.totalSyncsLast7d}
              </div>
              {lastSyncRelative && <div>Last sync: {lastSyncRelative}</div>}
            </div>
          </DrawerSection>
        )}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Footer */}
        <div
          style={{
            position: "sticky",
            bottom: 0,
            backgroundColor: "var(--bg-surface)",
            borderTop: "1px solid var(--border-subtle)",
            padding: "16px 24px",
            display: "flex",
            gap: "8px",
            alignItems: "center",
          }}
        >
          <button
            onClick={primaryAction}
            style={{
              flex: 1,
              height: "38px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
              backgroundColor: "var(--brand-primary)",
              border: "none",
              borderRadius: "var(--radius-md)",
              color: "var(--text-inverse)",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "inherit",
              transition: "background-color var(--duration-fast)",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.backgroundColor =
                "var(--brand-primary-hover)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.backgroundColor =
                "var(--brand-primary)")
            }
          >
            <RefreshCw size={14} />
            {primaryLabel}
          </button>
          <a
            href={`mailto:support@skeldir.com?subject=Integration%20Error&body=Error%20ID%3A%20${error?.correlationId || ""}%0A%0APlatform%3A%20${displayName}`}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "5px",
              height: "38px",
              padding: "0 14px",
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-md)",
              color: "var(--text-primary)",
              fontSize: "12px",
              fontWeight: 500,
              textDecoration: "none",
              whiteSpace: "nowrap",
              transition: "all var(--duration-fast)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = "var(--bg-hover)";
              e.currentTarget.style.borderColor = "var(--border-strong)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = "var(--bg-surface)";
              e.currentTarget.style.borderColor = "var(--border-default)";
            }}
          >
            <MessageSquare size={13} />
            Contact Support
          </a>
        </div>
      </aside>
    </>
  );
}

/* ══════════════════════════════════════════════════════════════
   Main Renderer — exported as AgentAPlatformIntegrations
   ══════════════════════════════════════════════════════════════ */

export function AgentAPlatformIntegrations(
  _props: PlatformIntegrationsRendererProps
) {
  const [integrations, setIntegrations] = useState<Integration[]>(
    MOCK_INTEGRATIONS
  );
  const [isLoading, setIsLoading] = useState(true);
  const [sort, setSort] = useState<SortState>({
    field: "status",
    direction: "asc",
  });
  const [filters, setFilters] = useState<FilterState>({
    status: "all",
    type: "all",
  });
  const [openDrawerPlatformId, setOpenDrawerPlatformId] = useState<
    string | null
  >(null);
  const [isResyncing, setIsResyncing] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

  const openDrawerIntegration =
    integrations.find((i) => i.platformId === openDrawerPlatformId) || null;

  const handleResyncAll = useCallback(() => {
    setIsResyncing(true);
    setTimeout(() => setIsResyncing(false), 3000);
  }, []);

  const handleCardAction = useCallback((action: CardAction) => {
    const { type, platformId } = action;
    if (type === "view_details" || type === "fix") {
      setOpenDrawerPlatformId(platformId);
    } else if (type === "resync") {
      setIntegrations((prev) =>
        prev.map((i) =>
          i.platformId === platformId
            ? {
                ...i,
                status: "syncing" as IntegrationStatus,
                syncProgress: {
                  percent: 0,
                  currentOperation: "Starting sync...",
                  estimatedSecondsRemaining: 30,
                },
              }
            : i
        )
      );
      let progress = 0;
      const interval = setInterval(() => {
        progress += 20;
        setIntegrations((prev) =>
          prev.map((i) =>
            i.platformId === platformId && i.status === "syncing"
              ? {
                  ...i,
                  syncProgress: {
                    percent: progress,
                    currentOperation:
                      progress < 80
                        ? "Pulling campaign data..."
                        : "Finalizing...",
                    estimatedSecondsRemaining: Math.max(
                      0,
                      30 - progress / 4
                    ),
                  },
                }
              : i
          )
        );
        if (progress >= 100) {
          clearInterval(interval);
          setIntegrations((prev) =>
            prev.map((i) =>
              i.platformId === platformId
                ? {
                    ...i,
                    status: "connected" as IntegrationStatus,
                    syncProgress: null,
                    lastSyncRelative: "just now",
                    dataFreshness: "fresh",
                  }
                : i
            )
          );
        }
      }, 600);
    } else if (type === "connect" || type === "reconnect") {
      setIntegrations((prev) =>
        prev.map((i) =>
          i.platformId === platformId
            ? {
                ...i,
                status: "connected" as IntegrationStatus,
                error: null,
                lastSyncRelative: "just now",
                dataFreshness: "fresh",
              }
            : i
        )
      );
    }
  }, []);

  const healthCounts = {
    connected: integrations.filter((i) => i.status === "connected").length,
    needsAttention: integrations.filter((i) => i.status === "needs_reauth")
      .length,
    errors: integrations.filter((i) => i.status === "error").length,
    notConnected: integrations.filter((i) => i.status === "not_connected")
      .length,
  };

  return (
    <div
      className="pi-root"
      style={{
        backgroundColor: "var(--bg-canvas)",
        minHeight: "100vh",
        fontFamily:
          '"DM Sans", -apple-system, BlinkMacSystemFont, sans-serif',
      }}
    >
      <IntegrationsTopBar
        isResyncing={isResyncing}
        onResyncAll={handleResyncAll}
      />

      <div
        style={{
          maxWidth: "1440px",
          margin: "0 auto",
          padding: "0 var(--space-8) var(--space-8)",
        }}
      >
        <ConnectionHealthBand
          {...healthCounts}
          isLoading={isLoading}
        />

        <SortFilterBar
          sort={sort}
          filters={filters}
          onSortChange={setSort}
          onFilterChange={setFilters}
        />

        <PlatformGrid
          integrations={integrations}
          sort={sort}
          filters={filters}
          isLoading={isLoading}
          openDrawerPlatformId={openDrawerPlatformId}
          onCardAction={handleCardAction}
        />
      </div>

      <ErrorDetailsDrawer
        isOpen={!!openDrawerPlatformId}
        integration={openDrawerIntegration}
        onClose={() => setOpenDrawerPlatformId(null)}
        onReconnect={(id) =>
          handleCardAction({ type: "reconnect", platformId: id })
        }
        onResync={(id) =>
          handleCardAction({ type: "resync", platformId: id })
        }
      />
    </div>
  );
}
