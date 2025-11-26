/**
 * Query parameters for Implementation Portal deep linking
 * 
 * Supports contextual navigation from dashboard CTAs to Implementation Portal
 * with analytics tracking via source parameter
 */
export interface ImplementationPortalParams {
  action?: 'connect' | 'retry-sync' | 'configure';
  tab?: 'health' | 'integrations' | 'settings';
  source?: 'reconciliation' | 'integrity-monitor' | 'empty-state' | 'dashboard';
  first?: 'true' | 'false'; // First-time user flag
  platform?: string; // Pre-select specific platform
}

/**
 * Type-safe navigation helper for Implementation Portal
 * 
 * @example
 * const url = buildImplementationPortalUrl({
 *   action: 'connect',
 *   source: 'reconciliation',
 *   first: 'false',
 * });
 * navigate(url); // /implementation-portal?action=connect&source=reconciliation&first=false
 */
export const buildImplementationPortalUrl = (
  params: ImplementationPortalParams
): string => {
  const queryParams = new URLSearchParams();
  
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      queryParams.append(key, value);
    }
  });

  const queryString = queryParams.toString();
  return queryString ? `/implementation-portal?${queryString}` : '/implementation-portal';
};
