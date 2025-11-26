import { ToastNotification, ToastNotificationProps } from './Toast';
import './Toast.css';

interface ToastContainerProps {
  toasts: Omit<ToastNotificationProps, 'onDismiss'>[];
  onDismiss: (id: string) => void;
}

export const ToastNotificationContainer = ({ toasts, onDismiss }: ToastContainerProps) => {
  // Render all toasts including dismissing ones
  // The dismissing toast will animate out and be removed within 250ms
  // This ensures the exit animation plays for toasts being dismissed when the 4th arrives
  return (
    <div className="toast-notification-container" aria-live="polite" aria-atomic="false">
      {toasts.map((toast, index) => (
        <div
          key={toast.id}
          className="toast-notification-wrapper toast-notification-reposition"
          style={{
            transform: `translateY(-${index * 8}px)`, // Stack spacing
          }}
        >
          <ToastNotification {...toast} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  );
};
