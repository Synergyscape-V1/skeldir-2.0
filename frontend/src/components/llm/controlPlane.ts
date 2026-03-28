import type { BudgetStatusResponse } from "../../api/contracts";
import type { InvestigationStatusResponse } from "../../api/contracts";
import { ApiContractError } from "../../api/contracts";

export type CentaurLifecycleStatus =
  | BudgetStatusResponse["status"]
  | InvestigationStatusResponse["status"];

export type CentaurMutationAction =
  | BudgetStatusResponse["available_actions"][number]
  | InvestigationStatusResponse["available_actions"][number];

export interface CentaurLifecycleSnapshot {
  status: CentaurLifecycleStatus;
  isAuthoritative: boolean;
  progressPercentage?: number;
  currentStep?: string;
  reviewRequired: boolean;
  availableActions: CentaurMutationAction[];
  estimatedDurationSeconds?: number;
  dataFreshnessSeconds?: number;
  lastUpdated?: string;
  failure?: {
    code: "failed" | "timeout" | "cancelled" | "rejected";
    reason: string;
  };
}

export interface CentaurLifecycleDescriptor {
  tone: "compute" | "review" | "retry" | "terminal" | "failure";
  title: string;
  detail: string;
}

export interface CentaurMutationAttemptState {
  fingerprint: string | null;
  idempotencyKey: string | null;
}

export type CentaurMutationIssueKind =
  | "invalid_state_transition"
  | "validation_error"
  | "idempotency_conflict"
  | "result_not_ready"
  | "not_found"
  | "server_or_network"
  | "unknown";

export interface CentaurMutationIssue {
  kind: CentaurMutationIssueKind;
  status?: number;
  code?: string;
  title: string;
  detail: string;
  retryable: boolean;
}

interface ProblemDetailsPayload {
  status?: number;
  title?: string;
  detail?: string;
  code?: string;
}

const RESULT_READY_STATUSES = new Set<CentaurLifecycleStatus>([
  "ready_for_review",
  "approved",
  "rejected",
  "completed",
]);

export function createStableUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = Math.floor(Math.random() * 16);
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function createMutationAttemptFingerprint(
  action: CentaurMutationAction,
  reasonOrNote: string,
): string {
  return `${action}:${reasonOrNote.trim()}`;
}

export function resolveAttemptIdempotencyKey(
  attemptState: CentaurMutationAttemptState,
  fingerprint: string,
): string {
  if (
    attemptState.fingerprint === fingerprint &&
    typeof attemptState.idempotencyKey === "string" &&
    attemptState.idempotencyKey.length > 0
  ) {
    return attemptState.idempotencyKey;
  }
  const nextKey = createStableUuid();
  attemptState.fingerprint = fingerprint;
  attemptState.idempotencyKey = nextKey;
  return nextKey;
}

export function clearMutationAttemptState(
  attemptState: CentaurMutationAttemptState,
): void {
  attemptState.fingerprint = null;
  attemptState.idempotencyKey = null;
}

