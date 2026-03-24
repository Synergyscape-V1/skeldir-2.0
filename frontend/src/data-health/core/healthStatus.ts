import type { HealthStatus, MetricStatus } from "./types";

export const computeHealthStatus = (score: number): HealthStatus => {
  if (score >= 90) return "healthy";
  if (score >= 70) return "warning";
  return "critical";
};

export const computeMetricStatus = (value: number, target: number): MetricStatus => {
  const percentOfTarget = value / target;
  if (percentOfTarget >= 0.95) return "good";
  if (percentOfTarget >= 0.8) return "warning";
  return "critical";
};

export const computeOverallScore = (
  trackingCoverage: number,
  utmConsistency: number,
  revenueMatchRate: number
): number => Math.round(trackingCoverage * 0.4 + utmConsistency * 0.3 + revenueMatchRate * 0.3);
