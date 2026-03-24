import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchDataHealthMock } from "./mockApi";
import { getDataHealthState } from "./stateMachine";
import type { DataHealthData, DataHealthScenario, DataHealthState, DataHealthUiState } from "./types";

export interface UseDataHealthDataOptions {
  scenario?: DataHealthScenario;
  uiState?: DataHealthUiState;
  stale?: boolean;
}

export interface UseDataHealthDataReturn {
  data: DataHealthData | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  state: DataHealthState;
}

export const useDataHealthData = ({
  scenario = "warning",
  uiState = "steady",
  stale = false,
}: UseDataHealthDataOptions = {}): UseDataHealthDataReturn => {
  const [data, setData] = useState<DataHealthData | null>(null);
  const [loading, setLoading] = useState(uiState === "initial_loading");
  const [error, setError] = useState<Error | null>(uiState === "error" ? new Error("Unable to load data health metrics. Please try again.") : null);

  const fetchData = useCallback(async () => {
    if (uiState === "initial_loading") {
      setLoading(true);
      setError(null);
      const result = await fetchDataHealthMock({ scenario, stale, delayMs: 500 });
      setData(result);
      setLoading(false);
      return;
    }

    if (uiState === "error") {
      setLoading(false);
      setData(null);
      setError(new Error("Unable to load data health metrics. Please try again."));
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
      const result = await fetchDataHealthMock({ scenario, stale, delayMs: 250 });
      setData(result);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError : new Error("Failed to load data health."));
    } finally {
      setLoading(false);
    }
  }, [scenario, stale, uiState]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const state = useMemo(() => getDataHealthState(loading, data, error), [loading, data, error]);

  return { data, loading, error, refetch: fetchData, state };
};
