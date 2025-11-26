import { useState, useCallback, ReactNode } from 'react';
import { ErrorBannerContextInstance } from './ErrorBannerContext';
import type { BannerConfig } from '@/types/error-banner';

const MAX_VISIBLE_BANNERS = 3;

interface ErrorBannerProviderProps {
  children: ReactNode;
}

export function ErrorBannerProvider({ children }: ErrorBannerProviderProps) {
  const [banners, setBanners] = useState<BannerConfig[]>([]);

  const showBanner = useCallback((config: Omit<BannerConfig, 'id' | 'createdAt'>) => {
    const id = `banner-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const banner: BannerConfig = {
      ...config,
      id,
      createdAt: Date.now(),
    };

    console.log(
      `[ErrorBanner:Create] id=${id} severity=${config.severity} correlationId=${
        config.correlationId || 'none'
      } time=${new Date().toISOString()}`
    );

    setBanners((prev) => {
      if (prev.length >= MAX_VISIBLE_BANNERS) {
        const evictIndex = prev.findIndex((b) => b.severity !== 'critical');
        
        if (evictIndex >= 0) {
          const newBanners = prev.slice();
          const evicted = newBanners.splice(evictIndex, 1)[0];
          console.log(
            `[ErrorBanner:Evicted] id=${evicted.id} severity=${evicted.severity} correlationId=${
              evicted.correlationId || 'none'
            } reason=non-critical,queue-full time=${new Date().toISOString()}`
          );
          return [...newBanners, banner];
        } else {
          const evicted = prev[0];
          console.log(
            `[ErrorBanner:Evicted] id=${evicted.id} severity=${evicted.severity} correlationId=${
              evicted.correlationId || 'none'
            } reason=all-critical,oldest-first time=${new Date().toISOString()}`
          );
          return [...prev.slice(1), banner];
        }
      }
      return [...prev, banner];
    });

    return id;
  }, []);

  const dismissBanner = useCallback((id: string, reason: 'manual' | 'auto' = 'manual') => {
    setBanners((prev) => {
      const banner = prev.find((b) => b.id === id);
      if (banner) {
        const eventType = reason === 'auto' ? 'AutoDismiss' : 'ManualDismiss';
        console.log(
          `[ErrorBanner:${eventType}] id=${id} severity=${banner.severity} correlationId=${
            banner.correlationId || 'none'
          } time=${new Date().toISOString()}`
        );
      }
      return prev.filter((b) => b.id !== id);
    });
  }, []);

  return (
    <ErrorBannerContextInstance.Provider value={{ banners, showBanner, dismissBanner }}>
      {children}
    </ErrorBannerContextInstance.Provider>
  );
}
