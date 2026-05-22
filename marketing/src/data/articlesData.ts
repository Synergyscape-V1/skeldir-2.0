export interface ArticleMetadata {
    id: string;
    slug: string;
    title: string;
    subtitle: string;
    category: 'Attribution' | 'Budget Planning';
    excerpt: string;
    readTimeMinutes: number;
    publishDate: string;
    heroImagePath: string;
    heroImageAlt: string;
    isFeaturedHero: boolean;
    author?: string;
}

export const articles: ArticleMetadata[] = [
    {
        id: 'article-1',
        slug: 'why-your-attribution-numbers-never-match',
        title: 'Why Your Attribution Numbers Never Match',
        subtitle: 'The Discrepancy Anatomy',
        category: 'Attribution',
        excerpt: 'You open Skeldir and see it: Meta Ads revenue is 16% lower than what Meta claims. Not 2%. Not "rounding." Sixteen. Enough to change which channel gets funded next week.',
        readTimeMinutes: 8,
        publishDate: '2026-01-25',
        heroImagePath: '/images/resources/article-1-hero.png',
        heroImageAlt: 'Visual representation of attribution discrepancies showing platform overlaps',
        isFeaturedHero: true,
        author: 'Amulya Puri',
    },
    {
        id: 'article-2',
        slug: 'roas-is-not-a-number-its-a-range',
        title: 'ROAS Is Not a Number—It\'s a Range',
        subtitle: 'How to Act on Confidence Ranges Without Fooling Yourself',
        category: 'Attribution',
        excerpt: 'When Skeldir shows a range—say, $2.80 to $3.60 ROAS—it\'s not being vague. It\'s telling you the truth about how much you don\'t know.',
        readTimeMinutes: 7,
        publishDate: '2026-01-20',
        heroImagePath: '/images/resources/article-2-hero.jpg',
        heroImageAlt: 'Abstract visualization of ROAS ranges and uncertainty',
        isFeaturedHero: false,
        author: 'Julie Atli',
    },
    {
        id: 'article-3',
        slug: 'attribution-methods-answer-different-questions',
        title: 'Attribution Methods Answer Different Questions',
        subtitle: 'Choosing the Right Tool',
        category: 'Attribution',
        excerpt: 'Attribution is not one tool. It is a toolbox. If you pick the wrong tool, you get a clean, confident answer to the wrong question.',
        readTimeMinutes: 9,
        publishDate: '2026-01-05',
        heroImagePath: '/images/resources/article-3-hero.jpg',
        heroImageAlt: 'Conceptual image of different attribution methodologies',
        isFeaturedHero: false,
        author: 'Matt Jain',
    },
    {
        id: 'article-4',
        slug: 'confidently-defend-budget-shift',
        title: 'Confidently Defend a Budget Shift Without Hiding Behind Dashboards',
        subtitle: 'Evidence-Based Budget Conversations',
        category: 'Budget Planning',
        excerpt: 'You need something stronger than "the dashboard says so." You need a way to explain how your numbers relate to reality.',
        readTimeMinutes: 5,
        publishDate: '2026-01-01',
        heroImagePath: '/images/resources/article-4-hero.jpg',
        heroImageAlt: 'Visual representation of budget planning and financial transparency',
        isFeaturedHero: false,
        author: 'Julie Atli',
    },
];

export const categories = ['All', 'Attribution', 'Budget Planning'] as const;
export type CategoryFilter = typeof categories[number];

export function getArticlesByCategory(category: CategoryFilter): ArticleMetadata[] {
    if (category === 'All') {
        return articles;
    }
    return articles.filter((article) => article.category === category);
}

export function getFeaturedArticle(): ArticleMetadata | undefined {
    return articles.find((article) => article.isFeaturedHero);
}

export function getNonFeaturedArticles(): ArticleMetadata[] {
    return articles.filter((article) => !article.isFeaturedHero);
}

export function getArticleBySlug(slug: string): ArticleMetadata | undefined {
    return articles.find((article) => article.slug === slug);
}

export function getRelatedArticles(currentSlug: string, limit: number = 2): ArticleMetadata[] {
    return articles
        .filter((article) => article.slug !== currentSlug)
        .slice(0, limit);
}
