import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useEffect, useState } from "react";

type RequestStatusProps = 
  | {
      status: 'loading';
      skeletonVariant?: 'text' | 'avatar' | 'card' | 'activityList';
      message?: never;
      onRetry?: never;
    }
  | {
      status: 'success';
      skeletonVariant?: 'text' | 'avatar' | 'card' | 'activityList';
      message?: never;
      onRetry?: never;
    }
  | {
      status: 'empty';
      skeletonVariant?: 'text' | 'avatar' | 'card' | 'activityList';
      message?: string;
      onRetry?: never;
    }
  | {
      status: 'error';
      skeletonVariant?: 'text' | 'avatar' | 'card' | 'activityList';
      message?: string;
      onRetry: () => void;
    };

const Skeletons = {
  text: <><div className="skeleton-loader h-4 w-full rounded-md" aria-hidden="true" /><div className="skeleton-loader h-4 w-3/4 rounded-md" aria-hidden="true" /><div className="skeleton-loader h-4 w-5/6 rounded-md" aria-hidden="true" /></>,
  avatar: <><div className="skeleton-loader h-12 w-12 rounded-full" aria-hidden="true" /><div className="skeleton-loader h-4 w-32 rounded-md" aria-hidden="true" /></>,
  card: <div className="skeleton-loader h-32 w-full rounded-md" aria-hidden="true" />,
  activityList: <div className="space-y-2">{[1, 2].map(i => (
    <div key={i} className="p-3 rounded-md skeleton-loader">
      <div className="h-4 w-3/4 rounded-md bg-current opacity-60 mb-2" aria-hidden="true" />
      <div className="h-3 w-1/2 rounded-md bg-current opacity-40" aria-hidden="true" />
    </div>
  ))}</div>
};

export function RequestStatus({ status, message, onRetry, skeletonVariant = 'text' }: RequestStatusProps) {
  const [display, setDisplay] = useState(status);
  const [transitioning, setTransitioning] = useState(false);

  useEffect(() => {
    if (status !== display && display === 'loading') {
      const transitionStart = performance.now();
      setTransitioning(true);
      const duration = status === 'success' ? 250 : status === 'error' ? 200 : 300;
      const t = setTimeout(() => { 
        if (import.meta.env.DEV) {
          const transitionEnd = performance.now();
          const actualDuration = transitionEnd - transitionStart;
          console.log(`[RequestStatus] Transition duration (${display} → ${status}): ${actualDuration.toFixed(2)}ms (target: ${duration}ms)`);
        }
        setDisplay(status); 
        setTransitioning(false); 
      }, duration);
      return () => clearTimeout(t);
    } else setDisplay(status);
  }, [status, display]);

  if (display === 'success' && !transitioning) return null;

  return (
    <div className="flex flex-col items-center justify-center gap-3 py-8" aria-live="polite" role="status" aria-busy={display === 'loading'}>
      {(display === 'loading' || transitioning) && <div className={`w-full space-y-3 ${transitioning ? (status === 'success' ? 'status-loading-to-success' : status === 'error' ? 'status-loading-to-error' : 'status-loading-to-empty') : ''}`}>{Skeletons[skeletonVariant]}</div>}
      {display === 'error' && !transitioning && (
        <div className="status-error-enter flex flex-col items-center gap-3 text-center">
          <AlertCircle className="h-12 w-12 text-[var(--status-error-icon)]" data-testid="icon-error" />
          <p className="text-sm text-[var(--status-error-text)]" data-testid="text-error-message">{message || 'Something went wrong. Please try again.'}</p>
          <Button onClick={onRetry} variant="default" aria-label="Retry loading data" data-testid="button-retry">Retry</Button>
        </div>
      )}
      {display === 'empty' && (
        <div className="status-empty-enter flex flex-col items-center gap-3 text-center">
          <svg className="empty-icon h-16 w-16 text-[var(--status-empty-icon)]" viewBox="0 0 306.028 306.028" aria-hidden="true" data-testid="icon-empty"><path fill="currentColor" d="M285.498,113.47H81.32V15h179.688v76.277c0,4.142,3.357,7.5,7.5,7.5s7.5-3.358,7.5-7.5V7.5c0-4.142-3.357-7.5-7.5-7.5H73.82c-4.143,0-7.5,3.358-7.5,7.5v113.47c0,0.438,0.045,0.864,0.117,1.281v149.841c0,10.441-8.494,18.936-18.936,18.936h-0.534c-10.441,0-18.937-8.495-18.937-18.936V91.963h18.937c4.143,0,7.5-3.358,7.5-7.5s-3.357-7.5-7.5-7.5H20.531c-4.143,0-7.5,3.358-7.5,7.5v187.629c0,18.712,15.224,33.936,33.937,33.936h0.534h201.197c24.427,0,44.299-19.873,44.299-44.299V120.97C292.998,116.828,289.64,113.47,285.498,113.47z M277.998,261.729c0,16.155-13.144,29.299-29.299,29.299H75.649c3.653-5.412,5.788-11.929,5.788-18.936V128.47h196.561V261.729z M98.011,41.633h49.663c4.143,0,7.5-3.358,7.5-7.5s-3.357-7.5-7.5-7.5H98.011c-4.143,0-7.5,3.358-7.5,7.5S93.869,41.633,98.011,41.633z M192.257,55.205H98.011c-4.143,0-7.5,3.358-7.5,7.5s3.357,7.5,7.5,7.5h94.246c4.143,0,7.5-3.358,7.5-7.5S196.4,55.205,192.257,55.205z M192.257,83.777H98.011c-4.143,0-7.5,3.358-7.5,7.5s3.357,7.5,7.5,7.5h94.246c4.143,0,7.5-3.358,7.5-7.5S196.4,83.777,192.257,83.777z M220.174,55.205c-4.143,0-7.5,3.358-7.5,7.5s3.357,7.5,7.5,7.5h20.417c4.143,0,7.5-3.358,7.5-7.5s-3.357-7.5-7.5-7.5H220.174z"/></svg>
          <p className="text-base text-[var(--status-error-text)]" data-testid="text-empty-message">{message || 'No data available'}</p>
        </div>
      )}
    </div>
  );
}
