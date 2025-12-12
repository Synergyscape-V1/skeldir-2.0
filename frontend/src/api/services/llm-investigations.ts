/**
 * LLM Investigations Service
 * Client for async investigation job processing via LLM
 * B0.2: Uses VITE_LLM_INVESTIGATIONS_URL (http://localhost:4024)
 */

import { createHttpClient } from '../httpClient';
import type { components, operations } from '@/types/api/llm-investigations';

export type InvestigationRequest = components['schemas']['InvestigationRequest'];
export type InvestigationStatusResponse = components['schemas']['InvestigationStatusResponse'];

type StartInvestigationResponse = operations['startInvestigation']['responses']['202']['content']['application/json'];
type GetStatusResponse = operations['getInvestigationStatus']['responses']['200']['content']['application/json'];

const LLM_INVESTIGATIONS_URL = import.meta.env.VITE_LLM_INVESTIGATIONS_URL as string;

if (!LLM_INVESTIGATIONS_URL) {
  console.warn('[LLMInvestigationsService] VITE_LLM_INVESTIGATIONS_URL is not set. Service may not function correctly.');
}

const client = createHttpClient(LLM_INVESTIGATIONS_URL || '');

/**
 * LLM Investigations Service
 * Provides methods for starting investigations and polling for status
 */
export const LLMInvestigationsService = {
  /**
   * Start a new LLM-powered investigation
   * @param payload - Investigation request parameters
   * @returns Promise with investigation ID and initial status
   */
  async startInvestigation(payload: InvestigationRequest): Promise<InvestigationStatusResponse> {
    const response = await client.post<StartInvestigationResponse>(
      '/api/investigations',
      payload
    );
    return response.data;
  },

  /**
   * Get the current status of an investigation
   * @param investigationId - Unique investigation identifier
   * @returns Promise with current investigation status
   */
  async getInvestigationStatus(investigationId: string): Promise<InvestigationStatusResponse> {
    const response = await client.get<GetStatusResponse>(
      `/api/investigations/${investigationId}/status`
    );
    return response.data;
  },
};

export default LLMInvestigationsService;
