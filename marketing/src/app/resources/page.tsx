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
            aria-label="Evidence Library — query-shaped public evidence pages"
        >
            <h2 className="text-2xl font-bold text-slate-900 mb-3">Evidence Library</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
                Skeldir&apos;s public resources now include a query-addressable{" "}
                <strong>Evidence Library</strong> for{" "}
                <strong>Revenue Verification</strong>, <strong>Platform Discrepancies</strong>,{" "}
                <strong>Finance Audit</strong> checklists, <strong>TrustEnvelope</strong> retrieval notes,{" "}
                <strong>Benchmark Methodology</strong> honesty boundaries, deterministic vs probabilistic{" "}
                <strong>confidence</strong> semantics, <strong>privacy</strong> / durable PII scope, and the{" "}
                <strong>AI boundary</strong>. Each page links back to D5 proof authorities (for example{" "}
                <Link className="underline font-medium text-slate-900" href="/methodology">
                    /methodology
                </Link>
                ,{" "}
                <Link className="underline font-medium text-slate-900" href="/revenue-verification">
                    /revenue-verification
                </Link>
                ,{" "}
                <Link className="underline font-medium text-slate-900" href="/discrepancy-taxonomy">
                    /discrepancy-taxonomy
                </Link>
                ).
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
