import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewExceptions } from '../ledger/permissions';
import { DETAIL_COPY } from '../detail/copy';
import { incrementDetailRequest, resetDetailRequestCounter } from '../detail/requestCounter';
import { validateExceptionDetailDto } from '../detail/detailDtoValidation';
import type { ExceptionDetailOutcome } from '../detail/types';
import { CANONICAL_EXCEPTION_FIXTURES } from './exceptionsFixtures';
import { buildExceptionDetailFromQueueRow } from './exceptionDetailGuidance';

export function createExceptionDetailClient(): {
  getExceptionDetail(
    tenantId: string,
    exceptionId: string,
    signal?: AbortSignal,
  ): Promise<ExceptionDetailOutcome>;
} {
  return {
    async getExceptionDetail(tenantId, exceptionId, signal) {
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
      resetDetailRequestCounter();
      incrementDetailRequest('exception-detail');

      if (!canViewExceptions(getCurrentUserRole())) {
        return { kind: 'permission_denied', message: DETAIL_COPY.permissionDenied };
      }
      if (!tenantId || !/^exc_\d{4}$/.test(exceptionId)) {
        return { kind: 'not_found', message: DETAIL_COPY.notFound };
      }

      const row = CANONICAL_EXCEPTION_FIXTURES.find((entry) => entry.exceptionId === exceptionId);
      if (!row) {
        return { kind: 'not_found', message: DETAIL_COPY.notFound };
      }

      const detail = buildExceptionDetailFromQueueRow(row, tenantId);

      const validation = validateExceptionDetailDto(detail, exceptionId, tenantId);
      if (!validation.ok) {
        return {
          kind: validation.kind,
          message:
            validation.kind === 'object_id_mismatch'
              ? DETAIL_COPY.objectIdMismatch
              : DETAIL_COPY.scopeDenied,
        };
      }

      return { kind: 'loaded', detail };
    },
  };
}

let defaultClient: ReturnType<typeof createExceptionDetailClient> | null = null;

export function getDefaultExceptionDetailClient() {
  if (!defaultClient) defaultClient = createExceptionDetailClient();
  return defaultClient;
}

export function resetDefaultExceptionDetailClient(): void {
  defaultClient = null;
}
