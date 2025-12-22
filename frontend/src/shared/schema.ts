/**
 * Shared schema types for frontend components.
 * These are stub types to support the migrated Replit codebase.
 * TODO: Replace with generated types from OpenAPI contracts when available.
 */

// ============================================================================
// Password & Authentication Types
// ============================================================================

export interface PasswordStrength {
  score: number;
  feedback: {
    suggestions: string[];
    warning?: string;
  };
  requirements: {
    minLength: boolean;
    hasUppercase: boolean;
    hasLowercase: boolean;
    hasNumbers: boolean;
    hasSpecialChars: boolean;
  };
}

// ============================================================================
// Platform & Revenue Types
// ============================================================================

export type PlatformId = 'shopify' | 'stripe' | 'paypal' | 'square' | 'google';

export interface PlatformStatus {
  platform_id: PlatformId;
  platform_name: string;
  status: 'connected' | 'disconnected' | 'error' | 'pending';
  last_sync?: string;
  revenue_total?: number;
  transaction_count?: number;
  error_message?: string;
}

export interface PlatformRevenue {
  platform_id: PlatformId;
  platform_name: string;
  revenue_cents: number;
  transaction_count: number;
  verified: boolean;
  last_updated: string;
}

export interface RevenueBreakdown {
  total_revenue_cents: number;
  verified_revenue_cents: number;
  unverified_revenue_cents: number;
  platform_breakdown: PlatformRevenue[];
}

// ============================================================================
// Sync & Integration Types
// ============================================================================

export type SyncStatusState = 'idle' | 'syncing' | 'success' | 'error';

export interface SyncStatus {
  state: SyncStatusState;
  last_sync?: string;
  next_sync?: string;
  error_message?: string;
  platforms_synced: number;
  platforms_total: number;
}

export interface ActiveIntegrationsResponse {
  integrations: PlatformStatus[];
  total_count: number;
  connected_count: number;
}

// ============================================================================
// Data Reconciliation Types
// ============================================================================

export type ReconciliationState = 'pending' | 'matched' | 'unmatched' | 'disputed' | 'resolved';

export interface UnmatchedTransaction {
  id: string;
  platform_id: PlatformId;
  platform_name: string;
  transaction_id: string;
  amount_cents: number;
  timestamp: string;
  status: ReconciliationState;
  reason?: string;
  suggested_match_id?: string;
}

export interface PlatformVariance {
  platform_id: PlatformId;
  platform_name: string;
  expected_revenue_cents: number;
  actual_revenue_cents: number;
  variance_cents: number;
  variance_percentage: number;
  transaction_count: number;
  unmatched_count: number;
  status: 'healthy' | 'warning' | 'critical';
}

export interface DataReconciliationStatus {
  status: 'healthy' | 'warning' | 'critical' | 'pending';
  match_rate: number;
  total_transactions: number;
  matched_transactions: number;
  unmatched_transactions: number;
  total_variance_cents: number;
  platform_variances: PlatformVariance[];
  unmatched_items: UnmatchedTransaction[];
  last_reconciliation?: string;
  next_scheduled?: string;
}

export interface ReconciliationContext {
  status: DataReconciliationStatus;
  is_loading: boolean;
  error?: string;
}

// ============================================================================
// Bulk Action Types
// ============================================================================

export type BulkActionType = 'approve' | 'reject' | 'dispute' | 'assign' | 'export';

export interface BulkActionRequest {
  action: BulkActionType;
  transaction_ids: string[];
  reason?: string;
  assigned_to?: string;
  notes?: string;
}

export interface BulkActionResponse {
  success: boolean;
  processed_count: number;
  failed_count: number;
  errors?: Array<{
    transaction_id: string;
    error: string;
  }>;
}

