import { useState, useEffect } from 'react';

/**
 * Platform Logo Configuration
 * Centralized source of truth for all platform branding
 */
export const PLATFORM_CONFIGS = {
  stripe: {
    name: 'Stripe',
    logoUrl: '/assets/platform-logos/stripe-logo.svg',
    fallbackUrl: 'https://cdn.jsdelivr.net/gh/simple-icons/simple-icons@latest/icons/stripe.svg',
    aspectRatio: 3.5, // width:height ratio
    primaryColor: '#635BFF',
    displayName: 'Stripe',
  },
  shopify: {
    name: 'Shopify',
    logoUrl: '/assets/platform-logos/shopify-logo.svg',
    fallbackUrl: 'https://cdn.jsdelivr.net/gh/simple-icons/simple-icons@latest/icons/shopify.svg',
    aspectRatio: 4.2,
    primaryColor: '#96BF48',
    displayName: 'Shopify',
  },
  square: {
    name: 'Square',
    logoUrl: '/assets/platform-logos/square-logo.svg',
    fallbackUrl: 'https://cdn.jsdelivr.net/gh/simple-icons/simple-icons@latest/icons/square.svg',
    aspectRatio: 1.0, // Square is 1:1 ratio
    primaryColor: '#000000',
    displayName: 'Square',
  },
  'google-ads': {
    name: 'Google Ads',
    logoUrl: '/assets/platform-logos/google-ads-logo.svg',
    fallbackUrl: 'https://cdn.jsdelivr.net/gh/simple-icons/simple-icons@latest/icons/googleads.svg',
    aspectRatio: 4.0,
    primaryColor: '#4285F4',
    displayName: 'Google Ads',
  },
  google: {
    name: 'Google',
    logoUrl: '/assets/platform-logos/google-ads-logo.svg',
    fallbackUrl: 'https://cdn.jsdelivr.net/gh/simple-icons/simple-icons@latest/icons/google.svg',
    aspectRatio: 4.0,
    primaryColor: '#4285F4',
    displayName: 'Google',
  },
  'facebook-ads': {
    name: 'Facebook Ads',
    logoUrl: '/assets/platform-logos/facebook-ads-logo.svg',
    fallbackUrl: 'https://cdn.jsdelivr.net/gh/simple-icons/simple-icons@latest/icons/meta.svg',
    aspectRatio: 1.0,
    primaryColor: '#0866FF',
    displayName: 'Meta Ads',
  },
  tiktok: {
    name: 'TikTok',
    logoUrl: '/assets/platform-logos/tiktok-logo.svg',
    fallbackUrl: 'https://cdn.jsdelivr.net/gh/simple-icons/simple-icons@latest/icons/tiktok.svg',
    aspectRatio: 1.0,
    primaryColor: '#000000',
    displayName: 'TikTok',
  },
  paypal: {
    name: 'PayPal',
    logoUrl: '/assets/platform-logos/paypal-logo.svg',
    fallbackUrl: 'https://cdn.jsdelivr.net/gh/simple-icons/simple-icons@latest/icons/paypal.svg',
    aspectRatio: 3.8,
    primaryColor: '#00457C',
    displayName: 'PayPal',
  },
} as const;

export type PlatformKey = keyof typeof PLATFORM_CONFIGS;

interface PlatformLogoProps {
  platform: PlatformKey | string;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'custom';
  customHeight?: number; // Used when size='custom'
  className?: string;
  showFallback?: boolean; // Show colored square with initial if logo fails
  grayscale?: boolean; // Desaturate logo (for disabled states)
  onError?: () => void;
}

/**
 * PlatformLogo Component
 * Standardized platform logo rendering with automatic aspect ratio preservation,
 * fallback handling, and accessibility features
 */
export const PlatformLogo: React.FC<PlatformLogoProps> = ({
  platform,
  size = 'md',
  customHeight,
  className = '',
  showFallback = true,
  grayscale = false,
  onError,
}) => {
  const [logoError, setLogoError] = useState(false);
  const [useFallbackCdn, setUseFallbackCdn] = useState(false);

  // Size presets (height in pixels)
  const sizeMap = {
    xs: 12,
    sm: 16,
    md: 20,
    lg: 24,
    xl: 32,
    custom: customHeight || 20,
  };

  const height = sizeMap[size];

  // Normalize platform key (handle variations)
  const platformKey = (platform.toLowerCase().replace(/\s+/g, '-') as PlatformKey);
  const config = PLATFORM_CONFIGS[platformKey];

  // If platform not in config, use generic fallback
  if (!config) {
    console.warn(`Platform logo config not found for: ${platform}`);
    return (
      <div
        className={`inline-flex items-center justify-center rounded px-2 py-1 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 text-xs font-medium ${className}`}
        style={{ height: `${height}px` }}
        data-testid={`logo-fallback-${platform.toLowerCase()}`}
      >
        {platform}
      </div>
    );
  }

  const width = height * config.aspectRatio;

  // Handle logo load errors - three-tier fallback
  const handleError = () => {
    if (!useFallbackCdn && config.fallbackUrl) {
      // First tier failed, try CDN fallback
      setUseFallbackCdn(true);
    } else {
      // Both tiers failed, show colored square fallback
      setLogoError(true);
      onError?.();
    }
  };

  // Handle successful logo load - reset error state if CDN succeeds
  const handleLoad = () => {
    // If we successfully loaded after an error, clear the error state
    if (logoError) {
      setLogoError(false);
    }
  };

  // Reset all error states when platform changes
  useEffect(() => {
    setLogoError(false);
    setUseFallbackCdn(false);
  }, [platform]);

  // Determine which logo URL to use
  const logoSrc = useFallbackCdn ? config.fallbackUrl : config.logoUrl;

  // Fallback UI: Colored square with platform initial
  if (logoError && showFallback) {
    return (
      <div
        className={`inline-flex items-center justify-center rounded font-bold text-white ${className}`}
        style={{
          width: `${height}px`,
          height: `${height}px`,
          backgroundColor: config.primaryColor,
          fontSize: `${height * 0.5}px`,
        }}
        title={config.displayName}
        aria-label={config.displayName}
        data-testid={`logo-initial-${platformKey}`}
      >
        {config.displayName[0]}
      </div>
    );
  }

  return (
    <img
      src={logoSrc}
      alt={`${config.displayName} logo`}
      className={`object-contain ${grayscale ? 'grayscale' : ''} ${className}`}
      style={{
        width: `${width}px`,
        height: `${height}px`,
        maxWidth: '100%',
      }}
      onError={handleError}
      onLoad={handleLoad}
      loading="lazy"
      aria-label={config.displayName}
      data-testid={`logo-${platformKey}${useFallbackCdn ? '-cdn' : ''}`}
    />
  );
};

/**
 * Hook to get platform configuration
 */
export const usePlatformConfig = (platform: PlatformKey | string) => {
  const platformKey = platform.toLowerCase().replace(/\s+/g, '-') as PlatformKey;
  return PLATFORM_CONFIGS[platformKey] || null;
};
