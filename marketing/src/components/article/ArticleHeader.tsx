import Link from "next/link";
import Image from "next/image";
import { Manrope } from "next/font/google";
import { ArrowLeft, Clock } from "lucide-react";
import { ArticleMetadata } from "@/data/articlesData";

const manrope = Manrope({
    subsets: ["latin"],
    weight: ["400", "500", "600", "700", "800"],
    variable: "--font-manrope",
});

interface ArticleHeaderProps {
    article: ArticleMetadata;
}

export function ArticleHeader({ article }: ArticleHeaderProps) {
    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
    };

    const categoryColors: Record<string, { bg: string; text: string }> = {
        'Attribution': { bg: '#3B82F6', text: '#FFFFFF' },
        'Budget Planning': { bg: '#10B981', text: '#FFFFFF' },
    };

    const categoryStyle = categoryColors[article.category] || categoryColors['Attribution'];

    return (
        <header className="w-full pt-8 md:pt-12">
            <div className="container mx-auto px-4 md:px-6 max-w-4xl">
                {/* Back to Resources Link */}
                <Link
                    href="/resources"
                    className="inline-flex items-center gap-2 mb-8 transition-colors group"
                    style={{
                        fontSize: '14px',
                        fontWeight: 500,
                        color: '#6B7280',
                    }}
                >
                    <ArrowLeft
                        className="w-4 h-4 transition-transform group-hover:-translate-x-1"
                        style={{ color: '#6B7280' }}
                    />
                    <span className="group-hover:text-blue-600">Back to Resources</span>
                </Link>

                {/* Category Badge */}
                <div className="mb-6">
                    <span
                        className="inline-block px-3 py-1.5 rounded text-xs font-semibold uppercase tracking-wide"
                        style={{
                            backgroundColor: categoryStyle.bg,
                            color: categoryStyle.text,
                            letterSpacing: '0.5px',
                        }}
                    >
                        {article.category}
                    </span>
                </div>

                {/* Title */}
                <h1
                    className="mb-4"
                    style={{
                        fontFamily: `${manrope.style.fontFamily}, sans-serif`,
                        fontSize: 'clamp(36px, 5vw, 56px)',
                        fontWeight: 700,
                        lineHeight: 1.1,
                        color: '#111827',
                        maxWidth: '800px',
                        letterSpacing: '-0.02em',
                    }}
                >
                    {article.title}
                </h1>

                {/* Subtitle */}
                <h2
                    className="mb-6"
                    style={{
                        fontSize: 'clamp(20px, 3vw, 28px)',
                        fontWeight: 400,
                        lineHeight: 1.3,
                        color: '#6B7280',
                    }}
                >
                    {article.subtitle}
                </h2>

                {/* Metadata Row */}
                <div
                    className="flex flex-wrap items-center gap-4 mb-12"
                    style={{ color: '#6B7280', fontSize: '14px' }}
                >
                    {/* Author */}
                    <div className="flex items-center gap-2">
                        <span style={{ fontWeight: 500, color: '#374151' }}>
                            {article.author || 'Amulya Puri'}
                        </span>
                    </div>

                    <span style={{ color: '#D1D5DB' }}>•</span>

                    {/* Read Time */}
                    <div className="flex items-center gap-1.5">
                        <Clock className="w-4 h-4" style={{ color: '#9CA3AF' }} />
                        <span>{article.readTimeMinutes} min read</span>
                    </div>

                    <span style={{ color: '#D1D5DB' }}>•</span>

                    {/* Date */}
                    <span>{formatDate(article.publishDate)}</span>
                </div>

                {/* Hero Image */}
                <div
                    className="relative w-full mb-12 overflow-hidden"
                    style={{
                        aspectRatio: '16/9',
                        borderRadius: '12px',
                        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.08)',
                    }}
                >
                    <Image
                        src={article.heroImagePath}
                        alt={article.heroImageAlt}
                        fill
                        className="object-cover"
                        sizes="(max-width: 768px) 100vw, (max-width: 1200px) 80vw, 900px"
                        priority
                    />
                    {/* Gradient overlays for smooth edge blending */}
                    <div
                        className="absolute top-0 left-0 right-0 pointer-events-none"
                        style={{
                            height: '60px',
                            background: 'linear-gradient(to bottom, rgba(255, 255, 255, 0.3) 0%, transparent 100%)',
                        }}
                    />
                    <div
                        className="absolute bottom-0 left-0 right-0 pointer-events-none"
                        style={{
                            height: '80px',
                            background: 'linear-gradient(to top, rgba(255, 255, 255, 0.5) 0%, transparent 100%)',
                        }}
                    />
                </div>
            </div>
        </header>
    );
}
