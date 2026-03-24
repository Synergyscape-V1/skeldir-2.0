import type { DataHealthData, DataHealthState } from "./types";

export const isStaleData = (lastUpdated: Date): boolean => {
  const now = Date.now();
  const ageMs = now - lastUpdated.getTime();
  return ageMs > 24 * 60 * 60 * 1000;
};

export const getDataHealthState = (
  loading: boolean,
  data: DataHealthData | null,
  error: Error | null
): DataHealthState => {
  if (loading && data === null) return { type: "initial_loading" };
  if (error) return { type: "error", error };
  if (data === null) return { type: "no_data" };
  return { type: "steady", data, stale: isStaleData(data.lastUpdated) };
};
