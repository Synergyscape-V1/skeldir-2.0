import { ArticleMetadata } from "@/data/articlesData";
import { ArticleCard } from "./ArticleCard";

interface ArticleGridProps {
    articles: ArticleMetadata[];
}

export function ArticleGrid({ articles }: ArticleGridProps) {
    if (articles.length === 0) {
        return (
            <div className="text-center py-12">
                <p
                    style={{
                        fontSize: "16px",
                        color: "#6B7280",
                    }}
                >
                    No articles found in this category.
                </p>
            </div>
        );
    }

    return (
        <section className="w-full pb-16 md:pb-20 lg:pb-24">
            <div className="container mx-auto px-4 md:px-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8">
                    {articles.map((article) => (
                        <ArticleCard key={article.id} article={article} />
                    ))}
                </div>
            </div>
        </section>
    );
}
