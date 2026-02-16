import { useEffect, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import './ConfidenceScoreBadge.css';
import type { Tier } from './ConfidenceScoreBadge';

/**
 * ConfidenceTooltip renders a positioned tooltip with tier-specific messages.
 * 
 * Features:
 * - Intelligent viewport collision detection
 * - Fallback positioning (above/below, left/right/center align)
 * - React Portal rendering for proper z-index layering
 * - Dynamic arrow positioning based on badge location
 * - Cursor clearance enforcement (16-24px buffer)
 * - State guards to prevent oscillation loops
 * - Locked positioning during active lifecycle
 * 
 * This is a sub-component of ConfidenceScoreBadge and should not be used standalone.
 */

interface Position {
  top: number;
  left: number;
  placement: 'above' | 'below';
  align: 'center' | 'left' | 'right';
}

interface ConfidenceTooltipProps {
  tier: Tier;
  score: number;
  visible: boolean;
  badgeRef: React.RefObject<HTMLDivElement>;
  tooltipId: string;
}

const getTooltipMessage = (tier: Tier, score: number): string => {
  const messages: Record<Tier, string> = {
    high: `High confidence (${score}%, ≥70%). Attribution model shows strong statistical significance.`,
    medium: `Medium confidence (${score}%, 30-69%). Model indicates moderate correlation strength.`,
    low: `Low confidence (${score}%, <30%). Limited data or weak statistical patterns detected.`,
  };
  return messages[tier];
};

export default function ConfidenceTooltip({ tier, score, visible, badgeRef, tooltipId }: ConfidenceTooltipProps) {
  const [position, setPosition] = useState<Position>({ top: -9999, left: -9999, placement: 'above', align: 'center' });
  const [isPositioned, setIsPositioned] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const isVisibleRef = useRef(false);
  const isScrollingRef = useRef(false);
  const scrollTimeoutRef = useRef<number>();

  useEffect(() => {
    if (!visible || !badgeRef.current || !tooltipRef.current) {
      isVisibleRef.current = false;
      setIsPositioned(false);
      return;
    }

    // State guard: only calculate position once when tooltip becomes visible
    if (isVisibleRef.current) {
      return;
    }

    isVisibleRef.current = true;

    const calculatePosition = () => {
      const badge = badgeRef.current?.getBoundingClientRect();
      const tooltip = tooltipRef.current?.getBoundingClientRect();
      
      if (!badge || !tooltip) return;

      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      const CURSOR_CLEARANCE = 20; // 16-24px buffer zone to prevent cursor overlap
      const gap = 10;

      // Default: position above with cursor clearance
      let top = badge.top - tooltip.height - gap - CURSOR_CLEARANCE;
      let left = badge.left + badge.width / 2 - tooltip.width / 2;
      let placement: 'above' | 'below' = 'above';
      let align: 'center' | 'left' | 'right' = 'center';

      // Collision detection: switch to below if insufficient space above
      if (top < 20) {
        top = badge.bottom + gap + CURSOR_CLEARANCE;
        placement = 'below';
      }

      // Horizontal collision detection with cursor clearance
      const MIN_EDGE_PADDING = 20 + CURSOR_CLEARANCE;
      if (left < MIN_EDGE_PADDING) {
        left = MIN_EDGE_PADDING;
        align = 'left';
      } else if (left + tooltip.width > viewportWidth - MIN_EDGE_PADDING) {
        left = viewportWidth - tooltip.width - MIN_EDGE_PADDING;
        align = 'right';
      }

      setPosition({ top, left, placement, align });
      setIsPositioned(true);
    };

    requestAnimationFrame(() => {
      calculatePosition();
    });

    // Only allow repositioning during scroll events
    const handleScroll = () => {
      if (!isVisibleRef.current) return;
      
      isScrollingRef.current = true;
      if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current);
      
      // Recalculate position during scroll
      requestAnimationFrame(() => {
        const badge = badgeRef.current?.getBoundingClientRect();
        const tooltip = tooltipRef.current?.getBoundingClientRect();
        
        if (!badge || !tooltip) return;

        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const CURSOR_CLEARANCE = 20;
        const gap = 10;

        let top = badge.top - tooltip.height - gap - CURSOR_CLEARANCE;
        let left = badge.left + badge.width / 2 - tooltip.width / 2;
        let placement: 'above' | 'below' = 'above';
        let align: 'center' | 'left' | 'right' = 'center';

        if (top < 20) {
          top = badge.bottom + gap + CURSOR_CLEARANCE;
          placement = 'below';
        }

        const MIN_EDGE_PADDING = 20 + CURSOR_CLEARANCE;
        if (left < MIN_EDGE_PADDING) {
          left = MIN_EDGE_PADDING;
          align = 'left';
        } else if (left + tooltip.width > viewportWidth - MIN_EDGE_PADDING) {
          left = viewportWidth - tooltip.width - MIN_EDGE_PADDING;
          align = 'right';
        }

        setPosition({ top, left, placement, align });
      });
      
      // Mark scrolling as ended after 150ms
      scrollTimeoutRef.current = window.setTimeout(() => {
        isScrollingRef.current = false;
      }, 150);
    };

    // Disable resize repositioning - only scroll events trigger recalculation
    window.addEventListener('scroll', handleScroll, true);

    return () => {
      window.removeEventListener('scroll', handleScroll, true);
      if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current);
    };
  }, [visible, badgeRef, tier]);

  // Clean up refs when tooltip becomes invisible
  useEffect(() => {
    if (!visible) {
      isVisibleRef.current = false;
      setIsPositioned(false);
    }
  }, [visible]);

  if (!visible) return null;

  const arrowLeft = badgeRef.current 
    ? badgeRef.current.getBoundingClientRect().left + badgeRef.current.getBoundingClientRect().width / 2 - position.left - 6
    : 0;

  return createPortal(
    <div
      ref={tooltipRef}
      id={tooltipId}
      role="tooltip"
      className="confidence-tooltip fixed px-4 py-3 rounded-lg max-w-[280px] pointer-events-none bg-gray-800 text-white text-sm shadow-lg"
      style={{
        top: `${position.top}px`,
        left: `${position.left}px`,
        zIndex: 9999,
        lineHeight: 1.6,
        opacity: isPositioned ? 1 : 0,
      }}
      data-testid="confidence-tooltip"
      data-tooltip-tier={tier}
    >
      {getTooltipMessage(tier, score)}
      <div
        className="absolute border-l-[6px] border-r-[6px] border-l-transparent border-r-transparent"
        style={{
          left: `${arrowLeft}px`,
          [position.placement === 'above' ? 'bottom' : 'top']: '-6px',
          [position.placement === 'above' ? 'borderTopWidth' : 'borderBottomWidth']: '6px',
          [position.placement === 'above' ? 'borderTopColor' : 'borderBottomColor']: 'rgb(31, 41, 55)', // gray-800
        }}
      />
    </div>,
    document.body
  );
}
