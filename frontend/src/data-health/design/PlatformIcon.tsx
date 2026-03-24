import React from "react";

/**
 * Canonical platform logo assets — same SVGs as Command Center, Channel Comparison,
 * and data-health core constants. Single source of truth for brand-accurate icons,
 * visually normalized for consistent sizing.
 */
const PLATFORM_ICONS: Record<string, { src: string; alt: string }> = {
  stripe: { src: "/assets/platform-icons/stripe.svg", alt: "Stripe" },
  paypal: { src: "/assets/platform-icons/paypal.svg", alt: "PayPal" },
  googleads: { src: "/assets/platform-icons/google-ads.svg", alt: "Google Ads" },
  google_ads: { src: "/assets/platform-icons/google-ads.svg", alt: "Google Ads" },
  meta: { src: "/assets/platform-icons/meta-ads.svg", alt: "Meta" },
  meta_ads: { src: "/assets/platform-icons/meta-ads.svg", alt: "Meta Ads" },
  tiktok: { src: "/assets/platform-icons/tiktok-ads.svg", alt: "TikTok" },
  tiktok_ads: { src: "/assets/platform-icons/tiktok-ads.svg", alt: "TikTok Ads" },
  linkedin: { src: "/assets/platform-icons/linkedin-ads.svg", alt: "LinkedIn" },
  linkedin_ads: { src: "/assets/platform-icons/linkedin-ads.svg", alt: "LinkedIn Ads" },
  /** Meta / Facebook family */
  facebook: { src: "/assets/platform-icons/meta-ads.svg", alt: "Facebook" },
  snapchat: { src: "/assets/platform-icons/snapchat-ads.svg", alt: "Snapchat" },
  klaviyo: { src: "/assets/platform-icons/klaviyo.svg", alt: "Klaviyo" },
};

const PLATFORM_SCALE: Record<string, number> = {
  stripe: 1.1,
  /** Icon mark reads larger than circular logos at same px — scale down */
  klaviyo: 0.84,
};

export function PlatformIcon({ platform, size = 32 }: { platform: string; size?: number }) {
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
