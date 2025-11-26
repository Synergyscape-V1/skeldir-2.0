export type BannerSeverity = 'info' | 'warning' | 'error' | 'critical';

export interface BannerAction {
  label: string;
  onClick: () => void;
  testId?: string;
}

export interface BannerConfig {
  id: string;
  severity: BannerSeverity;
  message: string;
  action?: BannerAction;
  duration?: number;
  correlationId?: string;
  createdAt: number;
}

export interface ErrorBannerContext {
  banners: BannerConfig[];
  showBanner: (config: Omit<BannerConfig, 'id' | 'createdAt'>) => string;
  dismissBanner: (id: string, reason?: 'manual' | 'auto') => void;
}
