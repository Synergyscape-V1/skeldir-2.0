import { useEffect, useState } from 'react';
import { CheckCircle, X } from 'lucide-react';
import { useVerificationSyncContext } from '@/contexts/VerificationSyncContext';
import { useToast } from '@/hooks/use-toast';

// ============================================================================
// TOAST COMPONENT
// ============================================================================

export const VerificationToast = () => {
  const { currentUpdate, isAnimating } = useVerificationSyncContext();
  const { toast } = useToast();
  const [hasShownToast, setHasShownToast] = useState(false);

  useEffect(() => {
    if (!currentUpdate || !isAnimating || hasShownToast) {
      return;
    }

    // Show toast 400ms after animation starts (as per directive)
    const timer = setTimeout(() => {
      const count = currentUpdate.transactionsVerified;
      const platforms = currentUpdate.platformsAffected.join(', ');
      
      toast({
        title: "Verification Complete",
        description: `${count} new transaction${count !== 1 ? 's' : ''} verified${platforms ? ` from ${platforms}` : ''}`,
        duration: 4000,
      });
      
      setHasShownToast(true);
    }, 400);

    return () => {
      clearTimeout(timer);
    };
  }, [currentUpdate, isAnimating, hasShownToast, toast]);

  // Reset flag when animation completes
  useEffect(() => {
    if (!isAnimating) {
      setHasShownToast(false);
    }
  }, [isAnimating]);

  return null; // This component only triggers toasts, doesn't render anything
};

// ============================================================================
// STANDALONE TOAST COMPONENT (Alternative Implementation)
// ============================================================================

interface ToastNotificationProps {
  message: string;
  onDismiss: () => void;
}

export const ToastNotification = ({ message, onDismiss }: ToastNotificationProps) => {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 4000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  return (
    <div 
      className="fixed top-4 right-4 z-50 bg-white dark:bg-gray-800 border-l-4 border-l-green-500 rounded-lg shadow-lg p-4 flex items-center space-x-3 min-w-[320px] animate-in slide-in-from-top-2"
      data-testid="verification-toast"
    >
      <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-500 flex-shrink-0" />
      <p className="flex-1 text-sm font-medium text-foreground">{message}</p>
      <button
        onClick={onDismiss}
        className="text-muted-foreground hover:text-foreground transition-colors"
        aria-label="Dismiss notification"
        data-testid="button-dismiss-toast"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};
