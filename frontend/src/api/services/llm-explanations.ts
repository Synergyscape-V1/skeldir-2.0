/**
 * LLM Explanations Service
 * Client for natural language entity explanations via LLM
 * B0.2: Uses VITE_LLM_EXPLANATIONS_URL (http://localhost:4026)
 */

import { createHttpClient } from '../httpClient';
import type { components, operations } from '@/types/api/llm-explanations';

export type EntityExplanationResponse = components['schemas']['EntityExplanationResponse'];

export type EntityType = 'transaction' | 'reconciliation' | 'attribution' | 'discrepancy' | 'platform' | 'metric';
export type DetailLevel = 'brief' | 'standard' | 'detailed';
export type Audience = 'technical' | 'business' | 'executive';

type GetExplanationResponse = operations['getExplanation']['responses']['200']['content']['application/json'];

const LLM_EXPLANATIONS_URL = import.meta.env.VITE_LLM_EXPLANATIONS_URL as string;

if (!LLM_EXPLANATIONS_URL) {
  console.warn('[LLMExplanationsService] VITE_LLM_EXPLANATIONS_URL is not set. Service may not function correctly.');
}

const client = createHttpClient(LLM_EXPLANATIONS_URL || '');

/**
 * Options for explanation generation
 */
export interface ExplanationOptions {
  detailLevel?: DetailLevel;
  audience?: Audience;
}

/**
 * LLM Explanations Service
 * Provides methods for generating natural language explanations
 */
export const LLMExplanationsService = {
  /**
   * Get an LLM-generated explanation for an entity
   * @param entityType - Type of entity to explain
   * @param entityId - Unique identifier of the entity
   * @param options - Optional parameters for detail level and audience
   * @returns Promise with generated explanation
   */
  async getExplanation(
    entityType: EntityType,
    entityId: string,
    options?: ExplanationOptions
  ): Promise<EntityExplanationResponse> {
    const params: Record<string, string> = {};
    
    if (options?.detailLevel) {
      params.detail_level = options.detailLevel;
    }
    if (options?.audience) {
      params.audience = options.audience;
    }

    const response = await client.get<GetExplanationResponse>(
      `/api/v1/explain/${entityType}/${entityId}`,
      { params }
    );
    return response.data;
  },
};

export default LLMExplanationsService;
