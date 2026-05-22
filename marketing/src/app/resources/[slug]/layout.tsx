import type { Metadata } from "next";
import { getArticleBySlug, articles } from "@/data/articlesData";
import { articleSeoBySlug } from "@/data/articleSeo";
import { canonicalUrl, SITE_ORIGIN } from "@/lib/crawlUrls";

interface LayoutProps {
    children: React.ReactNode;
    params: Promise<{ slug: string }>;
}

export async function generateMetadata({
    params,
}: {
    params: Promise<{ slug: string }>;
}): Promise<Metadata> {
    const { slug } = await params;
    const article = getArticleBySlug(slug);
    const meta = articleSeoBySlug[slug];

    if (!article) {
        return {
            title: "Article Not Found | Skeldir",
            description: "The article you're looking for could not be found.",
        };
    }

    const articleUrl = canonicalUrl(`/resources/${slug}`);
    const imageUrl = `${SITE_ORIGIN}${article.heroImagePath}`;

    return {
        title: `${article.title} | Skeldir`,
        description: meta?.description || article.excerpt,
        keywords: meta?.keywords || [],
        authors: [{ name: article.author || "Skeldir Team" }],
        openGraph: {
            title: article.title,
            description: meta?.description || article.excerpt,
            type: "article",
            url: articleUrl,
            images: [
                {
                    url: imageUrl,
                    width: 1200,
                    height: 675,
                    alt: article.heroImageAlt,
                },
            ],
            publishedTime: article.publishDate,
            authors: [article.author || "Skeldir Team"],
            siteName: "Skeldir",
        },
        twitter: {
            card: "summary_large_image",
            title: article.title,
            description: meta?.description || article.excerpt,
            images: [imageUrl],
        },
        alternates: {
            canonical: articleUrl,
        },
        robots: {
            index: true,
            follow: true,
        },
    };
}

// Generate static params for all articles
export async function generateStaticParams() {
    return articles.map((article) => ({
        slug: article.slug,
    }));
}

export default function ArticleLayout({ children }: LayoutProps) {
    return <>{children}</>;
}
