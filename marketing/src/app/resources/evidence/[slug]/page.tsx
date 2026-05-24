import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { JsonLd } from "@/components/schema/JsonLd";
import { EvidenceLibraryDocument } from "@/components/discoverability/EvidenceLibraryDocument";
import { canonicalUrl } from "@/lib/crawlUrls";
import { evidenceDetailBreadcrumbJsonLd, evidenceWebPageJsonLd } from "@/lib/schema/pageSchemas";
import { EVIDENCE_SLUGS, getEvidenceDefinition } from "@/data/evidenceLibraryCatalog";

export const dynamic = "error";

export function generateStaticParams() {
  return EVIDENCE_SLUGS.map((slug) => ({ slug }));
}

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const def = getEvidenceDefinition(slug);
  if (!def) return {};
  return {
    title: `${def.h1} | Skeldir Evidence Library`,
    description: def.metaDescription,
    alternates: { canonical: canonicalUrl(def.routePath) },
    openGraph: {
      title: `${def.h1} | Skeldir Evidence Library`,
      description: def.metaDescription,
      url: canonicalUrl(def.routePath),
    },
  };
}

export default async function EvidenceDetailPage({ params }: Props) {
  const { slug } = await params;
  const def = getEvidenceDefinition(slug);
  if (!def) notFound();

  return (
    <>
      <JsonLd
        data={[
          evidenceWebPageJsonLd(def.routePath, {
            name: def.h1,
            description: def.metaDescription,
          }),
          evidenceDetailBreadcrumbJsonLd(def.routePath, def.h1),
        ]}
      />
      <EvidenceLibraryDocument page={def} />
    </>
  );
}
