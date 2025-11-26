import { useContext } from 'react';
import { ErrorBannerContextInstance } from '@/components/error-banner/ErrorBannerContext';
import type { BannerSeverity, BannerAction } from '@/types/error-banner';

export function useErrorBanner(): {
  showBanner: (config: {
    severity: BannerSeverity;
    message: string;
    action?: BannerAction;
    duration?: number;
    correlationId?: string;
  }) => string;
  dismissBanner: (id: string) => void;
} {
  const context = useContext(ErrorBannerContextInstance);
  
  if (!context) {
    throw new Error('useErrorBanner must be used within ErrorBannerProvider');
  }

  return {
    showBanner: context.showBanner,
    dismissBanner: context.dismissBanner,
  };
}
