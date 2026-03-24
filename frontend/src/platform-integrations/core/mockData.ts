import { PLATFORM_REGISTRY } from "./constants";
import type {
  Platform,
  PlatformIntegrationsData,
  PlatformIntegrationsScenario,
} from "./types";

function minutesAgo(minutes: number): Date {
  return new Date(Date.now() - minutes * 60_000);
}

function hoursAgo(hours: number): Date {
  return new Date(Date.now() - hours * 3_600_000);
}

function daysAgo(days: number): Date {
  return new Date(Date.now() - days * 86_400_000);
}

const ALL_HEALTHY: Platform[] = [
  {
    ...PLATFORM_REGISTRY[0],
    status: "connected",
    connectionDetails: {
      connectedAt: daysAgo(45),
      lastSyncAt: minutesAgo(3),
      accountId: "123-456-7890",
      accountName: "Acme Corp Main",
    },
  },
  {
    ...PLATFORM_REGISTRY[1],
    status: "connected",
    connectionDetails: {
      connectedAt: daysAgo(30),
      lastSyncAt: minutesAgo(5),
      accountId: "act_987654321",
      accountName: "Acme Marketing",
    },
  },
  {
    ...PLATFORM_REGISTRY[2],
    status: "connected",
    connectionDetails: {
      connectedAt: daysAgo(60),
      lastSyncAt: minutesAgo(8),
      accountId: "li_555888",
      accountName: "Acme B2B",
    },
  },
  {
    ...PLATFORM_REGISTRY[3],
    status: "connected",
    connectionDetails: {
      connectedAt: daysAgo(20),
      lastSyncAt: minutesAgo(12),
      accountId: "tt_112233",
      accountName: "Acme TikTok",
    },
  },
  {
    ...PLATFORM_REGISTRY[4],
    status: "connected",
    connectionDetails: {
      connectedAt: daysAgo(90),
      lastSyncAt: minutesAgo(10),
      accountId: "hs_44556",
      accountName: "Acme HubSpot",
    },
  },
  {
    ...PLATFORM_REGISTRY[5],
    status: "connected",
    connectionDetails: {
      connectedAt: daysAgo(120),
      lastSyncAt: minutesAgo(15),
      accountId: "sf_778899",
      accountName: "Acme Salesforce",
    },
  },
];

const MIXED: Platform[] = [
  {
    ...PLATFORM_REGISTRY[0],
    status: "disconnected",
    connectionDetails: {
      connectedAt: daysAgo(45),
      lastSyncAt: daysAgo(2),
      accountId: "123-456-7890",
      accountName: "Acme Corp Main",
      error: {
        code: "oauth_expired",
        message: "OAuth token expired. Please reconnect.",
        canAutoReconnect: true,
      },
    },
  },
  {
    ...PLATFORM_REGISTRY[1],
    status: "syncing",
    connectionDetails: {
      connectedAt: minutesAgo(3),
      lastSyncAt: minutesAgo(3),
      accountId: "act_987654321",
      accountName: "Acme Marketing",
      syncProgress: {
        percentage: 60,
        statusText: "Synchronizing campaign data\u2026",
      },
    },
  },
  {
    ...PLATFORM_REGISTRY[2],
    status: "connected",
    connectionDetails: {
      connectedAt: daysAgo(60),
      lastSyncAt: minutesAgo(5),
      accountId: "li_555888",
      accountName: "Acme B2B",
    },
  },
  {
    ...PLATFORM_REGISTRY[3],
    status: "error",
    connectionDetails: {
      connectedAt: daysAgo(20),
      lastSyncAt: hoursAgo(1),
      accountId: "tt_112233",
      accountName: "Acme TikTok",
      error: {
        code: "api_limit_exceeded",
        message: "API Limit Exceeded. Check platform settings.",
        canAutoReconnect: false,
      },
    },
  },
  {
    ...PLATFORM_REGISTRY[4],
    status: "connected",
    connectionDetails: {
      connectedAt: daysAgo(90),
      lastSyncAt: minutesAgo(10),
      accountId: "hs_44556",
      accountName: "Acme HubSpot",
    },
  },
  {
    ...PLATFORM_REGISTRY[5],
    status: "connected",
    connectionDetails: {
      connectedAt: daysAgo(120),
      lastSyncAt: minutesAgo(15),
      accountId: "sf_778899",
      accountName: "Acme Salesforce",
    },
  },
];

const CRITICAL: Platform[] = [
  {
    ...PLATFORM_REGISTRY[0],
    status: "disconnected",
    connectionDetails: {
      connectedAt: daysAgo(45),
      lastSyncAt: daysAgo(3),
      accountId: "123-456-7890",
      accountName: "Acme Corp Main",
      error: {
        code: "oauth_expired",
        message: "OAuth token expired. Please reconnect to resume data syncing.",
        canAutoReconnect: true,
      },
    },
  },
  {
    ...PLATFORM_REGISTRY[1],
    status: "error",
    connectionDetails: {
      connectedAt: daysAgo(30),
      lastSyncAt: daysAgo(1),
      accountId: "act_987654321",
      accountName: "Acme Marketing",
      error: {
        code: "insufficient_permissions",
        message: "Insufficient permissions. Re-authorize with admin access.",
        canAutoReconnect: true,
      },
    },
  },
  {
    ...PLATFORM_REGISTRY[2],
    status: "error",
    connectionDetails: {
      connectedAt: daysAgo(60),
      lastSyncAt: daysAgo(2),
      accountId: "li_555888",
      accountName: "Acme B2B",
      error: {
        code: "api_outage",
        message: "LinkedIn API is currently experiencing an outage.",
        canAutoReconnect: false,
      },
    },
  },
  {
    ...PLATFORM_REGISTRY[3],
    status: "error",
    connectionDetails: {
      connectedAt: daysAgo(20),
      lastSyncAt: hoursAgo(6),
      accountId: "tt_112233",
      accountName: "Acme TikTok",
      error: {
        code: "api_limit_exceeded",
        message: "API Limit Exceeded. Check platform settings.",
        canAutoReconnect: false,
      },
    },
  },
  {
    ...PLATFORM_REGISTRY[4],
    status: "disconnected",
    connectionDetails: {
      connectedAt: daysAgo(90),
      lastSyncAt: daysAgo(5),
      accountId: "hs_44556",
      accountName: "Acme HubSpot",
      error: {
        code: "oauth_expired",
        message: "HubSpot connection expired. Reconnect to continue syncing.",
        canAutoReconnect: true,
      },
    },
  },
  {
    ...PLATFORM_REGISTRY[5],
    status: "syncing",
    connectionDetails: {
      connectedAt: minutesAgo(2),
      lastSyncAt: minutesAgo(2),
      accountId: "sf_778899",
      accountName: "Acme Salesforce",
      syncProgress: {
        percentage: 25,
        statusText: "Importing opportunity records\u2026",
      },
    },
  },
];

const SCENARIO_MAP: Record<PlatformIntegrationsScenario, Platform[]> = {
  all_healthy: ALL_HEALTHY,
  mixed: MIXED,
  critical: CRITICAL,
};

export interface FetchPlatformIntegrationsOptions {
  scenario: PlatformIntegrationsScenario;
  delayMs?: number;
}

export async function fetchPlatformIntegrationsMock(
  options: FetchPlatformIntegrationsOptions
): Promise<PlatformIntegrationsData> {
  const { scenario, delayMs = 250 } = options;
  await new Promise((resolve) => setTimeout(resolve, delayMs));
  return { platforms: SCENARIO_MAP[scenario] };
}
