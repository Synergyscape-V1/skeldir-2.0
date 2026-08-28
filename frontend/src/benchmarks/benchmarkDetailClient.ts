import type { BenchmarkRowDTO } from '../ledger/types';
import { BENCHMARKS_FIXTURES } from './benchmarksFixtures';

export interface BenchmarkDetailOutcome {
  kind: 'loaded' | 'not_found' | 'permission_denied' | 'network_error';
  detail?: BenchmarkRowDTO;
  message?: string;
}

export interface BenchmarkDetailClient {
  getBenchmarkDetail(tenantId: string, benchmarkId: string): Promise<BenchmarkDetailOutcome>;
}

let dataset = [...BENCHMARKS_FIXTURES];

export function setSyntheticBenchmarkDetailDataset(rows: BenchmarkRowDTO[]): void {
  dataset = [...rows];
}

export function createBenchmarkDetailClient(source = dataset): BenchmarkDetailClient {
  return {
    async getBenchmarkDetail(_tenantId, benchmarkId) {
      const detail = source.find((row) => row.benchmarkId === benchmarkId);
      if (!detail) {
        return { kind: 'not_found', message: 'Benchmark source details are unavailable.' };
      }
      return { kind: 'loaded', detail };
    },
  };
}

let defaultClient: BenchmarkDetailClient | null = null;

export function getDefaultBenchmarkDetailClient(): BenchmarkDetailClient {
  if (!defaultClient) defaultClient = createBenchmarkDetailClient();
  return defaultClient;
}

export function resetDefaultBenchmarkDetailClient(): void {
  defaultClient = null;
}
