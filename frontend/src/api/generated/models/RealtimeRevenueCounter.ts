/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type RealtimeRevenueCounter = {
    /**
     * Total verified revenue amount
     */
    total_revenue: number;
    /**
     * Number of revenue events tracked
     */
    event_count: number;
    /**
     * ISO 8601 timestamp of last data update
     */
    last_updated: string;
    /**
     * Seconds since data was last refreshed
     */
    data_freshness_seconds: number;
    /**
     * Whether revenue is verified through payment reconciliation
     */
    verified: boolean;
    /**
     * Optional message about upgrading for more features
     */
    upgrade_notice?: string | null;
};

