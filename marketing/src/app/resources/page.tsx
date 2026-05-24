import type { ReactNode } from "react";
import Link from "next/link";
import {
    articles,
    getFeaturedArticle,
    getNonFeaturedArticles,
    type CategoryFilter,
} from "@/data/articlesData";
import { ArticleGrid } from "@/components/resources/ArticleGrid";
import { ResourcesHero } from "@/components/resources/ResourcesHero";
import { ResourcesPageClient } from "./ResourcesPageClient";
import { JsonLd } from "@/components/schema/JsonLd";
import { collectionPageResourcesJsonLd, resourcesHubBreadcrumbJsonLd } from "@/lib/schema/pageSchemas";

function buildCategorySections(): Record<CategoryFilter, ReactNode> {
    const featured = getFeaturedArticle();
    const nonFeatured = getNonFeaturedArticles();
    const budgetArticle = articles.find((a) => a.category === "Budget Planning");

    if (!featured || !budgetArticle) {
        throw new Error("resources: missing featured or budget article in articlesData");
    }

    const attributionNonFeatured = nonFeatured.filter((a) => a.category === "Attribution");

    return {
        All: (
            <>
                <ResourcesHero article={featured} />
                <ArticleGrid articles={nonFeatured} />
            </>
        ),
        Attribution: (
            <>
                <ResourcesHero article={featured} />
                <ArticleGrid articles={attributionNonFeatured} />
            </>
        ),
        "Budget Planning": (
            <>
                <ResourcesHero article={budgetArticle} />
                <div className="pb-16" />
            </>
        ),
    };
}

export default function ResourcesPage() {
    const sections = buildCategorySections();

    const evidenceStrip = (
        <section
            className="container mx-auto px-4 md:px-6 max-w-5xl pb-10"
            aria-label="Evidence Library — methodology-aligned explainers"
        >
            <h2 className="text-2xl font-bold text-slate-900 mb-3">Evidence Library</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
                Alongside the articles below, we publish focused explainers on{" "}
                <strong>revenue verification</strong>, <strong>platform discrepancies</strong>, finance{" "}
                <strong>audit</strong> checklists, <strong>TrustEnvelope</strong> concepts,{" "}
                <strong>benchmark methodology</strong> and its limits, deterministic versus probabilistic{" "}
                <strong>confidence</strong>, <strong>privacy</strong> and durable identifiers, and the{" "}
                <strong>AI boundary</strong>. Those pages intentionally cross-link the same public methodology
                anchors (for example{" "}
                <Link className="underline font-medium text-slate-900" href="/methodology">
                    Methodology
                </Link>
                ,{" "}
                <Link className="underline font-medium text-slate-900" href="/revenue-verification">
                    Revenue verification
                </Link>
                , and{" "}
                <Link className="underline font-medium text-slate-900" href="/discrepancy-taxonomy">
                    Discrepancy taxonomy
                </Link>
                ) so we do not drift between “marketing language” and how Skeldir defines terms.
            </p>
            <Link
                href="/resources/evidence"
                className="inline-flex font-semibold text-slate-900 underline underline-offset-4"
            >
                Browse the Evidence Library hub
            </Link>
        </section>
    );

    return (
        <>
            <JsonLd data={[collectionPageResourcesJsonLd(), resourcesHubBreadcrumbJsonLd()]} />
            <nav aria-label="All Skeldir resource articles" className="sr-only">
                <ul>
                    {articles.map((article) => (
                        <li key={article.slug}>
                            <a href={`/resources/${article.slug}`}>{article.title}</a>
                        </li>
                    ))}
                </ul>
            </nav>
            <ResourcesPageClient sections={sections} prepend={evidenceStrip} />
        </>
    );
}
