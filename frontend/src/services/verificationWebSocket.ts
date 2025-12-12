import { VerificationUpdate } from '../hooks/useVerificationSync';

// ============================================================================
// WEBSOCKET SERVICE
// ============================================================================

export class VerificationWebSocketService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 3000;
  private listeners: Array<(update: VerificationUpdate) => void> = [];

  constructor(private url: string) {}

  // ============================================================================
  // CONNECTION MANAGEMENT
  // ============================================================================

  connect(): void {
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('[VerificationWS] Connected');
        this.reconnectAttempts = 0;
      };

      this.ws.onmessage = (event) => {
        try {
          const update = JSON.parse(event.data) as VerificationUpdate;
          this.notifyListeners(update);
        } catch (error) {
          console.error('[VerificationWS] Failed to parse message:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('[VerificationWS] WebSocket error:', error);
      };

      this.ws.onclose = () => {
        console.log('[VerificationWS] Disconnected');
        this.attemptReconnect();
      };
    } catch (error) {
      console.error('[VerificationWS] Connection failed:', error);
      this.attemptReconnect();
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      
      // Exponential backoff: base delay * 2^attempt, capped at 30 seconds
      const exponentialDelay = Math.min(
        this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
        30000
      );
      
      console.log(
        `[VerificationWS] Reconnecting... Attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} (delay: ${exponentialDelay}ms)`
      );
      
      setTimeout(() => this.connect(), exponentialDelay);
    } else {
      console.error('[VerificationWS] Max reconnection attempts reached');
    }
  }

  // ============================================================================
  // SUBSCRIPTION MANAGEMENT
  // ============================================================================

  subscribe(callback: (update: VerificationUpdate) => void): () => void {
    this.listeners.push(callback);
    
    // Return unsubscribe function
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

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.listeners = [];
  }
}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

// Use Vite environment variables (VITE_ prefix)
const WS_URL = import.meta.env.VITE_WS_URL || 'wss://api.skeldir.com/verification-updates';

/**
 * B0.2: Mock mode guard - disable WebSocket in mock environments
 * When VITE_MOCK_MODE=true, we create a no-op service that doesn't connect
 */
const isMockMode = import.meta.env.VITE_MOCK_MODE === 'true';

class MockVerificationWebSocketService {
  connect(): void {
    console.log('[VerificationWS] Mock mode enabled - WebSocket connection disabled');
  }
  subscribe(_callback: (update: VerificationUpdate) => void): () => void {
    return () => {};
  }
  disconnect(): void {}
}

export const verificationWebSocket = isMockMode 
  ? new MockVerificationWebSocketService() 
  : new VerificationWebSocketService(WS_URL);
