import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchPlatformIntegrationsMock } from "./mockData";
import type {
  PlatformIntegrationsData,
  PlatformIntegrationsScenario,
  PlatformIntegrationsState,
  PlatformIntegrationsUiState,
} from "./types";

export interface UsePlatformIntegrationsDataOptions {
  scenario?: PlatformIntegrationsScenario;
  uiState?: PlatformIntegrationsUiState;
}

export interface UsePlatformIntegrationsDataReturn {
  data: PlatformIntegrationsData | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  state: PlatformIntegrationsState;
}

function getState(
  loading: boolean,
  data: PlatformIntegrationsData | null,
  error: Error | null
): PlatformIntegrationsState {
  if (loading && data === null) return { type: "initial_loading" };
  if (error) return { type: "error", error };
  if (data === null) return { type: "no_data" };
  return { type: "steady", data };
}

export const usePlatformIntegrationsData = ({
  scenario = "mixed",
  uiState = "steady",
}: UsePlatformIntegrationsDataOptions = {}): UsePlatformIntegrationsDataReturn => {
  const [data, setData] = useState<PlatformIntegrationsData | null>(null);
  const [loading, setLoading] = useState(uiState === "initial_loading");
  const [error, setError] = useState<Error | null>(
    uiState === "error"
      ? new Error("Unable to load platform integrations. Please try again.")
      : null
  );

  const fetchData = useCallback(async () => {
    if (uiState === "initial_loading") {
      setLoading(true);
      setError(null);
      const result = await fetchPlatformIntegrationsMock({ scenario, delayMs: 500 });
      setData(result);
      setLoading(false);
      return;
    }

    if (uiState === "error") {
      setLoading(false);
      setData(null);
      setError(new Error("Unable to load platform integrations. Please try again."));
      return;
    }

    if (uiState === "no_data") {
      setLoading(false);
      setError(null);
      setData(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await fetchPlatformIntegrationsMock({ scenario, delayMs: 250 });
      setData(result);
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError
          : new Error("Failed to load platform integrations.")
      );
    } finally {
      setLoading(false);
    }
  }, [scenario, uiState]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const state = useMemo(() => getState(loading, data, error), [loading, data, error]);

  return { data, loading, error, refetch: fetchData, state };
};
