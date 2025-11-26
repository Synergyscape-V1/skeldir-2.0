import { useState, useEffect, useCallback, useRef } from 'react';

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

export interface VerificationUpdate {
  // Previous state
  previousVerified: number;
  previousUnverified: number;
  previousConfidence: number;
  
  // New state
  newVerified: number;
  newUnverified: number;
  newConfidence: number;
  
  // Metadata
  transactionsVerified: number;
  platformsAffected: string[]; // ["stripe", "shopify"]
  timestamp: string; // ISO 8601
}

export interface VerificationSyncState {
  isAnimating: boolean;
  highlightedComponent: 'verified' | 'unverified' | 'confidence' | null;
  currentUpdate: VerificationUpdate | null;
}

// ============================================================================
// MAIN HOOK
// ============================================================================

export const useVerificationSync = () => {
  const [syncState, setSyncState] = useState<VerificationSyncState>({
    isAnimating: false,
    highlightedComponent: null,
    currentUpdate: null,
  });

  const animationTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // ============================================================================
  // ANIMATION ORCHESTRATION
  // ============================================================================

  const triggerVerificationUpdate = useCallback((update: VerificationUpdate) => {
    // Clear any existing animation
    if (animationTimeoutRef.current) {
      clearTimeout(animationTimeoutRef.current);
    }

    setSyncState({
      isAnimating: true,
      highlightedComponent: 'verified',
      currentUpdate: update,
    });

    // Step 1: Highlight verified revenue (0-300ms)
    setTimeout(() => {
      setSyncState(prev => ({
        ...prev,
        highlightedComponent: 'unverified',
      }));
    }, 300);

    // Step 2: Highlight unverified revenue (300-600ms)
    setTimeout(() => {
      setSyncState(prev => ({
        ...prev,
        highlightedComponent: 'confidence',
      }));
    }, 600);

    // Step 3: Highlight confidence bar (600-900ms)
    setTimeout(() => {
      setSyncState(prev => ({
        ...prev,
        highlightedComponent: null,
      }));
    }, 900);

    // Step 4: Clear animation state (1200ms)
    animationTimeoutRef.current = setTimeout(() => {
      setSyncState({
        isAnimating: false,
        highlightedComponent: null,
        currentUpdate: null,
      });
    }, 1200);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (animationTimeoutRef.current) {
        clearTimeout(animationTimeoutRef.current);
      }
    };
  }, []);

  return {
    syncState,
    triggerVerificationUpdate,
    isAnimating: syncState.isAnimating,
    highlightedComponent: syncState.highlightedComponent,
    currentUpdate: syncState.currentUpdate,
  };
};
