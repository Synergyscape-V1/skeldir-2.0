import type { components, operations, paths } from "../../types/api/llm-budget";
import {
  buildCentaurHeaders,
  type CentaurRequestHeaders,
  requestJson,
} from "./http";

type BudgetPath = keyof paths;

const CREATE_BUDGET_OPTIMIZATION_PATH: Extract<BudgetPath, "/api/budget/optimize"> =
  "/api/budget/optimize";
const BUDGET_STATUS_PATH_TEMPLATE: Extract<
  BudgetPath,
  "/api/budget/recommendations/{job_id}/status"
> = "/api/budget/recommendations/{job_id}/status";
const BUDGET_RESULT_PATH_TEMPLATE: Extract<
  BudgetPath,
  "/api/budget/recommendations/{job_id}"
> = "/api/budget/recommendations/{job_id}";
const BUDGET_APPROVE_PATH_TEMPLATE: Extract<
  BudgetPath,
  "/api/budget/recommendations/{job_id}/approve"
> = "/api/budget/recommendations/{job_id}/approve";
const BUDGET_REJECT_PATH_TEMPLATE: Extract<
  BudgetPath,
  "/api/budget/recommendations/{job_id}/reject"
> = "/api/budget/recommendations/{job_id}/reject";
const BUDGET_REFINE_PATH_TEMPLATE: Extract<
  BudgetPath,
  "/api/budget/recommendations/{job_id}/refine"
> = "/api/budget/recommendations/{job_id}/refine";
const BUDGET_RERUN_PATH_TEMPLATE: Extract<
  BudgetPath,
  "/api/budget/recommendations/{job_id}/rerun"
> = "/api/budget/recommendations/{job_id}/rerun";
const BUDGET_RETRY_PATH_TEMPLATE: Extract<
  BudgetPath,
  "/api/budget/recommendations/{job_id}/retry"
> = "/api/budget/recommendations/{job_id}/retry";
const BUDGET_CANCEL_PATH_TEMPLATE: Extract<
  BudgetPath,
  "/api/budget/recommendations/{job_id}/cancel"
> = "/api/budget/recommendations/{job_id}/cancel";

type BudgetMutationPath =
  | typeof BUDGET_APPROVE_PATH_TEMPLATE
  | typeof BUDGET_REJECT_PATH_TEMPLATE
  | typeof BUDGET_REFINE_PATH_TEMPLATE
  | typeof BUDGET_RERUN_PATH_TEMPLATE
  | typeof BUDGET_RETRY_PATH_TEMPLATE
  | typeof BUDGET_CANCEL_PATH_TEMPLATE;

export type CreateBudgetOptimizationRequest =
  operations["createBudgetOptimization"]["requestBody"]["content"]["application/json"];
export type CreateBudgetOptimizationAcceptedResponse =
  operations["createBudgetOptimization"]["responses"][202]["content"]["application/json"];
export type BudgetStatusResponse =
  operations["getBudgetRecommendationStatus"]["responses"][200]["content"]["application/json"];
export type BudgetRecommendationResponse =
  operations["getBudgetRecommendation"]["responses"][200]["content"]["application/json"];
export type BudgetMutationRequest = components["schemas"]["BudgetMutationRequest"];
export type BudgetMutationResponse = components["schemas"]["BudgetMutationResponse"];
export type BudgetResultPayload = components["schemas"]["BudgetResultPayload"];
export type BudgetAuthorityBlock = Pick<
  BudgetResultPayload,
  "deterministic_recommendation"
>;
export type BudgetSynthesisBlock = BudgetResultPayload["llm_synthesis"] | undefined;

export interface BudgetSeparatedResult {
  authority: BudgetAuthorityBlock;
  synthesis: BudgetSynthesisBlock;
}

