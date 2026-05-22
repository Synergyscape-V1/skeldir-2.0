import entityProfiles from "../../../entity-profile-registry.json";
import { canonicalUrl, SITE_ORIGIN } from "@/lib/crawlUrls";
import { SITE_DESCRIPTION, SITE_DOCUMENT_TITLE } from "@/lib/siteMetadata";

/** Stable @id fragments — must use SITE_ORIGIN from crawl URL authority (D2). */
export const SKELDIR_ORGANIZATION_ID = `${SITE_ORIGIN}/#organization` as const;
export const SKELDIR_WEBSITE_ID = `${SITE_ORIGIN}/#website` as const;

export const SKELDIR_ORGANIZATION_NAME = "Skeldir" as const;

/**
 * Canonical public definition (Phase D4). Used for Organization.description and governance docs.
 */
export const SKELDIR_CANONICAL_DEFINITION =
  "Skeldir is deterministic revenue-verification and attribution infrastructure that reconciles platform-reported revenue against verified commerce/payment evidence and exposes audit-ready financial truth through TrustEnvelopes." as const;

/** Shorter org description for JSON-LD (visible-aligned; first sentence of canonical definition). */
export const SKELDIR_ORGANIZATION_DESCRIPTION =
  "Skeldir is deterministic revenue-verification and attribution infrastructure that reconciles platform-reported revenue against verified commerce and payment evidence." as const;

export const SKELDIR_LOGO_URL = `${SITE_ORIGIN}/images/skeldir-logo-black.png` as const;

/** Verified `sameAs` URLs only — sourced from `entity-profile-registry.json`. */
export const VERIFIED_SAME_AS_URLS: readonly string[] = entityProfiles.sameAs;

export function organizationJsonLd(): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": SKELDIR_ORGANIZATION_ID,
    name: SKELDIR_ORGANIZATION_NAME,
    url: `${SITE_ORIGIN}/`,
    logo: SKELDIR_LOGO_URL,
    description: SKELDIR_ORGANIZATION_DESCRIPTION,
    ...(VERIFIED_SAME_AS_URLS.length > 0 ? { sameAs: [...VERIFIED_SAME_AS_URLS] } : {}),
  };
}

export function webSiteJsonLd(): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": SKELDIR_WEBSITE_ID,
    url: `${SITE_ORIGIN}/`,
    name: SKELDIR_ORGANIZATION_NAME,
    description: SITE_DESCRIPTION,
    publisher: { "@id": SKELDIR_ORGANIZATION_ID },
    inLanguage: "en-US",
  };
}

export function webPageJsonLd(path: string, overrides: { name: string; description: string }): Record<string, unknown> {
  const url = canonicalUrl(path);
  return {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "@id": `${url}#webpage`,
    url,
    name: overrides.name,
    description: overrides.description,
    isPartOf: { "@id": SKELDIR_WEBSITE_ID },
    about: { "@id": SKELDIR_ORGANIZATION_ID },
  };
}
