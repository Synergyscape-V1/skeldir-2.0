import { useState, useCallback } from 'react';

/**
 * FE-UX-033: Custom hook for managing component elevation states
 * Provides programmatic control over elevation levels with smooth transitions
 * Based on Material Design 3 elevation principles
 */

export type ElevationLevel = 0 | 1 | 2 | 3 | 4 | 5 | 'verified' | 'unverified' | 'alert';

export interface UseElevationOptions {
  baseLevel: ElevationLevel;
  hoverLevel?: ElevationLevel;
  activeLevel?: ElevationLevel;
  transitionDuration?: number;
}

export interface UseElevationReturn {
  currentLevel: ElevationLevel;
  elevationClass: string;
  transitionClass: string;
  handlers: {
    onMouseEnter: () => void;
    onMouseLeave: () => void;
    onMouseDown: () => void;
    onMouseUp: () => void;
  };
  setElevation: (level: ElevationLevel) => void;
}

export const useElevation = ({
  baseLevel,
  hoverLevel,
  activeLevel,
  transitionDuration = 200,
}: UseElevationOptions): UseElevationReturn => {
  const [currentLevel, setCurrentLevel] = useState<ElevationLevel>(baseLevel);
  const [isHovered, setIsHovered] = useState(false);
  const [isActive, setIsActive] = useState(false);

  // Determine which level to display
  const getDisplayLevel = useCallback((): ElevationLevel => {
    if (isActive && activeLevel !== undefined) return activeLevel;
    if (isHovered && hoverLevel !== undefined) return hoverLevel;
    return currentLevel;
  }, [currentLevel, hoverLevel, activeLevel, isHovered, isActive]);

  // Generate elevation class name
  const getElevationClass = (level: ElevationLevel): string => {
    if (typeof level === 'string') {
      return `elevation-${level}`;
    }
    return `elevation-${level}`;
  };

  // Event handlers
  const handleMouseEnter = useCallback(() => {
    setIsHovered(true);
  }, []);

  const handleMouseLeave = useCallback(() => {
    setIsHovered(false);
    setIsActive(false);
  }, []);

  const handleMouseDown = useCallback(() => {
    setIsActive(true);
  }, []);

  const handleMouseUp = useCallback(() => {
    setIsActive(false);
  }, []);

  const displayLevel = getDisplayLevel();

  return {
    currentLevel: displayLevel,
    elevationClass: getElevationClass(displayLevel),
    transitionClass: 'elevation-transition',
    handlers: {
      onMouseEnter: handleMouseEnter,
      onMouseLeave: handleMouseLeave,
      onMouseDown: handleMouseDown,
      onMouseUp: handleMouseUp,
    },
    setElevation: setCurrentLevel,
  };
};