export interface BudgetApiClient {
  createBudgetOptimization(
    payload: CreateBudgetOptimizationRequest,
    headers: CentaurRequestHeaders,
  ): Promise<CreateBudgetOptimizationAcceptedResponse>;
  getBudgetRecommendationStatus(
    jobId: string,
    headers: CentaurRequestHeaders,
  ): Promise<BudgetStatusResponse>;
  getBudgetRecommendation(
    jobId: string,
    headers: CentaurRequestHeaders,
  ): Promise<BudgetRecommendationResponse>;
  approveBudgetRecommendation(
    jobId: string,
    payload: BudgetMutationRequest | undefined,
    headers: CentaurRequestHeaders,
  ): Promise<BudgetMutationResponse>;
  rejectBudgetRecommendation(
    jobId: string,
    payload: BudgetMutationRequest | undefined,
    headers: CentaurRequestHeaders,
  ): Promise<BudgetMutationResponse>;
  refineBudgetRecommendation(
    jobId: string,
    payload: BudgetMutationRequest | undefined,
    headers: CentaurRequestHeaders,
  ): Promise<BudgetMutationResponse>;
  rerunBudgetRecommendation(
    jobId: string,
    payload: BudgetMutationRequest | undefined,
    headers: CentaurRequestHeaders,
  ): Promise<BudgetMutationResponse>;
  retryBudgetRecommendation(
    jobId: string,
    payload: BudgetMutationRequest | undefined,
    headers: CentaurRequestHeaders,
  ): Promise<BudgetMutationResponse>;
  cancelBudgetRecommendation(
    jobId: string,
    payload: BudgetMutationRequest | undefined,
    headers: CentaurRequestHeaders,
  ): Promise<BudgetMutationResponse>;
}

function joinUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/+$/, "")}${path}`;
}

function withJobId(pathTemplate: string, jobId: string): string {
  return pathTemplate.replace("{job_id}", encodeURIComponent(jobId));
}

export function separateBudgetResultPayload(
  payload: BudgetResultPayload,
): BudgetSeparatedResult {
  return {
    authority: {
      deterministic_recommendation: payload.deterministic_recommendation,
    },
    synthesis: payload.llm_synthesis,
  };
}

export function separateBudgetRecommendationResponse(
  response: BudgetRecommendationResponse,
): BudgetSeparatedResult {
  return separateBudgetResultPayload({
    deterministic_recommendation: response.deterministic_recommendation,
    llm_synthesis: response.llm_synthesis,
  });
}

export function createBudgetApiClient(
  baseUrl: string = "http://localhost:4025",
  fetchImpl: typeof fetch = fetch,
): BudgetApiClient {
  async function postMutation(
    pathTemplate: BudgetMutationPath,
    jobId: string,
    payload: BudgetMutationRequest | undefined,
    headers: CentaurRequestHeaders,
  ): Promise<BudgetMutationResponse> {
    return requestJson<BudgetMutationResponse>(
      fetchImpl,
      joinUrl(baseUrl, withJobId(pathTemplate, jobId)),
      {
        method: "POST",
        headers: buildCentaurHeaders(headers, { jsonBody: payload !== undefined }),
        body: payload === undefined ? undefined : JSON.stringify(payload),
      },
    );
  }

  return {
    createBudgetOptimization(payload, headers) {
      return requestJson<CreateBudgetOptimizationAcceptedResponse>(
        fetchImpl,
        joinUrl(baseUrl, CREATE_BUDGET_OPTIMIZATION_PATH),
        {
          method: "POST",
          headers: buildCentaurHeaders(headers, { jsonBody: true }),
          body: JSON.stringify(payload),
        },
      );
    },
    getBudgetRecommendationStatus(jobId, headers) {
      return requestJson<BudgetStatusResponse>(
        fetchImpl,
        joinUrl(baseUrl, withJobId(BUDGET_STATUS_PATH_TEMPLATE, jobId)),
        {
          method: "GET",
          headers: buildCentaurHeaders(headers, { jsonBody: false }),
        },
      );
    },
    getBudgetRecommendation(jobId, headers) {
      return requestJson<BudgetRecommendationResponse>(
        fetchImpl,
        joinUrl(baseUrl, withJobId(BUDGET_RESULT_PATH_TEMPLATE, jobId)),
        {
          method: "GET",
          headers: buildCentaurHeaders(headers, { jsonBody: false }),
        },
      );
    },
    approveBudgetRecommendation(jobId, payload, headers) {
      return postMutation(BUDGET_APPROVE_PATH_TEMPLATE, jobId, payload, headers);
    },
    rejectBudgetRecommendation(jobId, payload, headers) {
      return postMutation(BUDGET_REJECT_PATH_TEMPLATE, jobId, payload, headers);
    },
    refineBudgetRecommendation(jobId, payload, headers) {
      return postMutation(BUDGET_REFINE_PATH_TEMPLATE, jobId, payload, headers);
    },
    rerunBudgetRecommendation(jobId, payload, headers) {
      return postMutation(BUDGET_RERUN_PATH_TEMPLATE, jobId, payload, headers);
    },
    retryBudgetRecommendation(jobId, payload, headers) {
      return postMutation(BUDGET_RETRY_PATH_TEMPLATE, jobId, payload, headers);
    },
    cancelBudgetRecommendation(jobId, payload, headers) {
      return postMutation(BUDGET_CANCEL_PATH_TEMPLATE, jobId, payload, headers);
    },
  };
}
