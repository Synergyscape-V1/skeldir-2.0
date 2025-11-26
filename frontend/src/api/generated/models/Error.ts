/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type Error = {
    /**
     * Error type/code
     */
    error: string;
    /**
     * Human-readable error message
     */
    message: string;
    /**
     * ISO 8601 timestamp of error
     */
    timestamp: string;
    /**
     * Request correlation ID for support/debugging
     */
    correlation_id: string;
    /**
     * Additional error context
     */
    details?: Record<string, any>;
};

