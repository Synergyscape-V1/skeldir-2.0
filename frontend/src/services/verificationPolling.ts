import { VerificationUpdate } from '../hooks/useVerificationSync';

// ============================================================================
// POLLING SERVICE (Fallback for WebSocket)
// ============================================================================

export class VerificationPollingService {
  private intervalId: NodeJS.Timeout | null = null;
  private listeners: Array<(update: VerificationUpdate) => void> = [];
  private lastUpdateTimestamp: string | null = null;
  private pollingInterval = 5000; // 5 seconds (FE-UX-021 real-time SLA)

  constructor(
    private apiUrl: string,
    private interval: number = 5000
  ) {
    this.pollingInterval = interval;
  }

  // ============================================================================
  // POLLING MANAGEMENT
  // ============================================================================

  start(): void {
    if (this.intervalId) {
      console.warn('[VerificationPolling] Already running');
      return;
    }

    console.log(`[VerificationPolling] Started (interval: ${this.pollingInterval}ms)`);
    
    // Initial fetch
    this.fetchUpdates();
    
    // Set up interval
    this.intervalId = setInterval(() => {
      this.fetchUpdates();
    }, this.pollingInterval);
  }

  private async fetchUpdates(): Promise<void> {
    try {
      const url = this.lastUpdateTimestamp
        ? `${this.apiUrl}?since=${encodeURIComponent(this.lastUpdateTimestamp)}`
        : this.apiUrl;

      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include', // Use cookies for auth in this stack
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      // Check if there's a new update
      if (data.hasUpdate && data.update) {
        const update = data.update as VerificationUpdate;
        this.lastUpdateTimestamp = update.timestamp;
        this.notifyListeners(update);
      }
    } catch (error) {
      console.error('[VerificationPolling] Fetch failed:', error);
    }
  }

  // ============================================================================
  // SUBSCRIPTION MANAGEMENT
  // ============================================================================

  subscribe(callback: (update: VerificationUpdate) => void): () => void {
    this.listeners.push(callback);
    
    return () => {
      this.listeners = this.listeners.filter(listener => listener !== callback);
    };
  }

  private notifyListeners(update: VerificationUpdate): void {
    this.listeners.forEach(listener => listener(update));
  }

  // ============================================================================
  // CLEANUP
  // ============================================================================

  stop(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
      console.log('[VerificationPolling] Stopped');
    }
    this.listeners = [];
  }
}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

// Use Vite environment variables (VITE_ prefix)
const API_URL = (import.meta.env.VITE_API_URL || '/api') + '/verification/status';
export const verificationPolling = new VerificationPollingService(API_URL, 5000);
