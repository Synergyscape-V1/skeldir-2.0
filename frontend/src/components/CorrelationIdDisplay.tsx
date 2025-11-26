import { useState } from 'react';
import copyIcon from '@/assets/brand/icons/copy.svg';
import checkIcon from '@/assets/brand/icons/checkmark.svg';

export function CorrelationIdDisplay({ correlationId, disableEntranceAnimation = false }: { correlationId: string; disableEntranceAnimation?: boolean }) {
  const [copied, setCopied] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const segs = correlationId.split('-');
  const mobile = typeof window !== 'undefined' && window.innerWidth < 768;
  const copy = () => { navigator.clipboard.writeText(correlationId); setCopied(true); setTimeout(() => setCopied(false), 2000); };

  return (
    <div className="relative" onMouseEnter={() => setShowTooltip(true)} onMouseLeave={() => setShowTooltip(false)} onFocus={() => setShowTooltip(true)} onBlur={() => setShowTooltip(false)}>
      <div onClick={copy} onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), copy())} role="button" tabIndex={0}
        aria-label={`Correlation ID: ${correlationId}, click to copy`} data-testid="correlation-id-display"
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md cursor-pointer font-mono text-[11px] tracking-normal border ${copied ? 'animate-[copyPulse_500ms_ease-out]' : ''}`}
        style={{ background: 'rgba(233,245,255,0.4)', backdropFilter: 'blur(8px)', borderColor: 'rgba(9,47,100,0.12)', color: 'rgba(9,47,100,0.7)', ...(disableEntranceAnimation ? {} : { animation: 'correlationEnter 250ms cubic-bezier(0.4,0,0.2,1) 100ms forwards', opacity: 0 }) }}>
        <span className="flex items-center gap-0.5" aria-live="polite">
          {mobile ? `${segs[0]}...${segs[4]}` : segs.map((s, i) => (
            <span key={i} style={{ opacity: [0.9, 0.85, 0.8, 0.85, 0.9][i] }} className="transition-opacity duration-150 hover:opacity-100">
              {s}{i < 4 && <span className="mx-0.5 text-[9px]" style={{ opacity: 0.1 }}>|</span>}
            </span>
          ))}
        </span>
        <img src={copied ? checkIcon : copyIcon} alt="" className={`w-3 h-3 ${copied ? 'animate-[iconMorph_150ms_ease]' : ''}`} style={{ opacity: 0.6 }} />
        {copied && <span className="sr-only">Copied to clipboard</span>}
      </div>
      {showTooltip && (
        <div className="absolute bottom-full left-0 mb-1 px-2 py-1 rounded text-[10px] font-mono whitespace-nowrap animate-[fullTooltipShow_200ms_ease_150ms_forwards] opacity-0" style={{ background: 'rgba(233,245,255,0.95)', color: 'rgba(9,47,100,0.8)', zIndex: 10000 }}>
          {correlationId}
        </div>
      )}
    </div>
  );
}
