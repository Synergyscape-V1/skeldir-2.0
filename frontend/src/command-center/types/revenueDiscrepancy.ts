/**
 * Revenue Discrepancy Alert Banner (Command Center — Constitution)
 */

export type RevenueDiscrepancySeverity = 'caution' | 'critical';

export interface RevenueDiscrepancyAlertModel {
  /** When false, banner is not rendered. */
  visible: boolean;
  /**
   * Amber for ~10–25% magnitude; red for >25% (absolute).
   * Can be derived client-side from `discrepancyPct` if omitted.
   */
  severity?: RevenueDiscrepancySeverity;
  /** e.g. "Facebook" — leads the mandatory copy sentence. */
  primaryPlatformName: string;
  claimedRevenueFormatted: string;
  verifiedRevenueFormatted: string;
  /** e.g. "Stripe" */
  verifiedSource: string;
  /** (verified − claimed) ÷ claimed × 100 */
  discrepancyPct: number;
  /** Optional: “+N other platforms…” */
  otherPlatformsCount?: number;
}
