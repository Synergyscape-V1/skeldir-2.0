export type PlatformStatus = "connected" | "disconnected" | "syncing" | "error";

export interface ConnectionError {
  code: string;
  message: string;
  canAutoReconnect: boolean;
}

export interface SyncProgress {
  percentage: number;
  statusText: string;
}

export interface ConnectionDetails {
  connectedAt: Date;
  lastSyncAt: Date;
  accountId?: string;
  accountName?: string;
  error?: ConnectionError;
  syncProgress?: SyncProgress;
}

export interface Platform {
  id: string;
  name: string;
  description: string;
  iconUrl: string;
  status: PlatformStatus;
  connectionDetails?: ConnectionDetails;
}

export interface PlatformIntegrationsData {
  platforms: Platform[];
}

export type PlatformIntegrationsState =
  | { type: "initial_loading" }
  | { type: "error"; error: Error }
  | { type: "no_data" }
  | { type: "steady"; data: PlatformIntegrationsData };

export type PlatformIntegrationsScenario = "all_healthy" | "mixed" | "critical";

export type PlatformIntegrationsUiState = "initial_loading" | "error" | "no_data" | "steady";

export interface PlatformIntegrationsRendererProps {
  state: PlatformIntegrationsState;
  scenario: PlatformIntegrationsScenario;
  onConnect: (platformId: string) => void;
  onReconnect: (platformId: string) => void;
  onDisconnect: (platformId: string) => void;
  onConfigure: (platformId: string) => void;
  onRetry: () => Promise<void> | void;
}
