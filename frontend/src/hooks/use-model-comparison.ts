/**
 * Model Comparison Hook
 * NOTE: This endpoint is NOT part of B0.2 contracts (attribution.yaml)
 * Returns placeholder data until the endpoint is available
 */

export interface ModelComparison {
  model_name: string;
  attribution_percentage: number;
  revenue_attributed: number;
}

export interface UseModelComparisonOptions {
  enabled?: boolean;
}

export interface UseModelComparisonReturn {
  data: ModelComparison[] | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  correlationId?: string;
}

/**
 * Model comparison endpoint is not available in B0.2
 * Returns placeholder state indicating feature is unavailable
 */
export function useModelComparison(
  _options: UseModelComparisonOptions = {}
): UseModelComparisonReturn {
  return {
    data: null,
    isLoading: false,
    error: new Error('Model comparison endpoint not available in B0.2'),
    refetch: () => {},
    correlationId: undefined,
  };
}
