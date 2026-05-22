import type { ReactNode } from "react";
import {
    articles,
    getFeaturedArticle,
    getNonFeaturedArticles,
    type CategoryFilter,
} from "@/data/articlesData";
import { ArticleGrid } from "@/components/resources/ArticleGrid";
import { ResourcesHero } from "@/components/resources/ResourcesHero";
import { ResourcesPageClient } from "./ResourcesPageClient";

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

    return (
        <>
            <nav aria-label="All Skeldir resource articles" className="sr-only">
                <ul>
                    {articles.map((article) => (
                        <li key={article.slug}>
                            <a href={`/resources/${article.slug}`}>{article.title}</a>
                        </li>
                    ))}
                </ul>
            </nav>
            <ResourcesPageClient sections={sections} />
        </>
    );
}
