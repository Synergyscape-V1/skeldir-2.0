import { useEffect, useState, useRef } from 'react';
import { CheckCircle, Info, AlertTriangle, XCircle, X } from 'lucide-react';
import { useAutoDismiss } from '@/hooks/use-auto-dismiss';
import './Toast.css';

export interface ToastNotificationProps {
  id: string;
  message: string;
  severity: 'success' | 'info' | 'warning' | 'error';
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
  isDismissing?: boolean;
  onDismiss: (id: string) => void;
}

export const ToastNotification = ({
  id,
  message,
  severity,
  duration,
  action,
  isDismissing,
  onDismiss,
}: ToastNotificationProps) => {
  const [isExiting, setIsExiting] = useState(false);
  const toastRef = useRef<HTMLDivElement>(null);

  // Default durations per severity (from spec)
  const defaultDurations = {
    success: 4000,
    info: 5000,
    warning: 7000,
    error: 10000,
  };

  const autoDismissDuration = duration ?? defaultDurations[severity];

  // Map toast severity to hook severity (success -> info for hook purposes)
  const hookSeverity: 'info' | 'warning' | 'error' | 'critical' = 
    severity === 'success' ? 'info' : severity;

  // Auto-dismiss integration with pause on hover
  // Note: useAutoDismiss returns progress as 0-1, we need to convert to 0-100 for display
  const { progress, isPaused, pause, resume } = useAutoDismiss({
    severity: hookSeverity,
    timeoutMs: autoDismissDuration,
    onDismiss: () => handleDismiss(),
  });

  // Icon mapping
  const icons = {
    success: <CheckCircle className="w-5 h-5" style={{ color: 'hsl(var(--brand-tufts))' }} />,
    info: <Info className="w-5 h-5" style={{ color: 'hsl(var(--brand-jordy))' }} />,
    warning: <AlertTriangle className="w-5 h-5" style={{ color: 'hsl(var(--brand-warning))' }} />,
    error: <XCircle className="w-5 h-5" style={{ color: 'hsl(var(--brand-error))' }} />,
  };

  // Severity color mapping for border
  const borderColors = {
    success: 'hsl(var(--brand-tufts))',
    info: 'hsl(var(--brand-jordy))',
    warning: 'hsl(var(--brand-warning))',
    error: 'hsl(var(--brand-error))',
  };

  // ARIA role mapping
  const ariaRole = severity === 'warning' || severity === 'error' ? 'alert' : 'status';

  const handleDismiss = () => {
    setIsExiting(true);
    // Wait for exit animation to complete
    setTimeout(() => {
      onDismiss(id);
    }, 250); // Exit animation duration from spec
  };

  // Handle external dismissal trigger (e.g., when 4th toast arrives)
  useEffect(() => {
    if (isDismissing && !isExiting) {
      handleDismiss();
    }
  }, [isDismissing, isExiting]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleDismiss();
      }
    };

    const currentRef = toastRef.current;
    if (currentRef) {
      currentRef.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      if (currentRef) {
        currentRef.removeEventListener('keydown', handleKeyDown);
      }
    };
  }, []);

  // Convert progress from 0-1 to 0-100
  const progressPercentage = progress * 100;

  return (
    <div
      ref={toastRef}
      className={`toast-notification ${isExiting ? 'toast-notification-exit' : 'toast-notification-enter'}`}
      role={ariaRole}
      aria-live={severity === 'error' ? 'assertive' : 'polite'}
      aria-atomic="true"
      onMouseEnter={pause}
      onMouseLeave={resume}
      onFocus={pause}
      onBlur={resume}
      style={{
        borderLeftColor: borderColors[severity],
      }}
      tabIndex={action ? 0 : -1}
      data-testid={`toast-${severity}`}
    >
      {/* Content Container */}
      <div className="toast-notification-content">
        {/* Icon */}
        <div className="toast-notification-icon" aria-hidden="true">
          {icons[severity]}
        </div>

        {/* Message */}
        <div className="toast-notification-message" data-testid={`toast-message-${severity}`}>
          {message}
        </div>

        {/* Optional Action Button */}
        {action && (
          <button
            className="toast-notification-action"
            onClick={action.onClick}
            data-testid="toast-action-button"
          >
            {action.label}
          </button>
        )}

        {/* Close Button */}
        <button
          className="toast-notification-close"
          onClick={handleDismiss}
          aria-label="Dismiss notification"
          data-testid="button-dismiss-toast"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Progress Bar */}
      <div
        className="toast-notification-progress"
        style={{
          width: `${100 - progressPercentage}%`,
          backgroundColor: borderColors[severity],
          opacity: 0.6,
          transitionDuration: isPaused ? '0s' : `${autoDismissDuration}ms`,
        }}
      />
    </div>
  );
};
