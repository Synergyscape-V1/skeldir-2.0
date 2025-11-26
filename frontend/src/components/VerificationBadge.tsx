import { useState, useRef } from 'react';
import type { ReconciliationContext } from '@shared/schema';
import checkmarkIcon from '@/assets/brand/icons/checkmark.svg';
import questionIcon from '@/assets/brand/icons/question.svg';

interface VerificationBadgeProps {
  verified: boolean;
  reconciliationContext?: ReconciliationContext;
}

export default function VerificationBadge({ verified, reconciliationContext }: VerificationBadgeProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  const timeoutRef = useRef<number>();
  const tooltipId = `tooltip-${Math.random().toString(36).substr(2, 9)}`;
  
  const handleMouseEnter = () => { 
    timeoutRef.current = window.setTimeout(() => setShowTooltip(true), 200); 
  };
  
  const handleMouseLeave = () => { 
    if (timeoutRef.current) window.clearTimeout(timeoutRef.current); 
    setShowTooltip(false); 
  };

  const handleFocus = () => {
    setShowTooltip(true);
  };

  const handleBlur = () => {
    setShowTooltip(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setShowTooltip(false);
      if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
    }
  };

  const getTooltipContent = (): string => {
    if (!reconciliationContext) {
      return verified 
        ? 'Verified: Reconciliation complete' 
        : 'Unverified: Awaiting reconciliation data';
    }

    if (verified) {
      const { source, matchPercentage, timeWindow } = reconciliationContext;
      let content = `Verified: Reconciled with ${source}`;
      
      if (timeWindow) {
        content += ` from ${timeWindow}`;
      }
      
      if (matchPercentage !== undefined) {
        content += ` (${matchPercentage}% match)`;
      }
      
      return content;
    } else {
      const { source, expectedReconciliation } = reconciliationContext;
      let content = `Pending—only ${source} data received`;
      
      if (expectedReconciliation) {
        content += `; backend reconciliation expected in ${expectedReconciliation}`;
      }
      
      return content;
    }
  };

  const getAriaLabel = (): string => {
    const tooltipContent = getTooltipContent();
    return `Verification status: ${tooltipContent}`;
  };

  const tooltipContent = getTooltipContent();
  const ariaLabel = getAriaLabel();

  return (
    <div className="relative inline-block">
      <div 
        className="verification-badge inline-flex items-center justify-center w-8 h-8 rounded-full border cursor-help" 
        style={{ 
          backgroundColor: 'var(--verification-badge-bg)', 
          borderColor: 'var(--verification-badge-border)', 
          backdropFilter: 'blur(12px)' 
        }} 
        role="status" 
        aria-label={ariaLabel}
        aria-describedby={showTooltip ? tooltipId : undefined} 
        onMouseEnter={handleMouseEnter} 
        onMouseLeave={handleMouseLeave}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        tabIndex={0}
        data-testid={`badge-${verified ? 'verified' : 'unverified'}`}
      >
        <img 
          src={verified ? checkmarkIcon : questionIcon} 
          alt="" 
          className={`w-4 h-4 ${verified ? 'checkmark-verified' : ''}`} 
          style={{ filter: verified ? 'none' : 'opacity(0.6)' }} 
          data-testid={`icon-${verified ? 'checkmark' : 'question'}`} 
        />
      </div>
      {showTooltip && (
        <div 
          id={tooltipId} 
          role="tooltip" 
          className="verification-tooltip absolute left-0 bottom-full mb-2 px-3 py-2 rounded-lg text-sm whitespace-nowrap pointer-events-none z-50" 
          style={{ 
            backgroundColor: '#1F2937', 
            color: '#FFFFFF',
            boxShadow: '0 4px 16px 0 rgba(0, 0, 0, 0.3)'
          }} 
          data-testid="tooltip-verification"
        >
          {tooltipContent}
          <div 
            className="absolute left-4 top-full w-0 h-0" 
            style={{ 
              borderLeft: '6px solid transparent', 
              borderRight: '6px solid transparent', 
              borderTop: '6px solid #1F2937' 
            }} 
          />
        </div>
      )}
    </div>
  );
}
