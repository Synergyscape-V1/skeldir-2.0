import { notFound } from "next/navigation";
import { Manrope, DM_Sans, Fira_Code } from "next/font/google";
import { Footer } from "@/components/layout/Footer";
import { ArticleHeader } from "@/components/article/ArticleHeader";
import { TableOfContents, getTOCItemsBySlug } from "@/components/article/TableOfContents";
import { getArticleBodyComponent } from "@/data/articleBodyRegistry";
import { ReadingProgressBar } from "@/components/article/ReadingProgressBar";
import { SocialShare } from "@/components/article/SocialShare";
import { BackToTop } from "@/components/article/BackToTop";
import { RelatedArticles } from "@/components/article/RelatedArticles";
import { getArticleBySlug, getRelatedArticles } from "@/data/articlesData";
import { canonicalUrl } from "@/lib/crawlUrls";
import { JsonLd } from "@/components/schema/JsonLd";
import { articleBreadcrumbJsonLd, articleJsonLd } from "@/lib/schema/pageSchemas";

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

export default async function ArticlePage({ params }: ArticlePageProps) {
    const { slug } = await params;
    const article = getArticleBySlug(slug);

    if (!article) {
        notFound();
    }

    const Body = getArticleBodyComponent(slug);
    if (!Body) {
        notFound();
    }

    const relatedArticles = getRelatedArticles(slug, 2);
    const tocItems = getTOCItemsBySlug(slug);

    return (
        <div
            className={`min-h-screen flex flex-col bg-white ${manrope.variable} ${dmSans.variable} ${firaCode.variable}`}
            style={{ fontFamily: dmSans.style.fontFamily }}
        >
            <JsonLd data={[articleJsonLd(article, slug), articleBreadcrumbJsonLd(slug, article.title)]} />

            <ReadingProgressBar />

            <main className="flex-grow pt-20">
                <ArticleHeader article={article} />

                <div className="container mx-auto px-4 md:px-6">
                    <div className="flex flex-col xl:flex-row gap-8 xl:gap-16 max-w-7xl mx-auto">
                        <aside className="xl:w-72 xl:flex-shrink-0 order-2 xl:order-1">
                            <TableOfContents items={tocItems} />
                        </aside>

                        <article className="flex-1 max-w-3xl order-1 xl:order-2">
                            <Body />
                        </article>
                    </div>
                </div>

                <RelatedArticles articles={relatedArticles} currentArticleSlug={slug} />
            </main>

            <SocialShare title={article.title} url={canonicalUrl(`/resources/${slug}`)} />

            <BackToTop />

            <Footer />
        </div>
    );
}
