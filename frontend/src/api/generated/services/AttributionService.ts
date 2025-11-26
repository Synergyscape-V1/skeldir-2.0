/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RealtimeRevenueCounter } from '../models/RealtimeRevenueCounter';
import type { CancelablePromise } from '../core/CancelablePromise';
import type { BaseHttpRequest } from '../core/BaseHttpRequest';
export class AttributionService {
    constructor(public readonly httpRequest: BaseHttpRequest) {}
    /**
     * Get Realtime Revenue Counter
     * Polls realtime revenue metrics with 30-second cache TTL.
     * Supports ETag-based caching with If-None-Match header.
     *
     * @param xCorrelationId Request correlation ID for tracing
     * @param ifNoneMatch ETag from previous response for cache validation
     * @returns RealtimeRevenueCounter Revenue counter data returned successfully
     * @throws ApiError
     */
    public getRealtimeRevenue(
        xCorrelationId: string,
        ifNoneMatch?: string,
    ): CancelablePromise<RealtimeRevenueCounter> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/attribution/revenue/realtime',
            headers: {
                'X-Correlation-ID': xCorrelationId,
                'If-None-Match': ifNoneMatch,
            },
            errors: {
                304: `Not Modified - ETag matches, use cached data`,
                401: `Unauthorized - Invalid or expired token`,
                429: `Too Many Requests - Rate limit exceeded`,
                500: `Internal Server Error`,
            },
        });
    }
}
