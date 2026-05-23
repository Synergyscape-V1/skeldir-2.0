import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  EVIDENCE_HUB_DESCRIPTION,
  EVIDENCE_HUB_H1,
  evidenceHubBreadcrumbJsonLd,
  evidenceHubCollectionJsonLd,
} from "@/lib/schema/pageSchemas";
import { Footer } from "@/components/layout/Footer";
import { EVIDENCE_CATALOG, EVIDENCE_SLUGS } from "@/data/evidenceLibraryCatalog";

export const dynamic = "error";

export const metadata: Metadata = {
  title: `${EVIDENCE_HUB_H1} | Skeldir Resources`,
  description: EVIDENCE_HUB_DESCRIPTION,
  alternates: { canonical: canonicalUrl("/resources/evidence") },
  openGraph: {
    title: `${EVIDENCE_HUB_H1} | Skeldir Resources`,
    description: EVIDENCE_HUB_DESCRIPTION,
    url: canonicalUrl("/resources/evidence"),
  },
};

const CLUSTER_LINKS: { title: string; description: string; hrefs: { href: string; label: string }[] }[] = [
  {
    title: "Platform Discrepancies",
    description: "Pair-specific mechanisms (not generic blog copy).",
    hrefs: [
      { href: "/resources/evidence/meta-vs-stripe", label: "Meta vs Stripe" },
      { href: "/resources/evidence/google-ads-vs-shopify", label: "Google Ads vs Shopify" },
      { href: "/resources/evidence/tiktok-discrepancies", label: "TikTok" },
      { href: "/resources/evidence/pinterest-discrepancies", label: "Pinterest" },
      { href: "/resources/evidence/paypal-reconciliation", label: "PayPal" },
      { href: "/resources/evidence/woocommerce-reconciliation", label: "WooCommerce" },
    ],
  },
  {
    title: "Revenue Verification & Finance Audit",
    description: "Checklists and verification framing for operators.",
    hrefs: [
      { href: "/resources/evidence/shopify-reconciliation", label: "Shopify reconciliation" },
      { href: "/resources/evidence/finance-roas-audit-checklist", label: "Finance ROAS audit checklist" },
      { href: "/revenue-verification", label: "D5 — Revenue verification" },
    ],
  },
  {
    title: "Attribution, confidence, TrustEnvelope",
    description: "Deterministic substrate vs model layers; TrustEnvelope authority.",
    hrefs: [
      { href: "/resources/evidence/deterministic-attribution-methods", label: "Deterministic attribution methods" },
      {
        href: "/resources/evidence/deterministic-vs-probabilistic-confidence",
        label: "Deterministic vs probabilistic confidence",
      },
      { href: "/resources/evidence/trust-envelope-technical-spec", label: "TrustEnvelope technical spec (retrieval)" },
      { href: "/trust-envelope", label: "D5 — TrustEnvelope (canonical)" },
    ],
  },
  {
    title: "Benchmark Methodology & Related",
    description: "Honesty boundaries for PII claims, LLMs, and roadmap benchmarks.",
    hrefs: [
      { href: "/resources/evidence/privacy-no-pii-methodology", label: "Privacy / durable PII methodology" },
      { href: "/resources/evidence/ai-llm-explanation-boundary", label: "AI / LLM explanation boundary" },
      { href: "/resources/evidence/benchmark-methodology", label: "Benchmark methodology" },
      { href: "/ai-boundary", label: "D5 — AI boundary" },
    ],
  },
];

export default function EvidenceLibraryHubPage() {
  return (
    <div className="min-h-screen flex flex-col bg-white text-slate-900">
      <JsonLd data={[evidenceHubCollectionJsonLd(), evidenceHubBreadcrumbJsonLd()]} />
      <main className="flex-grow pt-20 pb-16">
        <div className="container mx-auto px-4 md:px-6 max-w-4xl">
          <header className="mb-12 pt-12 md:pt-16 lg:pt-20 border-b border-slate-200 pb-10">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
              Resources
            </p>
            <h1 className="text-3xl md:text-4xl font-semibold leading-tight mb-4">{EVIDENCE_HUB_H1}</h1>
            <p className="text-lg text-slate-700 leading-relaxed">{EVIDENCE_HUB_DESCRIPTION}</p>
            <p className="mt-6 text-sm text-slate-600">
              This hub is the D6 retrieval layer. Canonical proof definitions remain on D5 routes such as{" "}
              <Link className="underline" href="/methodology">
                /methodology
              </Link>
              ,{" "}
              <Link className="underline" href="/revenue-verification">
                /revenue-verification
              </Link>
              , and{" "}
              <Link className="underline" href="/discrepancy-taxonomy">
                /discrepancy-taxonomy
              </Link>
              .
            </p>
          </header>

          <div className="space-y-12">
            {CLUSTER_LINKS.map((cluster, idx) => {
              const hid = `evidence-cluster-${idx}`;
              return (
              <section
                key={cluster.title}
                aria-labelledby={hid}
                className="scroll-mt-24"
              >
                <h2
                  id={hid}
                  className="text-2xl font-semibold text-slate-900 mb-2"
                >
                  {cluster.title}
                </h2>
                <p className="text-slate-600 mb-4">{cluster.description}</p>
                <ul className="grid sm:grid-cols-2 gap-3">
                  {cluster.hrefs.map((l) => (
                    <li key={l.href}>
                      <Link
                        href={l.href}
                        className="block rounded-lg border border-slate-200 px-4 py-3 hover:border-slate-400 transition-colors"
                      >
                        <span className="font-medium text-slate-900">{l.label}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            );
            })}

            <section aria-labelledby="matrix-heading" className="border-t border-slate-200 pt-10">
              <h2 id="matrix-heading" className="text-2xl font-semibold mb-3">
                Buyer query map
              </h2>
              <p className="text-slate-700 mb-4">
                Machine-readable matrices live at repo root:{" "}
                <code className="text-xs bg-slate-100 px-2 py-1 rounded">BUYER_QUERY_CONTENT_MATRIX.md</code> and{" "}
                <code className="text-xs bg-slate-100 px-2 py-1 rounded">discoverability.buyer-query-matrix.json</code>.
              </p>
              <p className="text-slate-600 text-sm">
                Evidence routes in this build: {EVIDENCE_SLUGS.length} pages under{" "}
                <code className="text-xs bg-slate-100 px-1 rounded">/resources/evidence/&lt;slug&gt;</code>.
              </p>
            </section>

            <section aria-labelledby="all-pages-heading">
              <h2 id="all-pages-heading" className="text-2xl font-semibold mb-4">
                All evidence pages
              </h2>
              <ul className="columns-1 sm:columns-2 gap-x-8 text-sm space-y-2">
                {EVIDENCE_SLUGS.map((slug) => {
                  const def = EVIDENCE_CATALOG[slug];
                  return (
                    <li key={slug}>
                      <Link className="underline text-slate-900" href={def.routePath}>
                        {def.h1}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </section>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