function parseProblemDetails(bodyText: string): ProblemDetailsPayload | null {
  if (!bodyText || bodyText.trim().length === 0) {
    return null;
  }
  try {
    const parsed = JSON.parse(bodyText) as ProblemDetailsPayload;
    if (typeof parsed !== "object" || parsed === null) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function mapMutationErrorToIssue(error: unknown): CentaurMutationIssue {
  if (error instanceof ApiContractError) {
    const problem = parseProblemDetails(error.bodyText);
    const status = problem?.status ?? error.status;
    const code = problem?.code;
    const detail =
      problem?.detail ??
      (error.bodyText.trim().length > 0 ? error.bodyText : "Mutation request failed.");
    const title = problem?.title ?? "Mutation Error";

    if (status === 409 && code === "INVALID_STATE_TRANSITION") {
      return {
        kind: "invalid_state_transition",
        status,
        code,
        title: "Invalid State Transition",
        detail,
        retryable: false,
      };
    }
    if (status === 409 && code === "IDEMPOTENCY_KEY_CONFLICT") {
      return {
        kind: "idempotency_conflict",
        status,
        code,
        title: "Idempotency Conflict",
        detail,
        retryable: false,
      };
    }
    if (status === 409 && code === "RESULT_NOT_READY") {
      return {
        kind: "result_not_ready",
        status,
        code,
        title: "Result Not Ready",
        detail,
        retryable: true,
      };
    }
    if (status === 400 || status === 422) {
      return {
        kind: "validation_error",
        status,
        code,
        title: "Validation Error",
        detail,
        retryable: false,
      };
    }
    if (status === 404) {
      return {
        kind: "not_found",
        status,
        code,
        title: "Resource Not Found",
        detail,
        retryable: false,
      };
    }
    if (status >= 500) {
      return {
        kind: "server_or_network",
        status,
        code,
        title: "Server Failure",
        detail,
        retryable: true,
      };
    }
    return {
      kind: "unknown",
      status,
      code,
      title,
      detail,
      retryable: false,
    };
  }

  if (error instanceof Error) {
    return {
      kind: "server_or_network",
      title: "Network or Runtime Failure",
      detail: error.message,
      retryable: true,
    };
  }

  return {
    kind: "unknown",
    title: "Unknown Mutation Failure",
    detail: String(error),
    retryable: false,
  };
}

export function isResultReadyStatus(status: CentaurLifecycleStatus): boolean {
  return RESULT_READY_STATUSES.has(status);
}

export function isReviewRailVisible(
  snapshot: CentaurLifecycleSnapshot,
): boolean {
  if (snapshot.isAuthoritative === false) {
    return false;
  }
  if (!snapshot.reviewRequired) {
    return false;
  }
  if (snapshot.status !== "ready_for_review") {
    return false;
  }
  return snapshot.availableActions.length > 0;
}

export function describeCentaurLifecycle(
  snapshot: CentaurLifecycleSnapshot,
): CentaurLifecycleDescriptor {
  switch (snapshot.status) {
    case "submitted":
      return {
        tone: "compute",
        title: "Submitted",
        detail: "Request accepted. Validation will begin shortly.",
      };
    case "validating":
      return {
        tone: "compute",
        title: "Validating",
        detail: "Inputs are being validated against contract constraints.",
      };
    case "investigating":
      return {
        tone: "compute",
        title: "Investigating",
        detail: "Machine workflow is executing deterministic analysis.",
      };
    case "ready_for_review":
      return {
        tone: "review",
        title: "Ready For Review",
        detail:
          "Machine output is ready. A reviewer decision is required before completion.",
      };
    case "approved":
      return {
        tone: "terminal",
        title: "Approved",
        detail: "Reviewer approved the machine output.",
      };
    case "rejected":
      return {
        tone: "terminal",
        title: "Rejected",
        detail: "Reviewer rejected the output. No automatic action is applied.",
      };
    case "refine_requested":
      return {
        tone: "retry",
        title: "Refine Requested",
        detail: "Reviewer requested refinement before a final decision.",
      };
    case "rerun_requested":
      return {
        tone: "retry",
        title: "Rerun Requested",
        detail: "A rerun has been requested and will transition back to compute.",
      };
    case "completed":
      return {
        tone: "terminal",
        title: "Completed",
        detail: "Lifecycle is complete with reviewer-governed finalization.",
      };
    case "failed":
      return {
        tone: "failure",
        title: "Failed",
        detail: snapshot.failure?.reason ?? "Execution failed before completion.",
      };
    case "timeout":
      return {
        tone: "failure",
        title: "Timeout",
        detail:
          snapshot.failure?.reason ??
          "Execution timed out before a review decision could be finalized.",
      };
    case "cancelled":
      return {
        tone: "failure",
        title: "Cancelled",
        detail: snapshot.failure?.reason ?? "Lifecycle was cancelled.",
      };
    default:
      return {
        tone: "failure",
        title: "Unknown State",
        detail: "Unrecognized lifecycle state.",
      };
  }
}

export function formatIsoDateTime(value?: string): string {
  if (!value) {
    return "n/a";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "n/a";
  }
  return parsed.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
