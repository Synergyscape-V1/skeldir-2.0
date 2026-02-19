"use client";

import { useEffect, useState } from "react";
import Script from "next/script";
import { notFound } from "next/navigation";
import { Manrope, DM_Sans, Fira_Code } from "next/font/google";
import { Footer } from "@/components/layout/Footer";
import { ArticleHeader } from "@/components/article/ArticleHeader";
import { TableOfContents, getTOCItemsBySlug } from "@/components/article/TableOfContents";
import { ArticleContent } from "@/components/article/ArticleContent";
import { ArticleContent2 } from "@/components/article/ArticleContent2";
import { ArticleContent3 } from "@/components/article/ArticleContent3";
import { ArticleContent4 } from "@/components/article/ArticleContent4";
import { ReadingProgressBar } from "@/components/article/ReadingProgressBar";
import { SocialShare } from "@/components/article/SocialShare";
import { BackToTop } from "@/components/article/BackToTop";
import { RelatedArticles } from "@/components/article/RelatedArticles";
import { getArticleBySlug, getRelatedArticles } from "@/data/articlesData";

// Generate JSON-LD structured data for article
function generateArticleJsonLd(article: {
    title: string;
    subtitle: string;
    excerpt: string;
    publishDate: string;
    heroImagePath: string;
    author?: string;
}, slug: string) {
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        headline: article.title,
        description: article.excerpt,
        image: `https://skeldir.com${article.heroImagePath}`,
        datePublished: article.publishDate,
        dateModified: article.publishDate,
        author: {
            "@type": "Organization",
            name: article.author || "Amulya Puri",
            url: "https://skeldir.com",
        },
        publisher: {
            "@type": "Organization",
            name: "Skeldir",
            logo: {
                "@type": "ImageObject",
                url: "https://skeldir.com/images/skeldir-logo-black.png",
            },
        },
        mainEntityOfPage: {
            "@type": "WebPage",
            "@id": `https://skeldir.com/resources/${slug}`,
        },
    };
}

const manrope = Manrope({
    subsets: ["latin"],
    weight: ["400", "500", "600", "700", "800"],
    variable: "--font-manrope",
});

const dmSans = DM_Sans({
    subsets: ["latin"],
    weight: ["400", "500", "600", "700"],
    variable: "--font-dm-sans",
});

const firaCode = Fira_Code({
    subsets: ["latin"],
    weight: ["400", "500"],
    variable: "--font-fira-code",
});

interface ArticlePageProps {
    params: Promise<{ slug: string }>;
}

export default function ArticlePage({ params }: ArticlePageProps) {
    const [slug, setSlug] = useState<string | null>(null);

    useEffect(() => {
        params.then((p) => setSlug(p.slug));
    }, [params]);

    if (!slug) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-white">
                <div className="animate-pulse text-gray-400">Loading...</div>
            </div>
        );
    }

    const article = getArticleBySlug(slug);

    if (!article) {
        notFound();
    }

    const relatedArticles = getRelatedArticles(slug, 2);
    const tocItems = getTOCItemsBySlug(slug);
    const jsonLd = generateArticleJsonLd(article, slug);

    // Render the correct content component based on slug
    const renderContent = () => {
        switch (slug) {
            case "why-your-attribution-numbers-never-match":
                return <ArticleContent />;
            case "roas-is-not-a-number-its-a-range":
                return <ArticleContent2 />;
            case "attribution-methods-answer-different-questions":
                return <ArticleContent3 />;
            case "confidently-defend-budget-shift":
                return <ArticleContent4 />;
            default:
                return <ArticleContent />;
        }
    };

    return (
        <div
            className={`min-h-screen flex flex-col bg-white ${manrope.variable} ${dmSans.variable} ${firaCode.variable}`}
            style={{ fontFamily: dmSans.style.fontFamily }}
        >
            {/* JSON-LD Structured Data */}
            <Script
                id="article-jsonld"
                type="application/ld+json"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
            />

            {/* Reading Progress Bar */}
            <ReadingProgressBar />

            <main className="flex-grow pt-20">
                {/* Article Header */}
                <ArticleHeader article={article} />

                {/* Main Content Area with TOC */}
                <div className="container mx-auto px-4 md:px-6">
                    <div className="flex flex-col xl:flex-row gap-8 xl:gap-16 max-w-7xl mx-auto">
                        {/* Table of Contents - Desktop Sidebar */}
                        <aside className="xl:w-72 xl:flex-shrink-0 order-2 xl:order-1">
                            <TableOfContents items={tocItems} />
                        </aside>

                        {/* Article Content */}
                        <article className="flex-1 max-w-3xl order-1 xl:order-2">
                            {renderContent()}
                        </article>
                    </div>
                </div>

                {/* Related Articles Section */}
                <RelatedArticles
                    articles={relatedArticles}
                    currentArticleSlug={slug}
                />
            </main>

            {/* Social Share - Floating on Desktop */}
            <SocialShare
                title={article.title}
                url={`https://skeldir.com/resources/${slug}`}
            />

            {/* Back to Top Button */}
            <BackToTop />

            <Footer />
        </div>
    );
}
