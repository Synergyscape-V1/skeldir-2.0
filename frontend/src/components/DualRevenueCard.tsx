/**
 * DualRevenueCard Component
 * 
 * ARCHITECTURE DECISION: Monolithic Implementation (Option A)
 * Decision Date: October 2025
 * Rationale: Component implements self-contained dual revenue visualization with integrated
 * polling, animations, and state management in a single ~470-line file. Despite exceeding
 * the initial 150-200 line target, decomposition (Option B) was rejected because:
 * 1. High cohesion: All sub-components (ProgressRing, useAnimatedRevenue) are tightly
 *    coupled to DualRevenueCard's specific data contracts and animation timing
 * 2. Complexity isolation: Circuit breaker, exponential backoff, and stale data detection
 *    form an atomic reliability layer that benefits from co-location
 * 3. Performance: GPU-accelerated animations require coordinated timing across rings,
 *    bars, and count-ups that decomposition would fragment
 * 
 * RESPONSIVE BREAKPOINTS:
 * - Mobile: <768px (Tailwind default 'md' breakpoint)
 * - Desktop: ≥768px
 * Justification: Aligns with Skeldir design system's breakpoint strategy and ensures
 * layout transitions (horizontal ↔ vertical) occur at standard tablet/desktop boundary.
 * 768px chosen for consistency with existing dashboard components and industry standards.
 * 
 * NEGATIVE REVENUE HANDLING:
 * Decision: Display all values without rejection; rely on shared formatting utilities
 * Implementation: Component displays all revenue values as received, including negatives.
 * Shared currency formatting utilities automatically style negative values with red color
 * and minus sign. Component performs sum validation (verified + unverified = total ±0.5%)
 * and logs console warnings on mismatch, but does not block rendering or reject data.
 * Backend is responsible for business logic enforcement; UI provides observability through
 * validation logging and visual formatting.
 * Future: Add error boundaries if strict value constraints become required.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import type { CSSProperties } from 'react';
import { usePollingManager } from '@/hooks/use-polling-manager';
import RevenueDisplay from '@/components/RevenueDisplay';
import ConfidenceScoreBadge from '@/components/ConfidenceScoreBadge';
import { VerificationCheckmarkBadge, PendingVerificationIndicator } from '@/components/icons';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { TooltipAdvanced, TooltipAdvancedTrigger, TooltipAdvancedContent } from '@/components/ui/tooltip-advanced';
import { useDashboardHighlight } from '@/contexts/DashboardHighlightContext';
import { useVerificationSyncContext } from '@/contexts/VerificationSyncContext';

interface RevenueData {
  verifiedRevenue: number;
  unverifiedRevenue: number;
  totalRevenue: number;
  verifiedPercentage: number;
  unverifiedPercentage: number;
  timestamp: string;
  currency?: 'USD' | 'EUR';
  confidenceScore?: number;
}

interface DualRevenueCardProps {
  data?: RevenueData;
  onPoll?: () => Promise<RevenueData>;
  pollingInterval?: number;
  currency?: 'USD' | 'EUR';
}

const useAnimatedRevenue = (target: number, shouldAnimate: boolean, duration: number = 800): number => {
  const [current, setCurrent] = useState(0);
  const rafRef = useRef<number>();
  const startValueRef = useRef(0);
  
  useEffect(() => {
    const prefersReducedMotion = typeof window !== 'undefined' && window.matchMedia 
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches 
      : false;
    
    // Instantly update without animation if:
    // - User prefers reduced motion
    // - Change is below animation threshold
    if (prefersReducedMotion || !shouldAnimate) {
      setCurrent(target);
      return;
    }

    const startTime = Date.now();
    startValueRef.current = current;
    const diff = target - startValueRef.current;
    
    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = progress < 0.5 ? 2 * progress * progress : 1 - Math.pow(-2 * progress + 2, 2) / 2;
      setCurrent(startValueRef.current + diff * eased);
      if (progress < 1) rafRef.current = requestAnimationFrame(animate);
    };
    
    rafRef.current = requestAnimationFrame(animate);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [target, shouldAnimate, duration]);
  
  return current;
};

const ProgressRing = ({ percentage, color, size = 64, 'aria-label': ariaLabel }: { percentage: number; color: string; size?: number; 'aria-label'?: string }) => {
  const radius = 30;
  const strokeWidth = 4;
  const circumference = 2 * Math.PI * radius;
  const minVisiblePercentage = 5;
  const displayPercentage = percentage > 0 && percentage < minVisiblePercentage ? minVisiblePercentage : percentage;
  const dashValue = (displayPercentage / 100) * circumference;
  
  return (
    <svg width={size} height={size} className="transform -rotate-90" role="img" aria-label={ariaLabel}>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="var(--dual-progress-bg, hsl(213 86% 20% / 0.1))"
        strokeWidth={strokeWidth}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        className="progress-ring-circle"
        style={{ '--progress-value': `${dashValue}` } as CSSProperties}
      />
      <text
        x={size / 2}
        y={size / 2}
        textAnchor="middle"
        dy=".35em"
        className="transform rotate-90"
        style={{ 
          fontSize: '16px', 
          fontWeight: 700, 
          fill: color,
          transformOrigin: 'center'
        }}
      >
        {Math.round(percentage)}%
      </text>
    </svg>
  );
};

const DualRevenueSkeleton = () => (
  <div 
    className="dual-revenue-card rounded-2xl p-6 grid grid-cols-1 md:grid-cols-[1fr_2px_1fr] gap-4"
    style={{
      background: 'var(--dual-card-bg, hsl(233 15% 97% / 0.85))',
      backdropFilter: 'blur(var(--dual-card-blur, 20px))',
      WebkitBackdropFilter: 'blur(var(--dual-card-blur, 20px))',
      border: '1px solid var(--dual-card-border, hsl(213 71% 76% / 0.3))',
      boxShadow: 'var(--dual-card-shadow, 0 8px 32px rgba(9, 47, 100, 0.12))'
    }}
  >
    <div className="space-y-4">
      <div className="h-6 w-40 dual-skeleton rounded" />
      <div className="h-12 w-full dual-skeleton rounded" />
      <div className="h-4 w-24 dual-skeleton rounded" />
    </div>
    <div className="hidden md:block" style={{ background: 'var(--dual-divider, hsl(213 86% 20% / 0.15))' }} />
    <div className="block md:hidden h-[2px]" style={{ background: 'var(--dual-divider, hsl(213 86% 20% / 0.15))' }} />
    <div className="space-y-4">
      <div className="h-6 w-40 dual-skeleton rounded" />
      <div className="h-12 w-full dual-skeleton rounded" />
      <div className="h-4 w-24 dual-skeleton rounded" />
    </div>
  </div>
);

export default function DualRevenueCard({ 
  data: initialData, 
  onPoll, 
  pollingInterval = 30000,
  currency = 'USD'
}: DualRevenueCardProps) {
  const [data, setData] = useState<RevenueData | null>(initialData || null);
  const [isLoading, setIsLoading] = useState(!initialData);
  const [error, setError] = useState<string | null>(null);
  const [failureCount, setFailureCount] = useState(0);
  const [retryDelay, setRetryDelay] = useState(0);
  const [circuitOpen, setCircuitOpen] = useState(false);
  const lastUpdateRef = useRef<Date>(initialData ? new Date(initialData.timestamp) : new Date());
  const circuitOpenTimeRef = useRef<number>(0);
  
  const { setHighlight, clearHighlight, isVerifiedHighlighted, isUnverifiedHighlighted } = useDashboardHighlight();
  
  // FE-UX-021: Verification Sync Integration
  const { highlightedComponent, isAnimating } = useVerificationSyncContext();
  
  // Track last values to determine if animation should be triggered
  const lastVerifiedRef = useRef<number>(initialData?.verifiedRevenue || 0);
  const lastUnverifiedRef = useRef<number>(initialData?.unverifiedRevenue || 0);
  
  // Only animate when revenue changes by more than 5%
  const ANIMATION_THRESHOLD = 0.05;
  
  const shouldAnimateValue = (currentValue: number, lastValue: number): boolean => {
    if (lastValue === 0) return currentValue > 0;
    const percentageChange = Math.abs((currentValue - lastValue) / lastValue);
    return percentageChange > ANIMATION_THRESHOLD;
  };
  
  const verifiedTarget = data?.verifiedRevenue || 0;
  const unverifiedTarget = data?.unverifiedRevenue || 0;
  
  // Determine if we should animate based on change magnitude
  const shouldAnimateVerified = shouldAnimateValue(verifiedTarget, lastVerifiedRef.current);
  const shouldAnimateUnverified = shouldAnimateValue(unverifiedTarget, lastUnverifiedRef.current);
  
  // Update refs to current values for next comparison
  useEffect(() => {
    lastVerifiedRef.current = verifiedTarget;
  }, [verifiedTarget]);
  
  useEffect(() => {
    lastUnverifiedRef.current = unverifiedTarget;
  }, [unverifiedTarget]);

  // Always pass current target, but control animation via shouldAnimate flag
  const animatedVerified = useAnimatedRevenue(verifiedTarget, shouldAnimateVerified);
  const animatedUnverified = useAnimatedRevenue(unverifiedTarget, shouldAnimateUnverified);

  useEffect(() => {
    if (data) {
      const { verifiedRevenue, unverifiedRevenue, totalRevenue } = data;
      const calculatedTotal = verifiedRevenue + unverifiedRevenue;
      const tolerance = totalRevenue * 0.005;
      
      if (Math.abs(calculatedTotal - totalRevenue) > tolerance) {
        console.warn(
          `[DualRevenueCard] Revenue validation failed: ` +
          `verified (${verifiedRevenue}) + unverified (${unverifiedRevenue}) = ${calculatedTotal}, ` +
          `but totalRevenue is ${totalRevenue}. Difference: ${Math.abs(calculatedTotal - totalRevenue)}, ` +
          `tolerance: ±${tolerance}`
        );
      }
    }
  }, [data]);

  const handlePoll = useCallback(async () => {
    if (!onPoll) return;
    
    if (circuitOpen && Date.now() - circuitOpenTimeRef.current < 30000) {
      console.warn('[DualRevenueCard] Circuit breaker open, skipping poll');
      return;
    }
    
    if (circuitOpen && Date.now() - circuitOpenTimeRef.current >= 30000) {
      setCircuitOpen(false);
      setFailureCount(0);
      console.log('[DualRevenueCard] Circuit breaker half-open, attempting request');
    }
    
    try {
      const newData = await onPoll();
      setData(newData);
      setError(null);
      setFailureCount(0);
      setRetryDelay(0);
      if (circuitOpen) {
        setCircuitOpen(false);
        console.log('[DualRevenueCard] Circuit breaker closed after successful request');
      }
      lastUpdateRef.current = new Date(newData.timestamp);
    } catch (err) {
      const newFailureCount = failureCount + 1;
      setFailureCount(newFailureCount);
      
      if (newFailureCount >= 3) {
        setCircuitOpen(true);
        circuitOpenTimeRef.current = Date.now();
        setError('Service temporarily unavailable');
        console.error('[DualRevenueCard] Circuit breaker opened after 3 failures');
      } else {
        const delays = [1000, 2000, 4000];
        const delay = delays[newFailureCount - 1] || 4000;
        setRetryDelay(delay);
        setError('Unable to fetch revenue data');
        console.warn(`[DualRevenueCard] Retry ${newFailureCount}/3 failed, next retry in ${delay}ms`);
      }
    } finally {
      setIsLoading(false);
    }
  }, [onPoll, failureCount, circuitOpen]);

  const { isPaused } = usePollingManager({
    intervalMs: pollingInterval,
    onPoll: handlePoll
  });

  useEffect(() => {
    if (initialData) {
      lastUpdateRef.current = new Date(initialData.timestamp);
    } else if (onPoll) {
      handlePoll();
    }
  }, [initialData]);
  
  useEffect(() => {
    if (data) {
      lastUpdateRef.current = new Date(data.timestamp);
    }
  }, [data]);

  const isStale = () => {
    const now = new Date();
    const diff = now.getTime() - lastUpdateRef.current.getTime();
    return diff > 2 * 60 * 1000;
  };

  if (isLoading) return <DualRevenueSkeleton />;

  if (data && data.verifiedRevenue === 0 && data.unverifiedRevenue === 0 && data.totalRevenue === 0) {
    return (
      <div 
        className="dual-revenue-card glass-card p-4 md:p-6 rounded-2xl"
        style={{
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          background: 'var(--dual-card-bg, hsl(233 15% 97% / 0.85))',
          boxShadow: 'var(--dual-card-shadow, 0 8px 32px rgba(9, 47, 100, 0.12))',
          border: '1px solid var(--dual-card-border, hsl(213 71% 76% / 0.3))'
        }}
        role="region"
        aria-label="Dual revenue display"
        data-testid="dual-revenue-card-empty"
      >
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <div className="w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center mb-4">
            <PendingVerificationIndicator size={32} aria-label="No revenue data" />
          </div>
          <h3 className="text-lg font-semibold mb-2">No Revenue Data Yet</h3>
          <p className="text-sm text-muted-foreground">Revenue tracking will appear here once data is available</p>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div 
        className="dual-revenue-card rounded-2xl p-4 md:p-6 flex items-center justify-center"
        style={{
          background: 'var(--dual-card-bg, hsl(233 15% 97% / 0.85))',
          backdropFilter: 'blur(var(--dual-card-blur, 20px))',
          WebkitBackdropFilter: 'blur(var(--dual-card-blur, 20px))',
          border: '1px solid var(--dual-card-border, hsl(213 71% 76% / 0.3))',
          boxShadow: 'var(--dual-card-shadow, 0 8px 32px rgba(9, 47, 100, 0.12))'
        }}
      >
        <div className="text-center space-y-2">
          <PendingVerificationIndicator size={32} aria-label="Error state" />
          <p style={{ color: 'var(--dual-unverified-label, hsl(213 86% 20% / 0.7))' }}>{error}</p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const verifiedPercentage = data.verifiedPercentage || 
    (data.totalRevenue > 0 ? (data.verifiedRevenue / data.totalRevenue) * 100 : 0);
  const unverifiedPercentage = data.unverifiedPercentage || 
    (data.totalRevenue > 0 ? (data.unverifiedRevenue / data.totalRevenue) * 100 : 0);


  const showVerified = data.verifiedRevenue > 0 || data.totalRevenue === 0;
  const showUnverified = data.unverifiedRevenue > 0 || data.totalRevenue === 0;

  return (
    <div 
      className="dual-revenue-card rounded-2xl p-4 md:p-6 grid grid-cols-1 md:grid-cols-[1fr_2px_1fr] gap-4 relative"
      style={{
        background: 'var(--dual-card-bg, hsl(233 15% 97% / 0.85))',
        backdropFilter: 'blur(var(--dual-card-blur, 20px))',
        WebkitBackdropFilter: 'blur(var(--dual-card-blur, 20px))',
        border: '1px solid var(--dual-card-border, hsl(213 71% 76% / 0.3))',
        boxShadow: 'var(--dual-card-shadow, 0 8px 32px rgba(9, 47, 100, 0.12))'
      }}
      role="region"
      aria-label="Dual revenue display"
      data-testid="dual-revenue-card"
    >
      {isStale() && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div 
                className="absolute -top-2 -right-2 w-10 h-10 rounded-full flex items-center justify-center z-10"
                style={{ background: 'var(--dual-stale-bg, hsl(25 95% 53% / 0.1))' }}
                data-testid="stale-indicator"
              >
                <PendingVerificationIndicator size={32} aria-label="Data is stale" />
              </div>
            </TooltipTrigger>
            <TooltipContent>
              <p>Last updated: {Math.round((Date.now() - lastUpdateRef.current.getTime()) / 60000)} minutes ago</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}

      {showVerified && (
        <TooltipAdvanced
          placement="top"
          sideOffset={12}
          collisionPadding={16}
          protectedElements={['[data-protected-zone="verification-status"]', '[data-protected-zone="verification-flow"]']}
        >
          <TooltipAdvancedTrigger asChild>
            <div
              className={`
                revenue-section relative p-4 rounded-xl min-h-[44px] cursor-help 
                focus-visible:outline-2 focus-visible:outline-offset-4
                transition-all duration-300 ease-out
                ${isVerifiedHighlighted() ? 'ring-4 ring-green-400 ring-opacity-50 shadow-xl shadow-green-200/50' : ''}
                ${highlightedComponent === 'verified' && isAnimating ? 'ring-4 ring-green-300 ring-opacity-50 animate-pulse-once' : ''}
              `}
              style={{
                background: 'hsl(var(--verified) / 0.08)',
                borderLeft: '4px solid hsl(var(--verified) / 1)',
                outlineColor: 'hsl(var(--verified) / 1)'
              }}
              aria-label="Verified revenue section. Hover to highlight related platforms."
              data-testid="section-verified"
              tabIndex={0}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'hsl(var(--verified) / 0.12)';
                setHighlight('verified');
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'hsl(var(--verified) / 0.08)';
                clearHighlight();
              }}
              onFocus={(e) => {
                e.currentTarget.style.background = 'hsl(var(--verified) / 0.12)';
                setHighlight('verified');
              }}
              onBlur={(e) => {
                e.currentTarget.style.background = 'hsl(var(--verified) / 0.08)';
                clearHighlight();
              }}
            >
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-2 flex-wrap">
              <VerificationCheckmarkBadge 
                size={32} 
                aria-label="Verified" 
                className="verified-icon"
              />
              <span 
                className="text-xs font-bold uppercase tracking-wider"
                style={{ color: 'hsl(var(--verified-foreground) / 1)', letterSpacing: '1px' }}
              >
                Verified Revenue
              </span>
              {data.confidenceScore !== undefined && (
                <ConfidenceScoreBadge score={Math.round(data.confidenceScore * 100)} />
              )}
            </div>
            <ProgressRing 
              percentage={verifiedPercentage} 
              color="hsl(var(--verified) / 1)"
              aria-label={`${Math.round(verifiedPercentage)}% verified revenue`}
            />
          </div>
          
          <div className="mb-3" aria-live="polite" aria-atomic="true" style={{ fontVariantNumeric: 'tabular-nums' }}>
            <RevenueDisplay 
              value={animatedVerified}
              currency={currency}
              verified={true}
            />
          </div>
          
          <div 
            className="text-sm font-medium"
            style={{ color: 'hsl(var(--verified-foreground) / 0.8)' }}
            data-testid="text-verified-percentage"
          >
            {verifiedPercentage < 1 && verifiedPercentage > 0 ? '< 1%' : `${Math.round(verifiedPercentage)}%`} of total
          </div>
        </div>
      </TooltipAdvancedTrigger>
      <TooltipAdvancedContent 
        className="max-w-xs p-4 !bg-gray-900 dark:!bg-gray-900 text-white rounded-lg shadow-xl border-gray-700"
        showArrow={true}
      >
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <p className="font-semibold text-green-100">Verified Revenue</p>
                </div>
                <p className="text-gray-200 leading-relaxed">
                  This revenue has been <strong className="text-white">confirmed through direct platform integrations</strong>. You can confidently use this data for budget allocation and strategic decisions.
                </p>
                <div className="pt-3 border-t border-gray-700">
                  <p className="text-xs text-gray-400 leading-relaxed">
                    Verified revenue represents transactions that have been successfully reconciled with payment processor records (Stripe, PayPal, etc.) and match your internal attribution data with 90%+ confidence.
                  </p>
                </div>
              </div>
            </TooltipAdvancedContent>
          </TooltipAdvanced>
      )}

      <div className="hidden md:block section-divider" style={{ background: 'var(--dual-divider, hsl(213 86% 20% / 0.15))' }} />
      <div className="block md:hidden section-divider h-[2px] my-2" style={{ background: 'var(--dual-divider, hsl(213 86% 20% / 0.15))' }} />

      {showUnverified && (
        <TooltipAdvanced
          placement="top"
          sideOffset={12}
          collisionPadding={16}
          protectedElements={['[data-protected-zone="verification-status"]', '[data-protected-zone="verification-flow"]']}
        >
          <TooltipAdvancedTrigger asChild>
            <div
              className={`
                revenue-section relative p-4 rounded-xl min-h-[44px] cursor-help 
                focus-visible:outline-2 focus-visible:outline-offset-4
                transition-all duration-300 ease-out
                ${isUnverifiedHighlighted() ? 'ring-4 ring-amber-400 ring-opacity-50 shadow-xl shadow-amber-200/50' : ''}
                ${highlightedComponent === 'unverified' && isAnimating ? 'ring-4 ring-amber-300 ring-opacity-50 animate-pulse-once' : ''}
              `}
              style={{
                background: 'hsl(var(--unverified) / 0.08)',
                borderLeft: '4px solid hsl(var(--unverified) / 1)',
                outlineColor: 'hsl(var(--unverified) / 1)'
              }}
              aria-label="Unverified revenue section. Hover to highlight related platforms."
              data-testid="section-unverified"
              tabIndex={0}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'hsl(var(--unverified) / 0.12)';
                setHighlight('unverified');
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'hsl(var(--unverified) / 0.08)';
                clearHighlight();
              }}
              onFocus={(e) => {
                e.currentTarget.style.background = 'hsl(var(--unverified) / 0.12)';
                setHighlight('unverified');
              }}
              onBlur={(e) => {
                e.currentTarget.style.background = 'hsl(var(--unverified) / 0.08)';
                clearHighlight();
              }}
            >
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-2">
              <PendingVerificationIndicator 
                size={32} 
                aria-label="Unverified" 
                className="unverified-icon"
              />
              <span 
                className="text-xs font-semibold uppercase tracking-wider"
                style={{ color: 'hsl(var(--unverified-foreground) / 1)', letterSpacing: '1px' }}
              >
                Unverified Revenue
              </span>
            </div>
            <ProgressRing 
              percentage={unverifiedPercentage} 
              color="hsl(var(--unverified) / 1)"
              aria-label={`${Math.round(unverifiedPercentage)}% unverified revenue`}
            />
          </div>
          
          <div className="mb-3" aria-live="polite" aria-atomic="true" style={{ fontVariantNumeric: 'tabular-nums' }}>
            <RevenueDisplay 
              value={animatedUnverified}
              currency={currency}
              verified={false}
            />
          </div>
          
          <div 
            className="text-sm font-medium"
            style={{ color: 'hsl(var(--unverified-foreground) / 0.8)' }}
            data-testid="text-unverified-percentage"
          >
            {unverifiedPercentage < 1 && unverifiedPercentage > 0 ? '< 1%' : `${Math.round(unverifiedPercentage)}%`} of total
          </div>
        </div>
      </TooltipAdvancedTrigger>
      <TooltipAdvancedContent 
        className="max-w-xs p-4 !bg-gray-900 dark:!bg-gray-900 text-white rounded-lg shadow-xl border-gray-700"
        showArrow={true}
      >
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-full bg-amber-500 flex items-center justify-center">
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  </div>
                  <p className="font-semibold text-amber-100">Unverified Revenue</p>
                </div>
                <p className="text-gray-200 leading-relaxed">
                  This revenue is <strong className="text-white">estimated and requires additional validation</strong> through platform reconciliation. Use this data for forecasting and trend analysis while verification is in progress.
                </p>
                <div className="bg-amber-900/30 rounded p-2 border border-amber-700/50">
                  <p className="text-xs text-amber-100 leading-relaxed">
                    <strong>How it works:</strong> As platforms sync and transactions are reconciled, revenue automatically moves from unverified → verified. This typically takes 15-60 minutes depending on platform sync frequency.
                  </p>
                </div>
                <div className="pt-3 border-t border-gray-700">
                  <p className="text-xs text-gray-400 leading-relaxed">
                    Unverified revenue includes partial matches (70-89% confidence) and pending reconciliation from connected payment platforms.
                  </p>
                </div>
              </div>
            </TooltipAdvancedContent>
          </TooltipAdvanced>
      )}

      <div className="col-span-1 md:col-span-3 mt-4">
        <div 
          className="flex h-2 overflow-hidden rounded"
          aria-label={`Revenue comparison: ${Math.round(verifiedPercentage)}% verified, ${Math.round(unverifiedPercentage)}% unverified`}
        >
          <div 
            className="comparison-bar h-full"
            style={{ 
              background: 'hsl(var(--verified) / 1)',
              width: `${verifiedPercentage}%`,
              minWidth: verifiedPercentage > 0 && verifiedPercentage < 1 ? '8px' : undefined,
              borderRadius: verifiedPercentage === 100 ? '4px' : '4px 0 0 4px'
            } as CSSProperties}
            data-testid="bar-verified"
          />
          <div 
            className="comparison-bar h-full"
            style={{ 
              background: 'hsl(var(--unverified) / 1)',
              width: `${unverifiedPercentage}%`,
              minWidth: unverifiedPercentage > 0 && unverifiedPercentage < 1 ? '8px' : undefined,
              borderRadius: unverifiedPercentage === 100 ? '4px' : '0 4px 4px 0'
            } as CSSProperties}
            data-testid="bar-unverified"
          />
        </div>
      </div>
    </div>
  );
}
