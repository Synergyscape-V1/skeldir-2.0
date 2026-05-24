import type { ReactNode } from "react";
import { Footer } from "@/components/layout/Footer";
import {
  TableOfContents,
  type TOCItem,
} from "@/components/article/TableOfContents";

/**
 * D5 trust proof page layout.
 *
 * Renders a fully static, retrievable HTML page with:
 *   - visible H1 (no aria-only headings),
 *   - optional meta strip showing owner and status,
 *   - table of contents (same pattern as /resources articles),
 *   - body sections,
 *   - explicit Limitations section (required by D5),
 *   - shared footer for legal/proof link parity.
 *
 * Every D5 page that uses this component therefore satisfies the
 * baseline checks in scripts/discoverability/lib/d5-trust-proof.mjs
 * (review-status token, static body, no Loading
 * shell, H1 present).
 */
export interface TrustProofPageSection {
  id: string;
  heading: string;
  body: ReactNode;
  /** Optional nested TOC entries (h3 anchors in section body). */
  tocChildren?: { id: string; title: string }[];
}

export interface TrustProofPageMeta {
  owner: string;
  status:
    | "operator_approved"
    | "technical_disclosure_only"
    | "legal_review_required"
    | "blocked_missing_content";
  /** Shown in the page meta strip (e.g. last reviewed). */
  lastReviewed: string;
  notes?: string;
}

export interface TrustProofPageProps {
  headline: string;
  lede: string;
  meta: TrustProofPageMeta;
  sections: TrustProofPageSection[];
  limitations: ReactNode;
}

const LIMITATIONS_TOC_ID = "limitations";

export function buildTrustProofTocItems(
  sections: TrustProofPageSection[]
): TOCItem[] {
  const items: TOCItem[] = sections.map((section) => ({
    id: section.id,
    title: section.heading,
    level: 2,
    children: section.tocChildren?.map((child) => ({
      id: child.id,
      title: child.title,
      level: 3,
    })),
  }));

  items.push({
    id: LIMITATIONS_TOC_ID,
    title: "Limitations",
    level: 2,
  });

  return items;
}

export function TrustProofPage(props: TrustProofPageProps) {
  const { headline, lede, meta, sections, limitations } = props;
  const tocItems = buildTrustProofTocItems(sections);

  return (
    <div className="min-h-screen flex flex-col bg-white text-slate-900">
      <main className="flex-grow pt-20 pb-16">
        <div className="container mx-auto px-4 md:px-6">
          <header className="max-w-3xl mx-auto mb-10 border-b border-slate-200 pb-8 pt-12 md:pt-16 lg:pt-20">
            <h1 className="text-3xl md:text-4xl font-semibold leading-tight mb-4">
              {headline}
            </h1>
            <p className="text-lg text-slate-700 leading-relaxed mb-6">{lede}</p>
            <dl
              className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2 text-sm"
              aria-label="Proof page metadata"
            >
              <div>
                <dt className="font-semibold text-slate-500 uppercase tracking-wide text-xs">
                  Owner
                </dt>
                <dd>{meta.owner}</dd>
              </div>
              <div>
                <dt className="font-semibold text-slate-500 uppercase tracking-wide text-xs">
                  Status
                </dt>
                <dd>
                  <code className="text-xs bg-slate-100 px-2 py-1 rounded">
                    {meta.status}
                  </code>
                </dd>
              </div>
            </dl>
            {meta.notes ? (
              <p className="mt-6 text-xs text-slate-500 leading-relaxed">
                {meta.notes}
              </p>
            ) : null}
          </header>

          <div className="flex flex-col xl:flex-row gap-8 xl:gap-16 max-w-7xl mx-auto">
            <aside className="xl:w-72 xl:flex-shrink-0 order-2 xl:order-1">
              <TableOfContents items={tocItems} />
            </aside>

            <article className="flex-1 max-w-3xl order-1 xl:order-2">
              <div className="space-y-12">
                {sections.map((section) => (
                  <section
                    key={section.id}
                    id={section.id}
                    className="scroll-mt-24"
                    aria-labelledby={`${section.id}-heading`}
                  >
                    <h2
                      id={`${section.id}-heading`}
                      className="text-xl md:text-2xl font-semibold mb-4"
                    >
                      {section.heading}
                    </h2>
                    <div className="text-base text-slate-700 leading-relaxed space-y-4">
                      {section.body}
                    </div>
                  </section>
                ))}

                <section
                  id={LIMITATIONS_TOC_ID}
                  className="scroll-mt-24 border-t border-slate-200 pt-10"
                  aria-labelledby="limitations-heading"
                >
                  <h2
                    id="limitations-heading"
                    className="text-xl md:text-2xl font-semibold mb-4"
                  >
                    Limitations
                  </h2>
                  <div className="text-base text-slate-700 leading-relaxed space-y-4">
                    {limitations}
                  </div>
                </section>
              </div>
            </article>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
