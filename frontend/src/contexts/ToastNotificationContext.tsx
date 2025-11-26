import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { ToastNotificationContainer } from '@/components/ui/toast-notification/ToastContainer';

interface ToastNotificationOptions {
  message: string;
  severity: 'success' | 'info' | 'warning' | 'error';
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

interface ToastNotificationContextType {
  showToast: (options: ToastNotificationOptions) => void;
  dismissToast: (id: string) => void;
  clearAllToasts: () => void;
}

const ToastNotificationContext = createContext<ToastNotificationContextType | undefined>(undefined);

interface ToastWithId extends ToastNotificationOptions {
  id: string;
  isDismissing?: boolean;
}

export const ToastNotificationProvider = ({ children }: { children: ReactNode }) => {
  const [toasts, setToasts] = useState<ToastWithId[]>([]);

  // Generate unique ID for each toast
  const generateId = () => `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => {
      const filtered = prev.filter((toast) => toast.id !== id);
      
      // After dismissal, enforce the 3-toast maximum
      // If we still have more than 3 toasts, mark the oldest non-dismissing one for dismissal
      if (filtered.length > 3) {
        const oldestIndex = filtered.length - 1;
        const oldest = filtered[oldestIndex];
        
        // Only mark for dismissal if not already dismissing
        if (!oldest.isDismissing) {
          filtered[oldestIndex] = { ...oldest, isDismissing: true };
        }
      }
      
      return filtered;
    });
  }, []);

  const showToast = useCallback((options: ToastNotificationOptions) => {
    const newToast: ToastWithId = {
      ...options,
      id: generateId(),
      isDismissing: false,
    };

    setToasts((prev) => {
      const updated = [newToast, ...prev];
      
      // Enforce maximum 3 active (non-dismissing) toasts
      // Mark all toasts beyond the 3rd newest as dismissing
      const nonDismissingCount = updated.filter(t => !t.isDismissing).length;
      
      if (nonDismissingCount > 3) {
        // Find and mark excess toasts as dismissing (from oldest to newest)
        let marked = 0;
        const needToMark = nonDismissingCount - 3;
        
        for (let i = updated.length - 1; i >= 0 && marked < needToMark; i--) {
          if (!updated[i].isDismissing) {
            updated[i] = { ...updated[i], isDismissing: true };
            marked++;
          }
        }
      }
      
      return updated;
    });
  }, []);

  const clearAllToasts = useCallback(() => {
    setToasts([]);
  }, []);

  return (
    <ToastNotificationContext.Provider value={{ showToast, dismissToast, clearAllToasts }}>
      {children}
      <ToastNotificationContainer toasts={toasts} onDismiss={dismissToast} />
    </ToastNotificationContext.Provider>
  );
};

export const useToastNotification = (): ToastNotificationContextType => {
  const context = useContext(ToastNotificationContext);
  if (!context) {
    throw new Error('useToastNotification must be used within ToastNotificationProvider');
  }
  return context;
};
