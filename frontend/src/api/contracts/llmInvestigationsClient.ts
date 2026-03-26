import type { components, operations, paths } from "../../types/api/llm-investigations";
import {
  buildCentaurHeaders,
  type CentaurRequestHeaders,
  requestJson,
} from "./http";

type InvestigationPath = keyof paths;

const CREATE_INVESTIGATION_PATH: Extract<InvestigationPath, "/api/investigations"> =
  "/api/investigations";
const INVESTIGATION_STATUS_PATH_TEMPLATE: Extract<
  InvestigationPath,
  "/api/investigations/{investigation_id}/status"
> = "/api/investigations/{investigation_id}/status";
const INVESTIGATION_RESULT_PATH_TEMPLATE: Extract<
  InvestigationPath,
  "/api/investigations/{investigation_id}"
> = "/api/investigations/{investigation_id}";
const INVESTIGATION_APPROVE_PATH_TEMPLATE: Extract<
  InvestigationPath,
  "/api/investigations/{investigation_id}/approve"
> = "/api/investigations/{investigation_id}/approve";
const INVESTIGATION_REJECT_PATH_TEMPLATE: Extract<
  InvestigationPath,
  "/api/investigations/{investigation_id}/reject"
> = "/api/investigations/{investigation_id}/reject";
const INVESTIGATION_REFINE_PATH_TEMPLATE: Extract<
  InvestigationPath,
  "/api/investigations/{investigation_id}/refine"
> = "/api/investigations/{investigation_id}/refine";
const INVESTIGATION_RERUN_PATH_TEMPLATE: Extract<
  InvestigationPath,
  "/api/investigations/{investigation_id}/rerun"
> = "/api/investigations/{investigation_id}/rerun";
const INVESTIGATION_RETRY_PATH_TEMPLATE: Extract<
  InvestigationPath,
  "/api/investigations/{investigation_id}/retry"
> = "/api/investigations/{investigation_id}/retry";
const INVESTIGATION_CANCEL_PATH_TEMPLATE: Extract<
  InvestigationPath,
  "/api/investigations/{investigation_id}/cancel"
> = "/api/investigations/{investigation_id}/cancel";

type InvestigationMutationPath =
  | typeof INVESTIGATION_APPROVE_PATH_TEMPLATE
  | typeof INVESTIGATION_REJECT_PATH_TEMPLATE
  | typeof INVESTIGATION_REFINE_PATH_TEMPLATE
  | typeof INVESTIGATION_RERUN_PATH_TEMPLATE
  | typeof INVESTIGATION_RETRY_PATH_TEMPLATE
  | typeof INVESTIGATION_CANCEL_PATH_TEMPLATE;

export type CreateInvestigationRequest =
  operations["createInvestigation"]["requestBody"]["content"]["application/json"];
export type CreateInvestigationAcceptedResponse =
  operations["createInvestigation"]["responses"][202]["content"]["application/json"];
export type InvestigationStatusResponse =
  operations["getInvestigationStatus"]["responses"][200]["content"]["application/json"];
export type InvestigationResultResponse =
  operations["getInvestigationResult"]["responses"][200]["content"]["application/json"];
export type InvestigationMutationRequest =
  components["schemas"]["InvestigationMutationRequest"];
export type InvestigationMutationResponse =
  components["schemas"]["InvestigationMutationResponse"];
export type InvestigationResultPayload = components["schemas"]["InvestigationResultPayload"];
export type InvestigationAuthorityBlock = Pick<
  InvestigationResultPayload,
  "deterministic_findings"
>;
export type InvestigationSynthesisBlock =
  InvestigationResultPayload["llm_synthesis"] | undefined;

export interface InvestigationSeparatedResult {
  authority: InvestigationAuthorityBlock;
  synthesis: InvestigationSynthesisBlock;
}

export interface InvestigationsApiClient {
  createInvestigation(
    payload: CreateInvestigationRequest,
    headers: CentaurRequestHeaders,
  ): Promise<CreateInvestigationAcceptedResponse>;
  getInvestigationStatus(
    investigationId: string,
    headers: CentaurRequestHeaders,
  ): Promise<InvestigationStatusResponse>;
  getInvestigationResult(
    investigationId: string,
    headers: CentaurRequestHeaders,
  ): Promise<InvestigationResultResponse>;
  approveInvestigation(
    investigationId: string,
    payload: InvestigationMutationRequest | undefined,
    headers: CentaurRequestHeaders,
  ): Promise<InvestigationMutationResponse>;
  rejectInvestigation(
    investigationId: string,
    payload: InvestigationMutationRequest | undefined,
    headers: CentaurRequestHeaders,
  ): Promise<InvestigationMutationResponse>;
  refineInvestigation(
    investigationId: string,
    payload: InvestigationMutationRequest | undefined,
    headers: CentaurRequestHeaders,
  ): Promise<InvestigationMutationResponse>;
  rerunInvestigation(
    investigationId: string,
    payload: InvestigationMutationRequest | undefined,
    headers: CentaurRequestHeaders,
  ): Promise<InvestigationMutationResponse>;
  retryInvestigation(
    investigationId: string,
    payload: InvestigationMutationRequest | undefined,
    headers: CentaurRequestHeaders,
  ): Promise<InvestigationMutationResponse>;
  cancelInvestigation(
    investigationId: string,
    payload: InvestigationMutationRequest | undefined,
    headers: CentaurRequestHeaders,
  ): Promise<InvestigationMutationResponse>;
}

function joinUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/+$/, "")}${path}`;
}

function withInvestigationId(pathTemplate: string, investigationId: string): string {
  return pathTemplate.replace(
    "{investigation_id}",
    encodeURIComponent(investigationId),
  );
}

export function separateInvestigationResultPayload(
  payload: InvestigationResultPayload,
): InvestigationSeparatedResult {
  return {
    authority: {
      deterministic_findings: payload.deterministic_findings,
    },
    synthesis: payload.llm_synthesis,
  };
}

export function separateInvestigationResultResponse(
  response: InvestigationResultResponse,
): InvestigationSeparatedResult {
  return separateInvestigationResultPayload({
    deterministic_findings: response.deterministic_findings,
    llm_synthesis: response.llm_synthesis,
  });
}

export function createInvestigationsApiClient(
  baseUrl: string = "http://localhost:4024",
  fetchImpl: typeof fetch = fetch,
): InvestigationsApiClient {
  async function postMutation(
    pathTemplate: InvestigationMutationPath,
    investigationId: string,
    payload: InvestigationMutationRequest | undefined,
    headers: CentaurRequestHeaders,
  ): Promise<InvestigationMutationResponse> {
    return requestJson<InvestigationMutationResponse>(
      fetchImpl,
      joinUrl(baseUrl, withInvestigationId(pathTemplate, investigationId)),
      {
        method: "POST",
        headers: buildCentaurHeaders(headers, { jsonBody: payload !== undefined }),
        body: payload === undefined ? undefined : JSON.stringify(payload),
      },
    );
  }

  return {
    createInvestigation(payload, headers) {
      return requestJson<CreateInvestigationAcceptedResponse>(
        fetchImpl,
        joinUrl(baseUrl, CREATE_INVESTIGATION_PATH),
        {
          method: "POST",
          headers: buildCentaurHeaders(headers, { jsonBody: true }),
          body: JSON.stringify(payload),
        },
      );
    },
    getInvestigationStatus(investigationId, headers) {
      return requestJson<InvestigationStatusResponse>(
        fetchImpl,
        joinUrl(
          baseUrl,
          withInvestigationId(INVESTIGATION_STATUS_PATH_TEMPLATE, investigationId),
        ),
        {
          method: "GET",
          headers: buildCentaurHeaders(headers, { jsonBody: false }),
        },
      );
    },
    getInvestigationResult(investigationId, headers) {
      return requestJson<InvestigationResultResponse>(
        fetchImpl,
        joinUrl(
          baseUrl,
          withInvestigationId(INVESTIGATION_RESULT_PATH_TEMPLATE, investigationId),
        ),
        {
          method: "GET",
          headers: buildCentaurHeaders(headers, { jsonBody: false }),
        },
      );
    },
    approveInvestigation(investigationId, payload, headers) {
      return postMutation(
        INVESTIGATION_APPROVE_PATH_TEMPLATE,
        investigationId,
        payload,
        headers,
      );
    },
    rejectInvestigation(investigationId, payload, headers) {
      return postMutation(
        INVESTIGATION_REJECT_PATH_TEMPLATE,
        investigationId,
        payload,
        headers,
      );
    },
    refineInvestigation(investigationId, payload, headers) {
      return postMutation(
        INVESTIGATION_REFINE_PATH_TEMPLATE,
        investigationId,
        payload,
        headers,
      );
    },
    rerunInvestigation(investigationId, payload, headers) {
      return postMutation(
        INVESTIGATION_RERUN_PATH_TEMPLATE,
        investigationId,
        payload,
        headers,
      );
    },
    retryInvestigation(investigationId, payload, headers) {
      return postMutation(
        INVESTIGATION_RETRY_PATH_TEMPLATE,
        investigationId,
        payload,
        headers,
      );
    },
    cancelInvestigation(investigationId, payload, headers) {
      return postMutation(
        INVESTIGATION_CANCEL_PATH_TEMPLATE,
        investigationId,
        payload,
        headers,
      );
    },
  };
}
