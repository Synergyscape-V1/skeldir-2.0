import React from "react";

/** Shared platform logo assets, aligned with CommandCenter PlatformIcon and TopBar,
 * rendered with consistent sizing (no background chip).
 */
const PLATFORM_ICONS: Record<string, { src: string; alt: string }> = {
  google_ads: { src: "/assets/platform-icons/google-ads.svg", alt: "Google Ads" },
  meta: { src: "/assets/platform-icons/meta-ads.svg", alt: "Meta Ads" },
  tiktok: { src: "/assets/platform-icons/tiktok-ads.svg", alt: "TikTok Ads" },
  linkedin: { src: "/assets/platform-icons/linkedin-ads.svg", alt: "LinkedIn Ads" },
  pinterest: { src: "/assets/platform-icons/pinterest-ads.svg", alt: "Pinterest Ads" },
  snapchat: { src: "/assets/platform-icons/snapchat-ads.svg", alt: "Snapchat Ads" },
  klaviyo: { src: "/assets/platform-icons/klaviyo.svg", alt: "Klaviyo" },
};

const PLATFORM_SCALE: Record<string, number> = {
  stripe: 1.1,
  klaviyo: 0.84,
};

export default function PlatformIcon({ platform, size = 16 }: { platform: string; size?: number }) {
  const meta = PLATFORM_ICONS[platform];
  if (!meta) return null;

  const diameter = size;
  const baseScale = 0.95;
  const platformScale = PLATFORM_SCALE[platform] ?? 1;
  const innerSize = Math.round(diameter * baseScale * platformScale);

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: diameter,
        height: diameter,
        flexShrink: 0,
      }}
    >
      <img
        src={meta.src}
        alt={meta.alt}
        width={innerSize}
        height={innerSize}
        style={{
          display: "block",
          flexShrink: 0,
          objectFit: "contain",
          ...(platform === "klaviyo" ? { maxWidth: "100%", maxHeight: "100%" } : {}),
        }}
        loading="lazy"
        decoding="async"
      />
    </span>
  );
}
