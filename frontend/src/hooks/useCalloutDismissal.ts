import { useState, useCallback } from 'react';

interface UseCalloutDismissalReturn {
  isVisible: boolean;
  dismiss: () => void;
  reset: () => void;
}

/**
 * Custom hook for managing callout dismissal state with localStorage persistence
 * @param storageKey - Unique key for localStorage
 * @param defaultVisible - Default visibility state (default: true)
 * @returns Object with visibility state and control functions
 */
export const useCalloutDismissal = (
  storageKey: string,
  defaultVisible: boolean = true
): UseCalloutDismissalReturn => {
  const [isVisible, setIsVisible] = useState<boolean>(() => {
    if (typeof window === 'undefined') return defaultVisible;
    
    try {
      const stored = localStorage.getItem(storageKey);
      return stored === 'true' ? false : defaultVisible;
    } catch (error) {
      console.warn('Failed to read from localStorage:', error);
      return defaultVisible;
    }
  });

  const dismiss = useCallback(() => {
    setIsVisible(false);
    
    try {
      localStorage.setItem(storageKey, 'true');
    } catch (error) {
      console.warn('Failed to save dismissal to localStorage:', error);
    }
  }, [storageKey]);

  const reset = useCallback(() => {
    setIsVisible(true);
    
    try {
      localStorage.removeItem(storageKey);
    } catch (error) {
      console.warn('Failed to remove from localStorage:', error);
    }
  }, [storageKey]);

  return { isVisible, dismiss, reset };
};
