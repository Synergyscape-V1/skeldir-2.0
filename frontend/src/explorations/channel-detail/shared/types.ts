/**
 * SKELDIR CHANNEL DETAIL — SHARED TYPE CONTRACT
 *
 * Canonical TypeScript interfaces consumed by all 5 Design Agents.
 * Derived from: Skeldir_Frontend_Design Implementation_Spec.md Section III
 *
 * Rule: Frontend receives pre-formatted values from the API.
 * No statistical calculations happen client-side.
 */

// ─────────────────────────────────────────────────────────────────
// CONFIDENCE (closed vocabulary — no synonyms)
// ─────────────────────────────────────────────────────────────────

export type ConfidenceLevel = 'high' | 'medium' | 'low';

// ─────────────────────────────────────────────────────────────────
// CHANNEL DETAIL DATA — the canonical shape from the API
// ─────────────────────────────────────────────────────────────────

export interface ChannelDetailData {
  channel: {
    id: string;
    name: string;
    platform: string;
    platformLogo?: string;
    status: 'active' | 'paused' | 'disconnected';
    connectedSince: string; // ISO date
  };

  dateRange: {
    start: string; // ISO date
    end: string;   // ISO date
    label: string; // Pre-formatted: "Jan 1 – Jan 31, 2026"
  };

  performance: {
    revenue: number;
    revenueFormatted: string;       // "$42,850"
    revenueDelta: string;           // "+12.3% vs prev period"
    spend: number;
    spendFormatted: string;         // "$12,400"
    spendDelta: string;             // "+5.1% vs prev period"
    roas: number;
    roasFormatted: string;          // "3.46x"
    roasDelta: string;              // "+0.40 vs Google"
    conversions: number;
    conversionsFormatted: string;   // "1,247"
    conversionsDelta: string;       // "+8.2% vs prev period"
    cpa: number;
    cpaFormatted: string;           // "$9.94"
    cpaDelta: string;               // "-$1.20 vs prev period"
  };

  verification: {
    platformClaimed: number;
    platformClaimedFormatted: string;    // "$45,200"
    verified: number;
    verifiedFormatted: string;           // "$42,850"
    discrepancy: number;
    discrepancyPercent: number;          // 5.2
    discrepancyFormatted: string;        // "-5.2%"
    transactionCount: number;
    transactionCountFormatted: string;   // "1,247 transactions"
    revenueSource: string;               // "Stripe"
  };

  confidenceRange: {
    low: number;
    lowFormatted: string;          // "$2.80"
    high: number;
    highFormatted: string;         // "$3.80"
    point: number;
    pointFormatted: string;        // "$3.46"
    level: ConfidenceLevel;
    explanation: string;           // Pre-built from backend
    margin: number;                // ±percentage
    daysOfData: number;
    conversionsUsed: number;
  };

  trendData: Array<{
    date: string;            // ISO date
    dateFormatted: string;   // "Jan 15"
    revenue: number;
    revenueFormatted: string;
    spend: number;
    spendFormatted: string;
    roas: number;
    roasFormatted: string;
    roasRangeLow: number;
    roasRangeLowFormatted: string;
    roasRangeHigh: number;
    roasRangeHighFormatted: string;
  }>;

  modelInfo: {
    version: number;
    lastUpdated: string;         // ISO datetime
    lastUpdatedFormatted: string; // "2 hours ago"
    nextUpdate: string;          // "in 22 hours"
  };
}

// ─────────────────────────────────────────────────────────────────
// COMPONENT STATE MACHINE — all 4 states must be handled
// ─────────────────────────────────────────────────────────────────

export type ChannelDetailState =
  | { status: 'loading' }
  | { status: 'empty'; emptyVariant: 'no-data-yet' | 'building-model' | 'no-results-filter' | 'feature-locked'; currentDay?: number }
  | { status: 'error'; error: ChannelDetailError }
  | { status: 'ready'; data: ChannelDetailData };

export interface ChannelDetailError {
  title: string;
  message: string;
  correlationId: string;
  retryable: boolean;
  action?: {
    label: string;
    onClick: () => void;
  };
}

// ─────────────────────────────────────────────────────────────────
// NAV ITEMS — horizontal navigation contract
// ─────────────────────────────────────────────────────────────────

export interface NavItem {
  id: string;
  label: string;
  path: string;
  icon: string; // Lucide icon name
  badge?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { id: 'command-center', label: 'Command Center', path: '/', icon: 'LayoutDashboard' },
  { id: 'channels', label: 'Channels', path: '/channels', icon: 'Radio' },
  { id: 'data', label: 'Data', path: '/data', icon: 'Database' },
  { id: 'budget', label: 'Budget', path: '/budget', icon: 'Wallet' },
  { id: 'investigations', label: 'Investigations', path: '/investigations', icon: 'Search' },
  { id: 'settings', label: 'Settings', path: '/settings', icon: 'Settings' },
];

// ─────────────────────────────────────────────────────────────────
// CHANNEL COLOR MAP — deterministic, never reorder
// ─────────────────────────────────────────────────────────────────

export const CHANNEL_COLORS: Record<string, string> = {
  'meta': '#3D7BF5',
  'facebook': '#3D7BF5',
  'google': '#10D98C',
  'tiktok': '#F5A623',
  'email': '#B36CF5',
  'pinterest': '#F54E8B',
  'linkedin': '#36BFFA',
  'other': '#FB7C4C',
  'direct': '#FB7C4C',
};
