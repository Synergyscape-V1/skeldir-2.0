import { useState, useRef, useEffect } from 'react';
import { X, ChevronDown } from 'lucide-react';
import { SEVERITY_CONFIG } from '@/lib/error-banner-config';
import { useAutoDismiss } from '@/hooks/use-auto-dismiss';
import type { BannerConfig } from '@/types/error-banner';
import { Button } from '@/components/ui/button';
import { CorrelationIdDisplay } from '@/components/CorrelationIdDisplay';
import './ErrorBanner.css';

interface ErrorBannerProps {
  config: BannerConfig;
  index: number;
  totalBanners: number;
  onDismiss: (id: string, reason?: 'manual' | 'auto') => void;
}

export function ErrorBanner({ config, index, totalBanners, onDismiss }: ErrorBannerProps) {
  const { severity, message, action, id, correlationId } = config;
  const severityConfig = SEVERITY_CONFIG[severity];
  const Icon = severityConfig.icon;

  const [isEntering, setIsEntering] = useState(true);
  const [isExiting, setIsExiting] = useState(false);
  const [isDetailsExpanded, setIsDetailsExpanded] = useState(false);
  const [hasInteractedWithDetails, setHasInteractedWithDetails] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const actionButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const startTimeRef = useRef<number>(performance.now());
  const isAutoDismissRef = useRef<boolean>(false);

  const effectiveDuration = config.duration ?? severityConfig.duration;

  if (config.duration !== undefined && config.duration !== 0 && config.duration < 1000) {
    console.warn(`[ErrorBanner] Duration ${config.duration}ms < 1000ms minimum`);
  }

  const handleDismiss = () => {
    setIsExiting(true);
  };

  const autoDismiss = useAutoDismiss({
    severity,
    timeoutMs: effectiveDuration,
    onDismiss: () => {
      isAutoDismissRef.current = true;
      setIsExiting(true);
    }
  });

  useEffect(() => {
    previousFocusRef.current = document.activeElement as HTMLElement;

    setTimeout(() => {
      if (actionButtonRef.current) {
        actionButtonRef.current.focus();
      } else if (closeButtonRef.current) {
        closeButtonRef.current.focus();
      }
    }, 0);
  }, []);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      const container = containerRef.current;
      if (e.key === 'Escape' && container) {
        if (container === document.activeElement || container.contains(document.activeElement)) {
          e.preventDefault();
          handleDismiss();
        }
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, []);

  const handleAnimationEnd = (e: React.AnimationEvent) => {
    if (e.animationName === 'bannerSlideIn' || e.animationName === 'bannerFadeIn') {
      setIsEntering(false);
      if (containerRef.current) {
        containerRef.current.style.willChange = 'auto';
      }

      if (import.meta.env.DEV) {
        const duration = performance.now() - startTimeRef.current;
        if (duration < 280 || duration > 320) {
          console.warn(
            `[ErrorBanner] Entrance animation ${duration.toFixed(1)}ms outside tolerance 280-320ms`
          );
        } else {
          console.log(`[ErrorBanner] Entrance ${duration.toFixed(1)}ms ✓`);
        }
      }
    } else if (e.animationName === 'bannerSlideOut' || e.animationName === 'bannerFadeOut') {
      onDismiss(id, isAutoDismissRef.current ? 'auto' : 'manual');

      setTimeout(() => {
        if (index < totalBanners - 1) {
          const nextBanner = document.querySelector(`[data-banner-id][data-index="${index + 1}"]`);
          const nextCloseButton = nextBanner?.querySelector('[aria-label^="Close"]') as HTMLButtonElement;
          if (nextCloseButton) {
            nextCloseButton.focus();
            return;
          }
        }
        
        if (previousFocusRef.current && document.contains(previousFocusRef.current)) {
          previousFocusRef.current.focus();
        } else {
          document.body.focus();
        }
      }, 0);
    }
  };

  const position = 80 + index * 76;

  // Justification: position is data-driven (computed from banner index), not known at build time
  const positionStyle = typeof window !== 'undefined' && window.innerWidth <= 640
    ? { bottom: `${position}px` }
    : { top: `${position}px`, right: '24px' };

  return (
    <div
      ref={containerRef}
      className={`error-banner-container fixed z-[9999] w-[400px] ${
        isEntering ? 'banner-enter' : isExiting ? 'banner-exit' : 'banner-reposition'
      }`}
      // Justification: top/bottom/right are data-driven geometry (computed from banner stack index)
      style={positionStyle}
      data-index={index}
      data-banner-id={id}
      role={severityConfig.role}
      aria-live={severityConfig.ariaLive}
      aria-atomic="true"
      aria-label={`${severity.charAt(0).toUpperCase() + severity.slice(1)} notification`}
      onAnimationEnd={handleAnimationEnd}
      tabIndex={-1}
    >
      <div
        ref={autoDismiss.elementRef as React.RefObject<HTMLDivElement>}
        className={`relative rounded-lg p-3 backdrop-blur-[16px] shadow-[0_4px_16px_rgba(9,47,100,0.1)] border-l-4 ${
          severity === 'critical' ? 'banner-bg-critical' : 'banner-bg-default'
        }`}
        // Justification: borderLeft color is severity-driven (4 runtime variants from D0 token config)
        style={{ borderLeftColor: severityConfig.borderColor }}
      >
        <div className="flex items-start gap-3">
          <Icon
            className="error-banner-icon w-5 h-5 flex-shrink-0"
            // Justification: icon color is severity-driven (4 runtime variants from D0 token config)
            style={{ color: severityConfig.iconColor }}
            aria-hidden="true"
          />

          <div className="flex-1 min-w-0">
            <p
              className="error-banner-message text-sm leading-relaxed text-brand-cool-black"
              data-testid={`text-banner-message-${id}`}
            >
              {message}
            </p>

            {action && (
              <Button
                ref={actionButtonRef}
                variant="ghost"
                onClick={action.onClick}
                className="mt-1.5 min-h-[44px] hover:underline text-brand-tufts"
                style={{ textUnderlineOffset: '3px' }}
                data-testid={`button-action-${action.testId || severity}`}
              >
                {action.label}
              </Button>
            )}

            {correlationId && (
              <>
                <button
                  onClick={() => {
                    setHasInteractedWithDetails(true);
                    setIsDetailsExpanded(!isDetailsExpanded);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setHasInteractedWithDetails(true);
                      setIsDetailsExpanded(!isDetailsExpanded);
                    }
                  }}
                  className="mt-2 inline-flex items-center gap-1 text-xs font-medium transition-all duration-150 opacity-50 hover:opacity-100 text-brand-cool-black"
                  aria-expanded={isDetailsExpanded}
                  aria-controls={`advanced-details-${id}`}
                  data-testid={`button-toggle-details-${id}`}
                >
                  <ChevronDown
                    className={`w-3.5 h-3.5 transition-transform duration-200 ${isDetailsExpanded ? 'rotate-180' : ''}`}
                  />
                  <span>Advanced details</span>
                </button>

                <div
                  id={`advanced-details-${id}`}
                  className={`overflow-hidden ${!hasInteractedWithDetails && !isDetailsExpanded ? 'advanced-details-collapsed' : ''}`}
                  // Justification: animation/maxHeight/opacity are state-driven expand/collapse (dynamic geometry)
                  style={{
                    animation: isDetailsExpanded
                      ? 'detailsExpand 250ms cubic-bezier(0.4, 0, 0.2, 1) forwards'
                      : hasInteractedWithDetails
                        ? 'detailsCollapse 200ms cubic-bezier(0.4, 0, 0.2, 1) forwards'
                        : 'none',
                    ...(hasInteractedWithDetails && {
                      maxHeight: isDetailsExpanded ? '100px' : '0',
                      opacity: isDetailsExpanded ? 1 : 0,
                    })
                  }}
                  aria-hidden={!isDetailsExpanded}
                >
                  <CorrelationIdDisplay correlationId={correlationId} disableEntranceAnimation={true} />
                </div>
              </>
            )}
          </div>

          <Button
            ref={closeButtonRef}
            variant="ghost"
            size="icon"
            onClick={handleDismiss}
            className="min-w-[44px] min-h-[44px] -mr-2 -mt-2 opacity-60 hover:opacity-100 hover:scale-110 border-transparent text-brand-cool-black"
            aria-label={`Close ${severity} notification`}
            data-testid={`button-close-banner-${id}`}
          >
            <X className="w-6 h-6" />
          </Button>
        </div>
      </div>
    </div>
  );
}
