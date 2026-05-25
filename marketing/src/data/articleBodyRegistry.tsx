import type { ComponentType } from "react";
import { ArticleContent } from "@/components/article/ArticleContent";
import { ArticleContent2 } from "@/components/article/ArticleContent2";
import { ArticleContent3 } from "@/components/article/ArticleContent3";
import { ArticleContent4 } from "@/components/article/ArticleContent4";
import { articles } from "./articlesData";

/**
 * Single registry mapping article slugs (from `articlesData`) to body renderers.
 * `articlesData` is the metadata source of truth; this registry is the body renderer
 * source of truth. They must stay in exact parity — validated at module load below.
 */
export const articleBodyRegistry: Record<string, ComponentType> = {
    "why-your-attribution-numbers-never-match": ArticleContent,
    "roas-is-not-a-number-its-a-range": ArticleContent2,
    "attribution-methods-answer-different-questions": ArticleContent3,
    "confidently-defend-budget-shift": ArticleContent4,
};

function assertArticleBodyRegistryParity(reg: Record<string, ComponentType>) {
    const fromData = articles.map((a) => a.slug).sort();
    const fromReg = Object.keys(reg).sort();
    const dataSet = new Set(fromData);
    const regSet = new Set(fromReg);
    const missing = fromData.filter((s) => !regSet.has(s));
    const extra = fromReg.filter((s) => !dataSet.has(s));
    if (missing.length || extra.length) {
        throw new Error(
            `[articleBodyRegistry] articlesData slugs and body registry must match exactly.\n` +
                `  Missing body renderers for: ${missing.join(", ") || "none"}\n` +
                `  Extra registry keys (stale or typo): ${extra.join(", ") || "none"}`
        );
    }
}

assertArticleBodyRegistryParity(articleBodyRegistry);

export function getArticleBodyComponent(slug: string): ComponentType | undefined {
    return articleBodyRegistry[slug];
}
