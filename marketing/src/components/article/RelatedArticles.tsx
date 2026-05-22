import Link from "next/link";
import Image from "next/image";
import { Manrope } from "next/font/google";
import { Clock, ArrowRight } from "lucide-react";
import { ArticleMetadata } from "@/data/articlesData";

const manrope = Manrope({
    subsets: ["latin"],
    weight: ["400", "500", "600", "700", "800"],
    variable: "--font-manrope",
});

interface RelatedArticlesProps {
    articles: ArticleMetadata[];
    currentArticleSlug: string;
}

// Article Card Component
function RelatedArticleCard({ article }: { article: ArticleMetadata }) {
    const categoryColors: Record<string, { bg: string; text: string }> = {
        Attribution: { bg: "#3B82F6", text: "#FFFFFF" },
        "Budget Planning": { bg: "#10B981", text: "#FFFFFF" },
    };

    const categoryStyle =
        categoryColors[article.category] || categoryColors["Attribution"];

    return (
        <Link
            href={`/resources/${article.slug}`}
            className="group block rounded-xl overflow-hidden transition-all duration-300 hover:-translate-y-1"
            style={{
                backgroundColor: "#FFFFFF",
                border: "1px solid #E5E7EB",
                boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
            }}
        >
            {/* Image */}
            <div
                className="relative w-full overflow-hidden"
                style={{ aspectRatio: "16/9" }}
            >
                <Image
                    src={article.heroImagePath}
                    alt={article.heroImageAlt}
                    fill
                    className="object-cover transition-transform duration-500 group-hover:scale-105"
                    sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 400px"
                    loading="lazy"
                />
                {/* Category Badge */}
                <div className="absolute top-4 left-4">
                    <span
                        className="inline-block px-2.5 py-1 rounded text-xs font-semibold uppercase"
                        style={{
                            backgroundColor: categoryStyle.bg,
                            color: categoryStyle.text,
                            letterSpacing: "0.5px",
                        }}
                    >
                        {article.category}
                    </span>
                </div>
            </div>

            {/* Content */}
            <div className="p-5">
                <h4
                    className="mb-2 transition-colors group-hover:text-blue-600"
                    style={{
                        fontFamily: `${manrope.style.fontFamily}, sans-serif`,
                        fontSize: "18px",
                        fontWeight: 600,
                        lineHeight: 1.3,
                        color: "#111827",
                    }}
                >
                    {article.title}
                </h4>
                <p
                    className="mb-4 line-clamp-2"
                    style={{
                        fontSize: "14px",
                        lineHeight: 1.6,
                        color: "#6B7280",
                    }}
                >
                    {article.excerpt}
                </p>
                <div
                    className="flex items-center gap-1.5"
                    style={{ color: "#9CA3AF", fontSize: "13px" }}
                >
                    <Clock className="w-3.5 h-3.5" />
                    <span>{article.readTimeMinutes} min read</span>
                </div>
            </div>
        </Link>
    );
}

// CTA Card Component
function CTACard() {
    return (
        <div
            className="relative rounded-xl overflow-hidden p-6 flex flex-col justify-between h-full min-h-[320px]"
            style={{
                background:
                    "linear-gradient(135deg, #1E3A5F 0%, #0F172A 50%, #1E293B 100%)",
            }}
        >
            {/* Decorative Elements */}
            <div
                className="absolute top-0 right-0 w-32 h-32 rounded-full opacity-10"
                style={{
                    background:
                        "radial-gradient(circle, #3B82F6 0%, transparent 70%)",
                    transform: "translate(30%, -30%)",
                }}
            />
            <div
                className="absolute bottom-0 left-0 w-24 h-24 rounded-full opacity-10"
                style={{
                    background:
                        "radial-gradient(circle, #60A5FA 0%, transparent 70%)",
                    transform: "translate(-30%, 30%)",
                }}
            />

            {/* Content */}
            <div className="relative z-10">
                <h4
                    className="mb-3"
                    style={{
                        fontFamily: `${manrope.style.fontFamily}, sans-serif`,
                        fontSize: "22px",
                        fontWeight: 700,
                        lineHeight: 1.2,
                        color: "#FFFFFF",
                    }}
                >
                    Ready to solve attribution discrepancies?
                </h4>
                <p
                    style={{
                        fontSize: "15px",
                        lineHeight: 1.6,
                        color: "#94A3B8",
                    }}
                >
                    See how Skeldir provides revenue verification ground truth and
                    confidence ranges.
                </p>
            </div>

            {/* CTA Button */}
            <Link
                href="/book-demo"
                className="relative z-10 inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all duration-200 group mt-6 w-full sm:w-auto"
                style={{
                    backgroundColor: "#FFFFFF",
                    color: "#0F172A",
                    fontSize: "15px",
                }}
            >
                Get a demo
                <ArrowRight
                    className="w-4 h-4 transition-transform group-hover:translate-x-1"
                    strokeWidth={2.5}
                />
            </Link>
        </div>
    );
}

export function RelatedArticles({
    articles,
    currentArticleSlug,
}: RelatedArticlesProps) {
    // Filter out current article just in case
    const filteredArticles = articles.filter(
        (a) => a.slug !== currentArticleSlug
    );

    return (
        <section className="py-16 md:py-24 mt-12" style={{ backgroundColor: "#F9FAFB" }}>
            <div className="container mx-auto px-4 md:px-6 max-w-6xl">
                {/* Section Header */}
                <h3
                    className="mb-10"
                    style={{
                        fontFamily: `${manrope.style.fontFamily}, sans-serif`,
                        fontSize: "clamp(24px, 3vw, 28px)",
                        fontWeight: 600,
                        color: "#111827",
                    }}
                >
                    Related Articles
                </h3>

                {/* Grid: 2 articles + 1 CTA on desktop, stacked on mobile */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {filteredArticles.slice(0, 2).map((article) => (
                        <RelatedArticleCard key={article.id} article={article} />
                    ))}
                    <div className="md:col-span-2 lg:col-span-1">
                        <CTACard />
                    </div>
                </div>
            </div>
        </section>
    );
}
