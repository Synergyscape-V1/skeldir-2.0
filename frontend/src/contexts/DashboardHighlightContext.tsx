/**
 * DashboardHighlightContext - Cross-Component Hover Highlighting System
 * 
 * FE-UX-020: Implements bidirectional visual associations between Revenue Overview
 * and Data Integrity Monitor components.
 * 
 * When a user hovers over a platform card in Data Integrity Monitor, the corresponding
 * Revenue Overview card (verified or unverified) highlights with a colored glow.
 * Similarly, hovering over Revenue Overview highlights all related platform cards.
 * 
 * Architecture Decision: React Context API chosen over Redux/Zustand because:
 * - Lightweight solution for single hover state
 * - No prop drilling needed
 * - Type-safe and React-native
 * - Minimal overhead for this specific use case
 */

import { createContext, useContext, useState, ReactNode } from 'react';

/**
 * Highlight state type definition
 * - 'verified': User is hovering over verified revenue elements
 * - 'unverified': User is hovering over unverified revenue elements
 * - 'platform-{id}': User is hovering over a specific platform card
 * - null: No active hover state
 */
type HighlightState = 'verified' | 'unverified' | `platform-${string}` | null;

interface DashboardHighlightContextValue {
  /** Current active highlight state */
  highlightedElement: HighlightState;
  
  /** Set the current highlight state */
  setHighlight: (element: HighlightState) => void;
  
  /** Clear all highlights (convenience method) */
  clearHighlight: () => void;
  
  /** Check if a specific element should be highlighted */
  isHighlighted: (element: HighlightState) => boolean;
  
  /** Check if verified category should be highlighted */
  isVerifiedHighlighted: () => boolean;
  
  /** Check if unverified category should be highlighted */
  isUnverifiedHighlighted: () => boolean;
}

const DashboardHighlightContext = createContext<DashboardHighlightContextValue | undefined>(
  undefined
);

/**
 * Provider component for dashboard hover highlighting
 * Wrap the entire dashboard layout with this provider
 */
export function DashboardHighlightProvider({ children }: { children: ReactNode }) {
  const [highlightedElement, setHighlightedElement] = useState<HighlightState>(null);

  const setHighlight = (element: HighlightState) => {
    setHighlightedElement(element);
  };

  const clearHighlight = () => {
    setHighlightedElement(null);
  };

  const isHighlighted = (element: HighlightState): boolean => {
    return highlightedElement === element;
  };

  const isVerifiedHighlighted = (): boolean => {
    // Highlight verified if user hovers verified overview OR any verified platform
    return (
      highlightedElement === 'verified' ||
      (typeof highlightedElement === 'string' && highlightedElement.startsWith('platform-verified-'))
    );
  };

  const isUnverifiedHighlighted = (): boolean => {
    // Highlight unverified if user hovers unverified overview OR any unverified platform
    return (
      highlightedElement === 'unverified' ||
      (typeof highlightedElement === 'string' && 
       highlightedElement.startsWith('platform-') && 
       !highlightedElement.includes('verified'))
    );
  };

  const value: DashboardHighlightContextValue = {
    highlightedElement,
    setHighlight,
    clearHighlight,
    isHighlighted,
    isVerifiedHighlighted,
    isUnverifiedHighlighted,
  };

  return (
    <DashboardHighlightContext.Provider value={value}>
      {children}
    </DashboardHighlightContext.Provider>
  );
}

/**
 * Custom hook to access dashboard highlight context
 * Must be used within DashboardHighlightProvider
 */
export function useDashboardHighlight(): DashboardHighlightContextValue {
  const context = useContext(DashboardHighlightContext);
  
  if (!context) {
    throw new Error(
      'useDashboardHighlight must be used within a DashboardHighlightProvider. ' +
      'Wrap your dashboard components with <DashboardHighlightProvider>.'
    );
  }
  
  return context;
}

/**
 * Type guard for platform highlight states
 */
export function isPlatformHighlight(state: HighlightState): state is `platform-${string}` {
  return typeof state === 'string' && state.startsWith('platform-');
}
