"use client";

import { useState, useMemo } from "react";
import { Manrope } from "next/font/google";
import { Footer } from "@/components/layout/Footer";
import { ResourcesHero } from "@/components/resources/ResourcesHero";
import { ArticleGrid } from "@/components/resources/ArticleGrid";
import { CategoryFilter } from "@/components/resources/CategoryFilter";
import {
    articles,
    getFeaturedArticle,
    getNonFeaturedArticles,
    CategoryFilter as CategoryFilterType,
} from "@/data/articlesData";

const manrope = Manrope({
    subsets: ["latin"],
    weight: ["400", "500", "600", "700", "800"],
    variable: "--font-manrope",
});

export default function ResourcesPage() {
    const [activeCategory, setActiveCategory] = useState<CategoryFilterType>("All");

    const featuredArticle = getFeaturedArticle();

    const filteredArticles = useMemo(() => {
        const nonFeatured = getNonFeaturedArticles();
        if (activeCategory === "All") {
            return nonFeatured;
        }
        return nonFeatured.filter((article) => article.category === activeCategory);
    }, [activeCategory]);

    // Check if featured article matches the filter
    const showFeaturedHero = useMemo(() => {
        if (!featuredArticle) return false;
        if (activeCategory === "All") return true;
        return featuredArticle.category === activeCategory;
    }, [activeCategory, featuredArticle]);

    // If filtering to Budget Planning only, promote article 4 to hero position
    const heroArticle = useMemo(() => {
        if (activeCategory === "Budget Planning") {
            return articles.find((a) => a.category === "Budget Planning");
        }
        return featuredArticle;
    }, [activeCategory, featuredArticle]);

    const gridArticles = useMemo(() => {
        if (activeCategory === "Budget Planning") {
            // Don't show any cards when Budget Planning is selected (only hero)
            return [];
        }
        return filteredArticles;
    }, [activeCategory, filteredArticles]);

    return (
        <div className="min-h-screen flex flex-col bg-white">

            <main className="flex-grow pt-20">
                {/* Page Header */}
                <header className="w-full pt-12 md:pt-16 lg:pt-20 pb-4 md:pb-6 text-center">
                    <div className="container mx-auto px-4 md:px-6">
                        <h1
                            className="mb-4"
                            style={{
                                fontFamily: `${manrope.style.fontFamily}, sans-serif`,
                                fontSize: "clamp(36px, 6vw, 56px)",
                                lineHeight: "1.1",
                                color: "#111827",
                                fontWeight: 700,
                                letterSpacing: "-0.03em",
                            }}
                        >
                            What's new at Skeldir?
                        </h1>
                        <p
                            className="max-w-2xl mx-auto"
                            style={{
                                fontSize: "18px",
                                lineHeight: "1.6",
                                color: "#4B5563",
                            }}
                        >
                            Learn how to navigate attribution discrepancies, understand ROAS ranges,
                            and defend budget shifts with evidence-based frameworks.
                        </p>
                    </div>
                </header>

                {/* Category Filter */}
                <CategoryFilter
                    activeCategory={activeCategory}
                    onCategoryChange={setActiveCategory}
                />

                {/* Hero Section */}
                {heroArticle && showFeaturedHero && (
                    <ResourcesHero article={heroArticle} />
                )}

                {/* Article 4 as hero when Budget Planning is selected */}
                {activeCategory === "Budget Planning" && heroArticle && (
                    <ResourcesHero article={heroArticle} />
                )}

                {/* Article Grid */}
                {gridArticles.length > 0 && <ArticleGrid articles={gridArticles} />}

                {/* Empty state for Budget Planning (no cards, only hero shown above) */}
                {activeCategory === "Budget Planning" && gridArticles.length === 0 && (
                    <div className="pb-16" />
                )}
            </main>

            <Footer />
        </div>
    );
}
