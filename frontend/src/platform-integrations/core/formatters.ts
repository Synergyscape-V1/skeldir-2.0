export { formatRelativeTime } from "../../data-health/core/formatters";

export type StalenessLevel = "fresh" | "stale" | "critical";

export function getStalenessLevel(lastSyncAt: Date): StalenessLevel {
  const diffMs = Date.now() - lastSyncAt.getTime();
  const thirtyMinutes = 30 * 60_000;
  const twentyFourHours = 24 * 3_600_000;

  if (diffMs < thirtyMinutes) return "fresh";
  if (diffMs < twentyFourHours) return "stale";
  return "critical";
}
