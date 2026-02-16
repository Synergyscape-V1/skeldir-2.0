/**
 * Channel Platform Logo Map
 *
 * Keyed by ChannelPlatform identifiers from shared-types.
 * All logos render monochrome via currentColor — theme-safe for light/dark.
 * Unknown platforms fall back to a generic link icon.
 */
import type { ComponentType } from 'react';
import { MetaLogo } from './MetaLogo';
import { GoogleLogo } from './GoogleLogo';
import { TikTokLogo } from './TikTokLogo';
import { LinkedInLogo } from './LinkedInLogo';
import { PinterestLogo } from './PinterestLogo';
import { SnapchatLogo } from './SnapchatLogo';
import { TwitterLogo } from './TwitterLogo';
import { FallbackLogo } from './FallbackLogo';

export interface LogoProps {
  className?: string;
  size?: number;
}

export const channelLogoMap: Record<string, ComponentType<LogoProps>> = {
  meta: MetaLogo,
  google: GoogleLogo,
  tiktok: TikTokLogo,
  linkedin: LinkedInLogo,
  pinterest: PinterestLogo,
  snapchat: SnapchatLogo,
  twitter: TwitterLogo,
};

/** Get logo component for a platform, with fallback for unknown */
export function getChannelLogo(platform: string): ComponentType<LogoProps> {
  return channelLogoMap[platform] ?? FallbackLogo;
}

export { MetaLogo, GoogleLogo, TikTokLogo, LinkedInLogo, PinterestLogo, SnapchatLogo, TwitterLogo, FallbackLogo };
