/**
 * Platform / Channel SVG Logo Components
 *
 * Sourced from official brand guidelines and SimpleIcons (https://simpleicons.org).
 * All logos are SVG React components, theme-safe, token-aligned.
 *
 * PROVENANCE:
 * - Google Ads: Google Brand Resource Center — https://about.google/brand-resource-center/
 * - Meta (Facebook): Meta Brand Resources — https://about.meta.com/brand/resources/
 * - TikTok: TikTok Brand Resources — https://www.tiktok.com/brand/
 * - Pinterest: Pinterest Brand Guidelines — https://business.pinterest.com/brand-guidelines/
 * - LinkedIn: LinkedIn Brand Guidelines — https://brand.linkedin.com/
 * - Email (generic): Lucide icon set (ISC License) — https://lucide.dev/
 *
 * LICENSE NOTES:
 * - Platform logos are trademarks of their respective companies.
 * - Usage limited to channel identification within Skeldir's attribution interface.
 * - SimpleIcons paths licensed under CC0 1.0 Universal.
 * - Lucide icons licensed under ISC License.
 */

import React from 'react';
import { MetaAdsLogo } from '@/pages/channel-detail/components/MetaAdsLogo';

interface LogoProps {
  size?: number;
  className?: string;
}

export const GoogleAdsLogo: React.FC<LogoProps> = ({ size = 20, className }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-label="Google Ads"
    role="img"
  >
    <path
      d="M3.2 14.6L9.5 3.6c.8-1.4 2.5-1.9 3.9-1.1 1.4.8 1.9 2.5 1.1 3.9L8.2 17.4c-.8 1.4-2.5 1.9-3.9 1.1-1.4-.8-1.9-2.5-1.1-3.9z"
      fill="#FBBC04"
    />
    <path
      d="M14.5 14.6l6.3-11c.8-1.4 2.5-1.9 3.9-1.1 1.4.8 1.9 2.5 1.1 3.9l-6.3 11c-.8 1.4-2.5 1.9-3.9 1.1-1.4-.8-1.9-2.5-1.1-3.9z"
      fill="#4285F4"
      transform="translate(-5)"
    />
    <circle cx="5.4" cy="19.2" r="3" fill="#34A853" />
  </svg>
);

/** Meta Ads: re-export shared infinity-loop logo (single source of truth). */
export { MetaAdsLogo };

export const TikTokAdsLogo: React.FC<LogoProps> = ({ size = 20, className }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-label="TikTok Ads"
    role="img"
  >
    <path
      d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.8.1V9.01a6.27 6.27 0 00-.8-.05 6.34 6.34 0 00-6.34 6.34 6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.33-6.34V8.69a8.21 8.21 0 004.77 1.52V6.76a4.83 4.83 0 01-1-.07z"
      fill="currentColor"
    />
  </svg>
);

export const PinterestAdsLogo: React.FC<LogoProps> = ({ size = 20, className }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-label="Pinterest Ads"
    role="img"
  >
    <path
      d="M12 0C5.373 0 0 5.373 0 12c0 5.084 3.163 9.426 7.627 11.174-.105-.949-.2-2.405.042-3.441.218-.937 1.407-5.965 1.407-5.965s-.359-.719-.359-1.782c0-1.668.967-2.914 2.171-2.914 1.023 0 1.518.769 1.518 1.69 0 1.029-.655 2.568-.994 3.995-.283 1.194.599 2.169 1.777 2.169 2.133 0 3.772-2.249 3.772-5.495 0-2.873-2.064-4.882-5.012-4.882-3.414 0-5.418 2.561-5.418 5.207 0 1.031.397 2.138.893 2.738a.36.36 0 01.083.345c-.091.379-.293 1.194-.333 1.361-.052.22-.174.267-.401.161-1.499-.698-2.436-2.889-2.436-4.649 0-3.785 2.75-7.262 7.929-7.262 4.163 0 7.398 2.967 7.398 6.931 0 4.136-2.607 7.464-6.227 7.464-1.216 0-2.359-.632-2.75-1.378l-.748 2.853c-.271 1.043-1.002 2.35-1.492 3.146C9.57 23.812 10.763 24 12 24c6.627 0 12-5.373 12-12S18.627 0 12 0z"
      fill="#E60023"
    />
  </svg>
);

export const LinkedInAdsLogo: React.FC<LogoProps> = ({ size = 20, className }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-label="LinkedIn Ads"
    role="img"
  >
    <path
      d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"
      fill="#0A66C2"
    />
  </svg>
);

export const EmailChannelLogo: React.FC<LogoProps> = ({ size = 20, className }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-label="Email Channel"
    role="img"
  >
    <rect width="20" height="16" x="2" y="4" rx="2" />
    <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
  </svg>
);

/**
 * Lookup map: platform string → Logo component
 */
export const PLATFORM_LOGO_MAP: Record<string, React.FC<LogoProps>> = {
  google_ads: GoogleAdsLogo,
  facebook_ads: MetaAdsLogo,
  tiktok_ads: TikTokAdsLogo,
  pinterest_ads: PinterestAdsLogo,
  linkedin_ads: LinkedInAdsLogo,
  email: EmailChannelLogo,
};

export function getPlatformLogo(platform: string): React.FC<LogoProps> {
  return PLATFORM_LOGO_MAP[platform] ?? EmailChannelLogo;
}
