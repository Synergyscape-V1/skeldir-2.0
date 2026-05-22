import type { Metadata } from "next";
import { getArticleBySlug, articles } from "@/data/articlesData";

// Article-specific metadata
const articleMetadata: Record<
    string,
    { description: string; keywords: string[] }
> = {
    "why-your-attribution-numbers-never-match": {
        description:
            "Understand why Meta Ads, Google Ads, and your verified revenue never match. Learn the 5 mechanisms driving attribution discrepancies and how to defend your measurement system.",
        keywords: [
            "attribution discrepancy",
            "marketing attribution",
            "revenue verification",
            "Meta Ads",
            "Google Ads",
            "ROAS",
            "measurement",
            "analytics",
        ],
    },
    "roas-is-not-a-number-its-a-range": {
        description:
            "Learn how to act on ROAS confidence ranges without fooling yourself. Understand what uncertainty intervals mean, why ranges widen, and the three action rules for budget decisions.",
        keywords: [
            "ROAS range",
            "return on ad spend",
            "uncertainty",
            "marketing measurement",
            "confidence intervals",
            "Bayesian",
            "credible interval",
            "budget allocation",
        ],
    },
    "attribution-methods-answer-different-questions": {
        description:
            "Attribution is not one tool. It is a toolbox. Learn when to use rules-based, platform-reported, multi-touch, experiments, MMM, and Bayesian MMM for different marketing questions.",
        keywords: [
            "attribution methods",
            "last touch attribution",
            "multi-touch attribution",
            "incrementality testing",
            "marketing mix modeling",
            "MMM",
            "Bayesian MMM",
            "experiments",
            "geo testing",
            "marketing measurement",
            "budget allocation",
        ],
    },
    "confidently-defend-budget-shift": {
        description:
            "You need something stronger than 'the dashboard says so.' Learn the six-step evidence chain to defend budget shifts and build trust with stakeholders who carry financial risk.",
        keywords: [
            "budget planning",
            "marketing budget",
            "evidence-based marketing",
            "marketing accountability",
            "budget reallocation",
            "uncertainty management",
            "marketing measurement",
            "finance stakeholders",
            "guardrails",
            "validation",
        ],
    },
};

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
    const meta = articleMetadata[slug];

    if (!article) {
        return {
            title: "Article Not Found | Skeldir",
            description: "The article you're looking for could not be found.",
        };
    }

    const baseUrl = "https://skeldir.com";
    const articleUrl = `${baseUrl}/resources/${slug}`;
    const imageUrl = `${baseUrl}${article.heroImagePath}`;

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
