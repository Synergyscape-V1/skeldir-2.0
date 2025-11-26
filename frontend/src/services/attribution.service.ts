/**
 * Attribution Service Layer
 * Handles all API communication for attribution data
 * Per Architecture Guide Section 2.3: Service Layer handles all API communication
 */

import type { ApiResponse } from '@/hooks/use-api-client';

export interface RevenueMetric {
  value: number;
  currency: string;
  verified: boolean;
}

export interface ActivityItem {
  id: number;
  action: string;
  time: string;
}

export interface AttributionData {
  revenueMetrics: RevenueMetric[];
  activity: ActivityItem[];
}

export interface ApiClient {
  get: <T>(url: string, opts?: { headers?: Record<string, string>; signal?: AbortSignal }) => Promise<ApiResponse<T>>;
  post: <TReq, TRes>(url: string, body?: TReq, opts?: { headers?: Record<string, string>; signal?: AbortSignal }) => Promise<ApiResponse<TRes>>;
  put: <TReq, TRes>(url: string, body?: TReq, opts?: { headers?: Record<string, string>; signal?: AbortSignal }) => Promise<ApiResponse<TRes>>;
  patch: <TReq, TRes>(url: string, body?: TReq, opts?: { headers?: Record<string, string>; signal?: AbortSignal }) => Promise<ApiResponse<TRes>>;
  delete: <TRes>(url: string, opts?: { headers?: Record<string, string>; signal?: AbortSignal }) => Promise<ApiResponse<TRes>>;
}

/**
 * Fetch revenue metrics from backend
 * Endpoint: /api/attribution/revenue
 * Note: API client automatically unwraps backend's { data: [...] } format
 * Returns: ApiResponse<RevenueMetric[]>
 */
export async function fetchRevenueMetrics(
  apiClient: ApiClient
): Promise<ApiResponse<RevenueMetric[]>> {
  return apiClient.get<RevenueMetric[]>('/api/attribution/revenue');
}

/**
 * Fetch user activity from backend
 * Endpoint: /api/attribution/activity
 * Note: API client automatically unwraps backend's { data: [...] } format
 * Returns: ApiResponse<ActivityItem[]>
 */
export async function fetchActivity(
  apiClient: ApiClient
): Promise<ApiResponse<ActivityItem[]>> {
  return apiClient.get<ActivityItem[]>('/api/attribution/activity');
}

/**
 * Fetch complete attribution data
 * Endpoint: /api/attribution/data
 */
export async function fetchAttributionData(
  apiClient: ApiClient
): Promise<ApiResponse<AttributionData>> {
  return apiClient.get<AttributionData>('/api/attribution/data');
}

/**
 * Transform revenue metrics into DualRevenueCard format
 */
export interface DualRevenueData {
  verifiedRevenue: number;
  unverifiedRevenue: number;
  totalRevenue: number;
  verifiedPercentage: number;
  unverifiedPercentage: number;
  timestamp: string;
  currency: 'USD' | 'EUR';
  confidenceScore?: number;
}

export async function fetchDualRevenueData(
  apiClient: ApiClient
): Promise<DualRevenueData> {
  const response = await fetchRevenueMetrics(apiClient);
  
  if (response.error) {
    // Return zeros instead of throwing to keep the card stable
    return {
      verifiedRevenue: 0,
      unverifiedRevenue: 0,
      totalRevenue: 0,
      verifiedPercentage: 0,
      unverifiedPercentage: 0,
      timestamp: new Date().toISOString(),
      currency: 'USD'
    };
  }
  
  // API client already unwrapped backend's { data: [...] } to response.data
  const metrics = response.data || [];
  
  // Defensive: handle empty or malformed datasets
  if (!Array.isArray(metrics) || metrics.length === 0) {
    return {
      verifiedRevenue: 0,
      unverifiedRevenue: 0,
      totalRevenue: 0,
      verifiedPercentage: 0,
      unverifiedPercentage: 0,
      timestamp: new Date().toISOString(),
      currency: 'USD'
    };
  }
  
  const verifiedMetrics = metrics.filter(m => m.verified);
  const unverifiedMetrics = metrics.filter(m => !m.verified);
  
  const verifiedRevenue = verifiedMetrics.reduce((sum, m) => sum + (m.value || 0), 0);
  const unverifiedRevenue = unverifiedMetrics.reduce((sum, m) => sum + (m.value || 0), 0);
  const totalRevenue = verifiedRevenue + unverifiedRevenue;
  
  const verifiedPercentage = totalRevenue > 0 ? (verifiedRevenue / totalRevenue) * 100 : 0;
  const unverifiedPercentage = totalRevenue > 0 ? (unverifiedRevenue / totalRevenue) * 100 : 0;
  
  // Use first metric's currency or default to USD
  const currency = (metrics[0]?.currency === 'EUR' ? 'EUR' : 'USD') as 'USD' | 'EUR';
  
  const confidenceScore = totalRevenue > 0 ? (verifiedRevenue / totalRevenue) : undefined;
  
  return {
    verifiedRevenue,
    unverifiedRevenue,
    totalRevenue,
    verifiedPercentage,
    unverifiedPercentage,
    timestamp: new Date().toISOString(),
    currency,
    confidenceScore
  };
}
