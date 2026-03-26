export interface CentaurRequestHeaders {
  correlationId: string;
  authorization?: string;
  idempotencyKey?: string;
}

export class ApiContractError extends Error {
  public readonly status: number;

  public readonly bodyText: string;

  public constructor(status: number, bodyText: string) {
    super(`API request failed with status ${status}`);
    this.status = status;
    this.bodyText = bodyText;
  }
}

export function buildCentaurHeaders(
  headers: CentaurRequestHeaders,
  options: { jsonBody: boolean },
): Record<string, string> {
  const result: Record<string, string> = {
    "X-Correlation-ID": headers.correlationId,
    Accept: "application/json",
  };

  if (options.jsonBody) {
    result["Content-Type"] = "application/json";
  }
  if (headers.authorization) {
    result.Authorization = headers.authorization;
  }
  if (headers.idempotencyKey) {
    result["X-Idempotency-Key"] = headers.idempotencyKey;
  }

  return result;
}

export async function requestJson<TResponse>(
  fetchImpl: typeof fetch,
  url: string,
  init: RequestInit,
): Promise<TResponse> {
  const response = await fetchImpl(url, init);
  const bodyText = await response.text();
  if (!response.ok) {
    throw new ApiContractError(response.status, bodyText);
  }
  return bodyText.length === 0 ? ({} as TResponse) : (JSON.parse(bodyText) as TResponse);
}
