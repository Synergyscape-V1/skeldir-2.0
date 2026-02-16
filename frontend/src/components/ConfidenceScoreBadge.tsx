import { useState, useEffect, useRef, useId } from 'react';
import ConfidenceTooltip from './ConfidenceTooltip';
import './ConfidenceScoreBadge.css';

/**
 * Tier level for confidence score visualization
 * - high: score >= 70 (Success Green)
 * - medium: 30 ≤ score < 70 (Warning Amber)
 * - low: score < 30 (Critical Red)
 */
export type Tier = 'high' | 'medium' | 'low';

/**
 * ConfidenceScoreBadge displays statistical confidence levels (0-100) 
 * with tier-based color coding and glass UI styling.
 * 
 * Features:
 * - Animated count-up from 0 to score value (600ms ease-out)
 * - Tier-based color indicators (high/medium/low)
 * - Glass UI with backdrop blur and pill shape
 * - Hover/focus tooltip with positioning intelligence
 * - High tier pulse animation for visual emphasis
 * - IntersectionObserver for performance optimization
 * - Full accessibility support (ARIA, keyboard, screen readers)
 * 
 * @param score - Confidence score (0-100). Values outside range are clamped.
 *   - High tier: >= 70 (Success Green - green-600)
 *   - Medium tier: 30-69 (Warning Amber - amber-500)
 *   - Low tier: < 30 (Critical Red - red-700)
 * @param className - Optional CSS classes for customization
 * 
 * @example
 * // High confidence score
 * <ConfidenceScoreBadge score={85} />
 * 
 * @example
 * // Medium confidence with custom styling
 * <ConfidenceScoreBadge score={65} className="ml-4" />
 * 
 * @example
 * // Handles invalid input gracefully
 * <ConfidenceScoreBadge score={null} /> // Renders "—"
 */
interface ConfidenceScoreBadgeProps {
  score: number;
  className?: string;
}

const getTier = (score: number): Tier => {
  if (score >= 70) return 'high';
  if (score >= 30) return 'medium';
  return 'low';
};

const getTierColor = (tier: Tier): string => {
  const colors = {
    high: 'var(--confidence-tier-high)',
    medium: 'var(--confidence-tier-medium)',
    low: 'var(--confidence-tier-low)',
  };
  return colors[tier];
};

const getTierRgb = (tier: Tier): string => {
  // RGB values for WCAG AA compliant tier colors
  // Light mode: darker shades for contrast, Dark mode: brighter shades
  const rgbValues = {
    high: '14, 133, 60',      // hsl(142, 76%, 28%) for light mode
    medium: '136, 92, 4',      // hsl(38, 95%, 28%) for light mode  
    low: '185, 28, 28',        // hsl(0, 84%, 40%) for light mode
  };
  return rgbValues[tier];
};

