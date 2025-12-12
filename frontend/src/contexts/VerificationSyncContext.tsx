import { createContext, useContext, useEffect, ReactNode, useCallback, useState } from 'react';
import { useVerificationSync, VerificationUpdate } from '@/hooks/useVerificationSync';
import { verificationWebSocket } from '@/services/verificationWebSocket';
import { verificationPolling } from '@/services/verificationPolling';

// ============================================================================
// CONTEXT TYPE
// ============================================================================

interface VerificationSyncContextType {
  isAnimating: boolean;
  highlightedComponent: 'verified' | 'unverified' | 'confidence' | null;
  currentUpdate: VerificationUpdate | null;
  triggerVerificationUpdate: (update: VerificationUpdate) => void;
}

// ============================================================================
// CONTEXT CREATION
// ============================================================================

const VerificationSyncContext = createContext<VerificationSyncContextType | undefined>(undefined);

// ============================================================================
// PROVIDER COMPONENT
// ============================================================================

interface VerificationSyncProviderProps {
  children: ReactNode;
  useWebSocket?: boolean;
}

export const VerificationSyncProvider = ({ 
  children, 
  useWebSocket = true 
}: VerificationSyncProviderProps) => {
  const { 
    syncState, 
    triggerVerificationUpdate, 
    isAnimating, 
    highlightedComponent, 
    currentUpdate 
  } = useVerificationSync();

  const [toastQueue, setToastQueue] = useState<VerificationUpdate[]>([]);

  // Handle incoming verification updates
  const handleVerificationUpdate = useCallback((update: VerificationUpdate) => {
    triggerVerificationUpdate(update);
    
    // Add to toast queue (will be shown after animation starts)
    setToastQueue(prev => [...prev, update]);
    
    // Remove from queue after toast duration (4 seconds + animation delay)
    setTimeout(() => {
      setToastQueue(prev => prev.filter(u => u !== update));
    }, 4400);
  }, [triggerVerificationUpdate]);

  // Set up WebSocket or Polling based on configuration
  // B0.2: Mock mode forces polling to prevent production WebSocket traffic
  useEffect(() => {
    const isMockMode = import.meta.env.VITE_MOCK_MODE === 'true';
    const useWS = !isMockMode && useWebSocket && import.meta.env.VITE_USE_WEBSOCKET !== 'false';

    if (useWS) {
      console.log('[VerificationSync] Using WebSocket mode');
      verificationWebSocket.connect();
      const unsubscribe = verificationWebSocket.subscribe(handleVerificationUpdate);
      
      return () => {
        unsubscribe();
        verificationWebSocket.disconnect();
      };
    } else {
      console.log('[VerificationSync] Using Polling mode (mock mode:', isMockMode, ')');
      verificationPolling.start();
      const unsubscribe = verificationPolling.subscribe(handleVerificationUpdate);
      
      return () => {
        unsubscribe();
        verificationPolling.stop();
      };
    }
  }, [useWebSocket, handleVerificationUpdate]);

  const value: VerificationSyncContextType = {
    isAnimating,
    highlightedComponent,
    currentUpdate,
    triggerVerificationUpdate,
  };

  return (
    <VerificationSyncContext.Provider value={value}>
      {children}
    </VerificationSyncContext.Provider>
  );
};

// ============================================================================
// HOOK TO USE CONTEXT
// ============================================================================

export const useVerificationSyncContext = () => {
  const context = useContext(VerificationSyncContext);
  if (context === undefined) {
    throw new Error('useVerificationSyncContext must be used within a VerificationSyncProvider');
  }
  return context;
};
