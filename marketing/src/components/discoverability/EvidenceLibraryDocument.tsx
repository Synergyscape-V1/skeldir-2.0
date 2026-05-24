import type { ReactNode } from "react";
import Link from "next/link";
import { Footer } from "@/components/layout/Footer";
import type { EvidencePageDefinition } from "@/types/evidenceLibrary";

/** Renders `[[Label|/path]]` as internal links; keeps copy in plain strings for the catalog. */
export function renderEvidenceRich(text: string): ReactNode {
  const re = /\[\[([^|\]]+)\|([^\]]+)\]\]/g;
  const out: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      out.push(<span key={`t-${key++}`}>{text.slice(last, m.index)}</span>);
    }
    out.push(
      <Link key={`l-${key++}`} className="underline text-slate-900" href={m[2]}>
        {m[1]}
      </Link>,
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    out.push(<span key={`t-${key++}`}>{text.slice(last)}</span>);
  }
  return out.length ? out : text;
}

function RichParagraphs({ body }: { body: string }) {
  const blocks = body.split(/\n{2,}/).map((b) => b.trim()).filter(Boolean);
  return (
    <div className="space-y-4">
      {blocks.map((b, i) => (
        <p key={i} className="text-base text-slate-700 leading-relaxed">
          {renderEvidenceRich(b)}
        </p>
      ))}
    </div>
  );
}