export default function ConfidenceScoreBadge({ score: rawScore, className = '' }: ConfidenceScoreBadgeProps) {
  const validScore = typeof rawScore === 'number' && !isNaN(rawScore) 
    ? Math.max(0, Math.min(100, rawScore))
    : null;

  const [displayValue, setDisplayValue] = useState(0);
  const [showTooltip, setShowTooltip] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);
  
  const badgeRef = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<number>();
  const rafRef = useRef<number>();
  const observerRef = useRef<IntersectionObserver>();
  const displayValueRef = useRef(0);
  const tooltipId = useId();

  const tier = validScore !== null ? getTier(validScore) : 'low';
  const tierColor = getTierColor(tier);
  const tierRgb = getTierRgb(tier);

  useEffect(() => {
    if (!badgeRef.current || validScore === null) return;

    observerRef.current = new IntersectionObserver(
      ([entry]) => setIsVisible(entry.isIntersecting),
      { threshold: 0.1 }
    );

    observerRef.current.observe(badgeRef.current);

    return () => observerRef.current?.disconnect();
  }, [validScore]);

  useEffect(() => {
    if (!isVisible || validScore === null) return;

    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }

    setIsAnimating(true);
    const startTime = performance.now();
    const duration = 600;
    const startValue = displayValueRef.current;

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easeOut = 1 - Math.pow(1 - progress, 3);
      
      const value = Math.floor(startValue + (validScore - startValue) * easeOut);
      displayValueRef.current = value;
      setDisplayValue(value);

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      } else {
        setIsAnimating(false);
      }
    };

    rafRef.current = requestAnimationFrame(animate);

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = undefined;
      }
    };
  }, [isVisible, validScore]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  const handleMouseEnter = (e: React.MouseEvent) => {
    if (import.meta.env.DEV) {
      console.log('[Tooltip] ENTER:', e.timeStamp, 'Badge tier:', tier, 'Target:', e.currentTarget);
    }
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = window.setTimeout(() => {
      if (import.meta.env.DEV) {
        console.log('[Tooltip] SHOW:', performance.now(), 'Badge tier:', tier);
      }
      setShowTooltip(true);
    }, 150);
  };

  const handleMouseLeave = (e: React.MouseEvent) => {
    if (import.meta.env.DEV) {
      console.log('[Tooltip] LEAVE:', e.timeStamp, 'Badge tier:', tier, 'Target:', e.currentTarget);
    }
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = window.setTimeout(() => {
      if (import.meta.env.DEV) {
        console.log('[Tooltip] HIDE:', performance.now(), 'Badge tier:', tier);
      }
      setShowTooltip(false);
    }, 200);
  };

  const handleFocus = () => setShowTooltip(true);
  const handleBlur = () => setShowTooltip(false);
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') setShowTooltip(false);
  };

  if (validScore === null) {
    return <span className="text-sm text-muted-foreground">—</span>;
  }

  const ariaLive = isAnimating ? 'off' : 'polite';

  return (
    <>
      <div
        ref={badgeRef}
        className={`confidence-badge inline-flex items-center gap-2 px-3.5 py-1.5 rounded-[20px] border min-w-[80px] h-8 cursor-help ${className}`}
        // Justification: glass UI requires computed rgba() from tier-dependent RGB + D0 CSS vars; Tailwind cannot express runtime-computed backdrop/border/shadow from dynamic color components
        style={{
          backgroundColor: 'var(--confidence-badge-bg)',
          backdropFilter: 'blur(var(--confidence-badge-blur))',
          borderColor: `rgba(${tierRgb}, 0.3)`,
          boxShadow: `0 2px 12px rgba(${tierRgb}, 0.15)`,
          background: `linear-gradient(rgba(${tierRgb}, 0.12), rgba(${tierRgb}, 0.12)), var(--confidence-badge-bg)`,
        }}
        aria-label={`Confidence score: ${validScore}%, ${tier} confidence`}
        aria-describedby={showTooltip ? tooltipId : undefined}
        aria-live={ariaLive}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        tabIndex={0}
        data-testid={`confidence-badge-${tier}`}
        data-tier={tier}
        data-score={validScore}
      >
        <div
          className={`tier-dot ${tier === 'high' ? 'tier-dot-high' : ''} w-2 h-2 rounded-full`}
          // Justification: tier-dot color is tier-dependent (3 runtime variants from D0 CSS vars)
          style={{ backgroundColor: tierColor }}
          data-testid={`tier-dot-${tier}`}
        />
        <span
          className="confidence-percentage text-sm font-bold"
          // Justification: percentage color is tier-dependent (3 runtime variants from D0 CSS vars); letterSpacing is typography geometry
          style={{ color: tierColor, letterSpacing: '-0.5px' }}
          data-testid="confidence-percentage"
        >
          {displayValue}%
        </span>
      </div>
      <ConfidenceTooltip
        tier={tier}
        score={validScore}
        visible={showTooltip}
        badgeRef={badgeRef}
        tooltipId={tooltipId}
      />
    </>
  );
}
