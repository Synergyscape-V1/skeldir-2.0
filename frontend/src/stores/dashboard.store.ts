/**
 * Dashboard Store - Centralized State Management
 * Per Architecture Guide Section 2.1: Use centralized state store (Zustand)
 * Replaces scattered useState hooks in Dashboard.tsx
 * Integrates with Service Layer per Architecture Guide Section 2.3
 */

import { create } from 'zustand';
import type { ActivityItem } from '@/services/attribution.service';
import type { ApiClient } from '@/services/attribution.service';
import { fetchActivity } from '@/services/attribution.service';

type ActivityStatus = 'loading' | 'error' | 'empty' | 'success';

/**
 * Deep equality check for activity items
 * Prevents unnecessary re-renders when data hasn't actually changed
 */
function areActivitiesEqual(a: ActivityItem[], b: ActivityItem[]): boolean {
  if (a.length !== b.length) return false;
  
  return a.every((item, index) => {
    const other = b[index];
    return item.id === other.id && 
           item.action === other.action && 
           item.time === other.time;
  });
}

interface DashboardState {
  // Activity state
  activityStatus: ActivityStatus;
  activityData: ActivityItem[];
  lastFetchTime: Date | null;
  
  // Actions
  setActivityStatus: (status: ActivityStatus) => void;
  setActivityData: (data: ActivityItem[]) => void;
  loadActivity: (apiClient: ApiClient) => Promise<void>;
  retryActivity: (apiClient: ApiClient) => void;
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  // Initial state
  activityStatus: 'loading',
  activityData: [],
  lastFetchTime: null,
  
  // Actions
  setActivityStatus: (status) => set({ activityStatus: status }),
  
  setActivityData: (data) => set({ activityData: data }),
  
  /**
   * Load activity data using Service Layer
   * Per Architecture Guide: Component → State Manager → Service Layer
   */
  loadActivity: async (apiClient: ApiClient) => {
    const currentData = get().activityData;
    set({ activityStatus: 'loading' });
    
    try {
      // Call service layer to fetch activity
      const response = await fetchActivity(apiClient);
      
      if (response.error) {
        // Handle API error
        console.error('[DashboardStore] Failed to load activity:', response.error);
        set({ activityStatus: 'error' });
        return;
      }
      
      // API client already unwraps backend's { data: [...] } to { data: [...], error: null }
      // So response.data is the ActivityItem[] array directly
      const data = response.data || [];
      
      // Check if data actually changed to prevent unnecessary re-renders
      if (areActivitiesEqual(currentData, data)) {
        // Data unchanged, just update status and timestamp without triggering activityData change
        set({ activityStatus: 'success', lastFetchTime: new Date() });
        return;
      }
      
      if (data.length === 0) {
        set({ activityStatus: 'empty', activityData: [], lastFetchTime: new Date() });
      } else {
        set({ activityStatus: 'success', activityData: data, lastFetchTime: new Date() });
      }
    } catch (error) {
      console.error('[DashboardStore] Unexpected error loading activity:', error);
      set({ activityStatus: 'error' });
    }
  },
  
  /**
   * Retry loading activity
   * Uses same service layer pattern
   */
  retryActivity: (apiClient: ApiClient) => {
    if (import.meta.env.DEV) {
      console.log('[DashboardStore] Retry clicked, reloading activity');
    }
    get().loadActivity(apiClient);
  },
}));