export function EvidenceLibraryDocument(props: { page: EvidencePageDefinition }) {
  const { page } = props;
  return (
    <div className="min-h-screen flex flex-col bg-white text-slate-900">
      <main className="flex-grow pt-20 pb-16">
        <div className="container mx-auto px-4 md:px-6 max-w-3xl">
          <header className="mb-8 border-b border-slate-200 pb-6 pt-12 md:pt-16 lg:pt-20">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
              Evidence Library
            </p>
            <h1 className="text-3xl md:text-4xl font-semibold leading-tight">{page.h1}</h1>
          </header>

          <article className="space-y-12">
            <section id="bottom-line" aria-labelledby="bottom-line-heading" className="scroll-mt-24">
              <h2 id="bottom-line-heading" className="text-xl md:text-2xl font-semibold mb-4">
                Bottom line
              </h2>
              <RichParagraphs body={page.bluf} />
            </section>

            <section id="key-facts" aria-labelledby="key-facts-heading" className="scroll-mt-24">
              <h2 id="key-facts-heading" className="text-xl md:text-2xl font-semibold mb-4">
                Key Facts
              </h2>
              <ul className="list-disc pl-6 space-y-2 text-slate-700">
                {page.keyFacts.map((f, i) => (
                  <li key={i}>{renderEvidenceRich(f)}</li>
                ))}
              </ul>
            </section>

            <section id="claims-and-evidence" aria-labelledby="claims-evidence-heading" className="scroll-mt-24">
              <h2 id="claims-evidence-heading" className="text-xl md:text-2xl font-semibold mb-4">
                Claims and evidence
              </h2>
              <div className="overflow-x-auto border border-slate-200 rounded-lg">
                <table className="min-w-full text-sm text-left">
                  <thead className="bg-slate-100 text-slate-800">
                    <tr>
                      <th className="px-4 py-3 font-semibold">Claim</th>
                      <th className="px-4 py-3 font-semibold">Evidence / where Skeldir grounds it</th>
                    </tr>
                  </thead>
                  <tbody>
                    {page.claimRows.map((row, i) => (
                      <tr key={i} className="border-t border-slate-200 align-top">
                        <td className="px-4 py-3 text-slate-800">{renderEvidenceRich(row.claim)}</td>
                        <td className="px-4 py-3 text-slate-700">{renderEvidenceRich(row.evidence)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section
              id="evidence-metadata"
              aria-labelledby="evidence-metadata-heading"
              className="scroll-mt-24"
            >
              <h2 id="evidence-metadata-heading" className="sr-only">
                Evidence metadata
              </h2>
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2 text-sm border border-slate-100 rounded-lg p-4 bg-slate-50">
                <div>
                  <dt className="font-semibold text-slate-500 uppercase tracking-wide text-xs">Owner</dt>
                  <dd>{page.owner}</dd>
                </div>
                <div>
                  <dt className="font-semibold text-slate-500 uppercase tracking-wide text-xs">Status</dt>
                  <dd>
                    <code className="text-xs bg-white px-2 py-1 rounded border border-slate-200">
                      {page.disclosureStatus}
                    </code>
                  </dd>
                </div>
              </dl>
            </section>

            <section id="capability-status" aria-labelledby="capability-status-heading" className="scroll-mt-24">
              <h2 id="capability-status-heading" className="text-xl md:text-2xl font-semibold mb-4">
                Capability status
              </h2>
              <ul className="space-y-2 text-slate-700">
                {page.capabilityRows.map((r, i) => (
                  <li key={i}>
                    <span className="font-medium text-slate-900">{r.label}:</span> {r.state}
                  </li>
                ))}
              </ul>
            </section>

            <section id="how-skeldir-treats" aria-labelledby="how-skeldir-treats-heading" className="scroll-mt-24">
              <h2 id="how-skeldir-treats-heading" className="text-xl md:text-2xl font-semibold mb-4">
                How Skeldir Treats This
              </h2>
              <RichParagraphs body={page.howSkeldirTreats} />
            </section>

            <section id="methodology" aria-labelledby="methodology-heading" className="scroll-mt-24">
              <h2 id="methodology-heading" className="text-xl md:text-2xl font-semibold mb-4">
                Methodology
              </h2>
              <RichParagraphs body={page.methodology} />
            </section>

            <section id="what-does-not-prove" aria-labelledby="what-does-not-prove-heading" className="scroll-mt-24">
              <h2 id="what-does-not-prove-heading" className="text-xl md:text-2xl font-semibold mb-4">
                What This Does Not Prove
              </h2>
              <RichParagraphs body={page.whatDoesNotProve} />
            </section>

            <section id="limitations" aria-labelledby="limitations-heading" className="scroll-mt-24 border-t border-slate-200 pt-10">
              <h2 id="limitations-heading" className="text-xl md:text-2xl font-semibold mb-4">
                Limitations
              </h2>
              <RichParagraphs body={page.limitations} />
            </section>

            <section id="related-methodology-pages" aria-labelledby="related-methodology-heading" className="scroll-mt-24">
              <h2 id="related-methodology-heading" className="text-xl md:text-2xl font-semibold mb-4">
                Related methodology pages
              </h2>
              <ul className="list-disc pl-6 space-y-2">
                {page.relatedProof.map((l) => (
                  <li key={l.href}>
                    <Link className="underline text-slate-900" href={l.href}>
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>

            <section id="common-questions" aria-labelledby="common-questions-heading" className="scroll-mt-24">
              <h2 id="common-questions-heading" className="text-xl md:text-2xl font-semibold mb-4">
                Common questions
              </h2>
              <ul className="list-disc pl-6 space-y-2">
                {page.relatedQuestions.map((l) => (
                  <li key={l.href}>
                    <Link className="underline text-slate-900" href={l.href}>
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>

            <section id="last-reviewed" aria-labelledby="last-reviewed-heading" className="scroll-mt-24">
              <h2 id="last-reviewed-heading" className="text-xl md:text-2xl font-semibold mb-4">
                Last Reviewed
              </h2>
              <p className="text-slate-700">
                <time dateTime={page.lastReviewed}>{page.lastReviewed}</time> (content owner: {page.owner})
              </p>
            </section>

            <section id="owner" aria-labelledby="owner-heading" className="scroll-mt-24">
              <h2 id="owner-heading" className="text-xl md:text-2xl font-semibold mb-4">
                Owner
              </h2>
              <p className="text-slate-700">{page.owner}</p>
            </section>
          </article>
        </div>
      </main>
      <Footer />
    </div>
  );
}
