import { canonicalUrl, SITE_ORIGIN } from "@/lib/crawlUrls";
import type { ArticleMetadata } from "@/data/articlesData";
import { getArticleSeoDescription } from "@/data/articleSeo";
import {
  SKELDIR_ORGANIZATION_ID,
  SKELDIR_ORGANIZATION_NAME,
  SKELDIR_WEBSITE_ID,
} from "@/lib/schema/entity";

/** Must match visible `<h1>` on the product page (single-line mobile + aria). */
export const PRODUCT_PAGE_HEADLINE =
  "The Revenue Verification Infrastructure Your Ad Stack Has Always Been Missing" as const;

/** Must match the first hero `<p>` on the product page. */
export const PRODUCT_PAGE_LEAD_DESCRIPTION =
  "Stop guessing where your budget works. Skeldir connects all ad platforms, reconciles claimed revenue vs. verified revenue, and shows exactly which channels drive real growth." as const;

export function softwareApplicationJsonLd(): Record<string, unknown> {
  const url = canonicalUrl("/product");
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "@id": `${url}#software`,
    name: SKELDIR_ORGANIZATION_NAME,
    alternateName: PRODUCT_PAGE_HEADLINE,
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
    url,
    description: PRODUCT_PAGE_LEAD_DESCRIPTION,
    offers: {
      "@type": "Offer",
      price: "199",
      priceCurrency: "USD",
      priceValidUntil: "2027-12-31",
      category: "subscription",
    },
    publisher: { "@id": SKELDIR_ORGANIZATION_ID },
  };
}

/** Must match `PricingHero` H1 and lead paragraph. */
export const PRICING_PAGE_H1 = "One platform for marketing, finance, and leadership." as const;
export const PRICING_PAGE_DESCRIPTION =
  "Whether you're a growing e-commerce brand, established retailer, or multi-client agency, Skeldir is designed to eliminate budget waste and deliver attribution clarity." as const;

/** Resources hub — must match `ResourcesPageClient` H1 and intro paragraph. */

export const RESOURCES_HUB_H1 = "What's new at Skeldir?" as const;
export const RESOURCES_HUB_DESCRIPTION =
  "Learn how to navigate attribution discrepancies, understand ROAS ranges, and defend budget shifts with evidence-based frameworks." as const;

export function collectionPageResourcesJsonLd(): Record<string, unknown> {
  const url = canonicalUrl("/resources");
  return {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "@id": `${url}#collection`,
    url,
    name: RESOURCES_HUB_H1,
    description: RESOURCES_HUB_DESCRIPTION,
    isPartOf: { "@id": SKELDIR_WEBSITE_ID },
    publisher: { "@id": SKELDIR_ORGANIZATION_ID },
  };
}

export function breadcrumbJsonLd(items: { name: string; path: string }[]): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((it, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: it.name,
      item: canonicalUrl(it.path),
    })),
  };
}

export function resourcesHubBreadcrumbJsonLd(): Record<string, unknown> {
  return breadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Resources", path: "/resources" },
  ]);
}

/** Evidence library hub (CollectionPage; keep in sync with `resources/evidence/page.tsx` H1 + meta). */
export const EVIDENCE_HUB_H1 = "Evidence Library" as const;
export const EVIDENCE_HUB_DESCRIPTION =
  "Short explainers for finance and growth teams: platform versus commerce discrepancies, revenue verification, ROAS audit discipline, TrustEnvelope concepts at a high level, attribution limits, confidence semantics, privacy boundaries, and benchmark limitations. Each topic links to our public methodology pages so definitions stay consistent." as const;

export function evidenceHubCollectionJsonLd(): Record<string, unknown> {
  const url = canonicalUrl("/resources/evidence");
  return {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "@id": `${url}#collection`,
    url,
    name: EVIDENCE_HUB_H1,
    description: EVIDENCE_HUB_DESCRIPTION,
    isPartOf: { "@id": SKELDIR_WEBSITE_ID },
    publisher: { "@id": SKELDIR_ORGANIZATION_ID },
  };
}

export function evidenceHubBreadcrumbJsonLd(): Record<string, unknown> {
  return breadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Resources", path: "/resources" },
    { name: "Evidence Library", path: "/resources/evidence" },
  ]);
}

export function evidenceWebPageJsonLd(
  routePath: string,
  args: { name: string; description: string },
): Record<string, unknown> {
  const url = canonicalUrl(routePath);
  return {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "@id": `${url}#webpage`,
    url,
    name: args.name,
    description: args.description,
    isPartOf: { "@id": SKELDIR_WEBSITE_ID },
    publisher: { "@id": SKELDIR_ORGANIZATION_ID },
  };
}

export function evidenceDetailBreadcrumbJsonLd(
  routePath: string,
  pageTitle: string,
): Record<string, unknown> {
  return breadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Resources", path: "/resources" },
    { name: "Evidence Library", path: "/resources/evidence" },
    { name: pageTitle, path: routePath },
  ]);
}

export function articleBreadcrumbJsonLd(slug: string, articleTitle: string): Record<string, unknown> {
  return breadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Resources", path: "/resources" },
    { name: articleTitle, path: `/resources/${slug}` },
  ]);
}

export function articleJsonLd(article: ArticleMetadata, slug: string): Record<string, unknown> {
  const url = canonicalUrl(`/resources/${slug}`);
  const imageUrl = `${SITE_ORIGIN}${article.heroImagePath}`;
  const authorName = article.author ?? "Amulya Puri";
  const description = getArticleSeoDescription(slug) ?? article.excerpt;

  return {
    "@context": "https://schema.org",
    "@type": "Article",
    "@id": `${url}#article`,
    headline: article.title,
    description,
    image: imageUrl,
    datePublished: article.publishDate,
    author: {
      "@type": "Person",
      name: authorName,
    },
    publisher: { "@id": SKELDIR_ORGANIZATION_ID },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": `${url}#webpage`,
    },
    url,
    isPartOf: { "@id": SKELDIR_WEBSITE_ID },
  };
}
