/**
 * LLM Budget Optimization Service
 * Client for budget allocation optimization via LLM
 * B0.2: Uses VITE_LLM_BUDGET_URL (http://localhost:4025)
 */

import { createHttpClient } from '../httpClient';
import type { components, operations } from '@/types/api/llm-budget';

export type BudgetOptimizationRequest = components['schemas']['BudgetOptimizationRequest'];
export type BudgetOptimizationResponse = components['schemas']['BudgetOptimizationResponse'];

type OptimizeResponse = operations['optimizeBudget']['responses']['200']['content']['application/json'];

const LLM_BUDGET_URL = import.meta.env.VITE_LLM_BUDGET_URL as string;

if (!LLM_BUDGET_URL) {
  console.warn('[LLMBudgetService] VITE_LLM_BUDGET_URL is not set. Service may not function correctly.');
}

const client = createHttpClient(LLM_BUDGET_URL || '');

/**
 * LLM Budget Optimization Service
 * Provides methods for budget allocation optimization
 */
export const LLMBudgetService = {
  /**
   * Optimize budget allocation using LLM analysis
   * @param payload - Budget optimization request with platforms and constraints
   * @returns Promise with optimization recommendations
   */
  async optimizeBudget(payload: BudgetOptimizationRequest): Promise<BudgetOptimizationResponse> {
    const response = await client.post<OptimizeResponse>(
      '/api/budget/optimization',
      payload
    );
    return response.data;
  },
};

export default LLMBudgetService;
