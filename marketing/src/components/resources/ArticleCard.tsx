import Image from "next/image";
import Link from "next/link";
import { ArticleMetadata } from "@/data/articlesData";

interface ArticleCardProps {
    article: ArticleMetadata;
}

const categoryColors: Record<string, { bg: string; text: string }> = {
    Attribution: { bg: "#3B82F6", text: "#FFFFFF" },
    "Budget Planning": { bg: "#10B981", text: "#FFFFFF" },
};

function formatDate(dateString: string) {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

export function ArticleCard({ article }: ArticleCardProps) {
    const categoryStyle = categoryColors[article.category] || categoryColors["Attribution"];

    return (
        <Link
            href={`/resources/${article.slug}`}
            className="group block rounded-2xl overflow-hidden transition-all duration-300 ease-out hover:-translate-y-0.5 hover:shadow-lg hover:border-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
            style={{
                border: "1px solid #E5E7EB",
            }}
        >
            <article className="flex flex-col bg-white h-full">
                <div className="relative w-full" style={{ aspectRatio: "16/9" }}>
                    <Image
                        src={article.heroImagePath}
                        alt={article.heroImageAlt}
                        fill
                        className="object-cover"
                        sizes="(max-width: 767px) 100vw, (max-width: 1023px) 50vw, 33vw"
                        loading="lazy"
                    />
                    <div
                        className="absolute top-4 right-4 px-3 py-1 rounded-full text-xs font-semibold"
                        style={{
                            backgroundColor: categoryStyle.bg,
                            color: categoryStyle.text,
                        }}
                    >
                        {article.category}
                    </div>
                </div>

                <div className="flex flex-col flex-grow p-6">
                    <h3
                        className="font-semibold line-clamp-2 mb-2"
                        style={{
                            fontSize: "20px",
                            lineHeight: "1.3",
                            color: "#111827",
                        }}
                    >
                        {article.title}
                    </h3>

                    <p
                        className="mb-3"
                        style={{
                            fontSize: "14px",
                            fontWeight: 400,
                            color: "#6B7280",
                        }}
                    >
                        By {article.author || "Julie Atli"} • {article.readTimeMinutes} min
                    </p>

                    <p
                        className="line-clamp-3 mb-4 flex-grow"
                        style={{
                            fontSize: "15px",
                            lineHeight: "1.6",
                            color: "#4B5563",
                        }}
                    >
                        {article.excerpt}
                    </p>

                    <p
                        style={{
                            fontSize: "13px",
                            color: "#9CA3AF",
                        }}
                    >
                        {formatDate(article.publishDate)}
                    </p>
                </div>
            </article>
        </Link>
    );
}
