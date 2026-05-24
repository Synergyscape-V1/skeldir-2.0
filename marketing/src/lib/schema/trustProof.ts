import { canonicalUrl, SITE_ORIGIN } from "@/lib/crawlUrls";
import { SKELDIR_ORGANIZATION_ID, SKELDIR_WEBSITE_ID } from "@/lib/schema/entity";

/**
 * D5 trust proof JSON-LD.
 *
 * Conservatively emits WebPage + BreadcrumbList only. We intentionally
 * avoid TechArticle / SoftwareSourceCode / FAQPage so structured data
 * never overclaims the visible proof content.
 */
export function trustProofWebPageJsonLd(
  path: string,
  args: { name: string; description: string },
): Record<string, unknown> {
  const url = canonicalUrl(path);
  return {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "@id": `${url}#webpage`,
    url,
    name: args.name,
    description: args.description,
    isPartOf: { "@id": SKELDIR_WEBSITE_ID },
    about: { "@id": SKELDIR_ORGANIZATION_ID },
  };
}

export function trustProofBreadcrumbJsonLd(
  path: string,
  args: { label: string },
): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "Home",
        item: `${SITE_ORIGIN}/`,
      },
      {
        "@type": "ListItem",
        position: 2,
        name: args.label,
        item: canonicalUrl(path),
      },
    ],
  };
}
