/**
 * Shared Types Contract — All 5 Design Agents implement these identically
 *
 * Source: Implementation Spec (Command Center canonical structure)
 * Source: Master Skill (state machine, confidence model)
 *
 * DO NOT MODIFY — this is the invariant contract.
 */

// ---------------------------------------------------------------------------
// Dashboard Data
// ---------------------------------------------------------------------------

export interface DashboardData {
  totalRevenue: {
    value: number;
    confidence: ConfidenceTier;
    confidenceInterval: number; // ±X%
    trend: TrendDirection;
  };
  activeChannels: {
    count: number;
    total: number;
    healthStatus: 'healthy' | 'degraded' | 'critical';
  };
  modelConfidence: {
    score: number; // 0-100
    daysOfEvidence: number;
    maxDays: 14;
    status: 'building' | 'stable' | 'converged';
  };
  lastUpdated: string; // ISO 8601
  priorityActions: PriorityAction[];
}

// ---------------------------------------------------------------------------
// Priority Actions
// ---------------------------------------------------------------------------

export interface PriorityAction {
  id: string;
  type: 'discrepancy' | 'channel_issue' | 'model_alert' | 'data_quality';
  severity: 'critical' | 'warning' | 'info';
  title: string;
  description: string;
  affectedChannel?: string;
  estimatedImpact: string; // Always quantified: "$X,XXX" or "X%"
  actionUrl: string;
}

// ---------------------------------------------------------------------------
// Channel Performance
// ---------------------------------------------------------------------------

export type ChannelPlatform =
  | 'meta'
  | 'google'
  | 'tiktok'
  | 'linkedin'
  | 'twitter'
  | 'pinterest'
  | 'snapchat';

export interface ChannelPerformance {
  channelId: string;
  channelName: string;
  platform: ChannelPlatform;
  spend: number;
  revenue: number;
  roas: number;
  confidence: number; // 0-100
  trend: TrendDirection;
}

// ---------------------------------------------------------------------------
// State Machine (MANDATORY for all data-bearing components)
// NO component may exist in an undefined visual state.
// ---------------------------------------------------------------------------

export type EmptyVariant =
  | 'no-data-yet'       // Data pipeline not connected
  | 'building-model'    // Connected, insufficient history (<14 days)
  | 'no-results-filter' // Connected, model exists, filter returns nothing
  | 'feature-locked';   // Tier restriction

export interface SkeldirError {
  message: string;        // Human-readable, actionable
  correlationId: string;  // For support traces
  retryable: boolean;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export type CommandCenterState =
  | { status: 'loading' }
  | { status: 'empty'; variant: EmptyVariant }
  | { status: 'error'; error: SkeldirError }
  | { status: 'ready'; data: DashboardData; channels: ChannelPerformance[] };

// ---------------------------------------------------------------------------
// Semantic Types (Master Skill — CLOSED vocabulary)
// ---------------------------------------------------------------------------

export type ConfidenceTier = 'high' | 'medium' | 'low';
export type TrendDirection = 'up' | 'down' | 'stable';

/**
 * Confidence display copy — CLOSED vocabulary, no synonyms.
 * Source: Master Skill copy-system/copy-templates.ts
 */
export function formatConfidenceLabel(tier: ConfidenceTier, margin: number): string {
  switch (tier) {
    case 'high':
      return `High Confidence · ±${margin}%`;
    case 'medium':
      return `Medium Confidence · ±${margin}%`;
    case 'low':
      return `Low Confidence · ±${margin}% — more data needed`;
  }
}

/**
 * Channel color lookup (deterministic, NEVER reorder)
 * Source: Master Skill tokens/design-tokens.ts
 */
export const CHANNEL_COLORS: Record<string, string> = {
  meta: 'var(--channel-meta)',
  google: 'var(--channel-google)',
  tiktok: 'var(--channel-tiktok)',
  linkedin: 'var(--channel-linkedin)',
  twitter: 'var(--channel-twitter)',
  pinterest: 'var(--channel-pinterest)',
  snapchat: 'var(--channel-other)',
};

// ---------------------------------------------------------------------------
// Deterministic Fixtures (for Storybook + testing)
// ---------------------------------------------------------------------------

export const FIXTURES = {
  ready: {
    status: 'ready' as const,
    data: {
      totalRevenue: {
        value: 142837,
        confidence: 'high' as ConfidenceTier,
        confidenceInterval: 3.2,
        trend: 'up' as TrendDirection,
      },
      activeChannels: {
        count: 5,
        total: 7,
        healthStatus: 'healthy' as const,
      },
      modelConfidence: {
        score: 87,
        daysOfEvidence: 12,
        maxDays: 14 as const,
        status: 'stable' as const,
      },
      lastUpdated: '2026-02-14T10:30:00Z',
      priorityActions: [
        {
          id: 'pa-001',
          type: 'discrepancy' as const,
          severity: 'critical' as const,
          title: 'Meta revenue gap exceeds 15%',
          description: 'Platform-reported revenue diverges from Stripe-verified by $4,230 (18.2%)',
          affectedChannel: 'Meta',
          estimatedImpact: '$4,230',
          actionUrl: '/channels/meta',
        },
        {
          id: 'pa-002',
          type: 'data_quality' as const,
          severity: 'warning' as const,
          title: 'TikTok sync delayed 6 hours',
          description: 'Last successful data pull was at 04:30 UTC. Current lag exceeds 4-hour threshold.',
          affectedChannel: 'TikTok',
          estimatedImpact: '6h data gap',
          actionUrl: '/data',
        },
        {
          id: 'pa-003',
          type: 'model_alert' as const,
          severity: 'info' as const,
          title: 'Google attribution model reconverging',
          description: 'Recent campaign changes triggered model recalculation. Updated estimates in ~2 hours.',
          affectedChannel: 'Google',
          estimatedImpact: '±5% variance window',
          actionUrl: '/channels/google',
        },
      ],
    },
    channels: [
      { channelId: 'ch-meta', channelName: 'Meta Ads', platform: 'meta' as const, spend: 23500, revenue: 67200, roas: 2.86, confidence: 92, trend: 'up' as const },
      { channelId: 'ch-google', channelName: 'Google Ads', platform: 'google' as const, spend: 18700, revenue: 52100, roas: 2.79, confidence: 88, trend: 'stable' as const },
      { channelId: 'ch-tiktok', channelName: 'TikTok Ads', platform: 'tiktok' as const, spend: 8200, revenue: 15400, roas: 1.88, confidence: 64, trend: 'down' as const },
      { channelId: 'ch-linkedin', channelName: 'LinkedIn Ads', platform: 'linkedin' as const, spend: 4100, revenue: 5200, roas: 1.27, confidence: 71, trend: 'stable' as const },
      { channelId: 'ch-pinterest', channelName: 'Pinterest Ads', platform: 'pinterest' as const, spend: 2800, revenue: 2937, roas: 1.05, confidence: 55, trend: 'down' as const },
    ],
  },

  loading: {
    status: 'loading' as const,
  },

  empty: {
    status: 'empty' as const,
    variant: 'no-data-yet' as EmptyVariant,
  },

  emptyBuildingModel: {
    status: 'empty' as const,
    variant: 'building-model' as EmptyVariant,
  },

  error: {
    status: 'error' as const,
    error: {
      message: 'Dashboard data temporarily unavailable. The attribution service is being updated.',
      correlationId: 'err-cc-20260214-a7f3',
      retryable: true,
      action: {
        label: 'Retry now',
        onClick: () => console.log('[fixture] retry clicked'),
      },
    },
  },
} satisfies Record<string, CommandCenterState>;
