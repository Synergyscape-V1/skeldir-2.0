import type { ReactNode } from "react";
import { Footer } from "@/components/layout/Footer";

/**
 * D5 legal placeholder page.
 *
 * Used by /privacy, /terms, /gdpr while operator/legal copy is being
 * prepared. The page is intentionally minimal but:
 *   - always has a visible H1,
 *   - always carries an explicit `legal_review_required` status badge,
 *   - always names an owner and a last-reviewed date,
 *   - never invents legal guarantees (no SOC 2, no GDPR-compliant, no
 *     blanket privacy promises),
 *   - is rendered fully static so a crawler sees the disclosure.
 *
 * The route itself sets `metadata.robots = { index: false }` until legal
 * copy is approved. The static disclosure here is what protects against
 * the audit's "footer link 404s to /privacy" failure mode while
 * preserving the "no invented legal claims" rule.
 */
export interface LegalPlaceholderPageProps {
  headline: string;
  description: string;
  contactEmail: string;
  owner: string;
  lastReviewed: string;
  body: ReactNode;
}

export function LegalPlaceholderPage(props: LegalPlaceholderPageProps) {
  const { headline, description, contactEmail, owner, lastReviewed, body } = props;
  return (
    <div className="min-h-screen flex flex-col bg-white text-slate-900">
      <main className="flex-grow px-6 pt-20 pb-16 max-w-2xl mx-auto w-full">
        <header className="mb-8 border-b border-slate-200 pb-6">
          <p className="text-xs uppercase tracking-widest text-slate-500 mb-3">
            Legal surface
          </p>
          <h1 className="text-3xl font-semibold mb-3">{headline}</h1>
          <p className="text-slate-700 leading-relaxed mb-5">{description}</p>
          <dl
            className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2 text-sm"
            aria-label="Legal placeholder metadata"
          >
            <div>
              <dt className="font-semibold text-slate-500 uppercase tracking-wide text-xs">
                Owner
              </dt>
              <dd>{owner}</dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-500 uppercase tracking-wide text-xs">
                Status
              </dt>
              <dd>
                <code className="text-xs bg-amber-100 text-amber-900 px-2 py-1 rounded">
                  legal_review_required
                </code>
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-500 uppercase tracking-wide text-xs">
                Last reviewed
              </dt>
              <dd>
                <time dateTime={lastReviewed}>{lastReviewed}</time>
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-500 uppercase tracking-wide text-xs">
                Indexing
              </dt>
              <dd>
                <code className="text-xs bg-slate-100 px-2 py-1 rounded">
                  noindex
                </code>{" "}
                until approved copy is published
              </dd>
            </div>
          </dl>
        </header>

        <section
          id="status-disclosure"
          aria-labelledby="status-disclosure-heading"
          className="space-y-4 text-slate-700 leading-relaxed"
        >
          <h2 id="status-disclosure-heading" className="text-xl font-semibold">
            Why this page is a placeholder
          </h2>
          {body}
          <p>
            We will not publish legal language we have not had reviewed by
            operator and legal counsel. The page exists at this URL so that
            footer and book-demo links resolve to a real, static disclosure
            rather than to a 404, while the approved text is being prepared.
          </p>
          <p>
            For questions in the interim, contact{" "}
            <a className="underline" href={`mailto:${contactEmail}`}>
              {contactEmail}
            </a>
            .
          </p>
        </section>
      </main>
      <Footer />
    </div>
  );
}
