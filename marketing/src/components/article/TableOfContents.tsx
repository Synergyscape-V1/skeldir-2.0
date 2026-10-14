import type { ReactNode } from "react";
import { articles } from "@/data/articlesData";

export interface TOCItem {
    id: string;
    title: string;
    level: number;
    children?: TOCItem[];
}

interface TableOfContentsProps {
    items: TOCItem[];
}

function renderTocItem(item: TOCItem, depth: number): ReactNode {
    const paddingLeft = depth * 16 + 16;
    return (
        <li key={item.id} className="relative">
            <a
                href={`#${item.id}`}
                className="block py-1.5 transition-colors duration-200 hover:text-blue-600"
                style={{
                    paddingLeft: `${paddingLeft}px`,
                    fontSize: depth === 0 ? "15px" : "14px",
                    fontWeight: 400,
                    color: "#6B7280",
                    borderLeft: "3px solid transparent",
                    lineHeight: 1.8,
                }}
            >
                {item.title}
            </a>
            {item.children && item.children.length > 0 && (
                <ul className="ml-0">{item.children.map((child) => renderTocItem(child, depth + 1))}</ul>
            )}
        </li>
    );
}

function tocLinkList(items: TOCItem[]) {
    return <ul className="space-y-0">{items.map((item) => renderTocItem(item, 0))}</ul>;
}

/** Server-rendered TOC: native hash links; mobile uses `<details>` (no JS). */
export function TableOfContents({ items }: TableOfContentsProps) {
    return (
        <>
            <nav
                aria-label="Article table of contents"
                className="hidden xl:block sticky top-32 w-72 max-h-[calc(100vh-160px)] overflow-y-auto pr-4"
            >
                <h3
                    className="mb-4 uppercase tracking-wide"
                    style={{
                        fontSize: "12px",
                        fontWeight: 600,
                        color: "#9CA3AF",
                        letterSpacing: "0.5px",
                    }}
                >
                    Table of Contents
                </h3>
                {tocLinkList(items)}
            </nav>

            <div className="xl:hidden mb-8">
                <details
                    className="rounded-lg overflow-hidden group"
                    style={{ backgroundColor: "#F3F4F6" }}
                >
                    <summary
                        className="px-4 py-3 cursor-pointer font-medium flex items-center justify-between list-none [&::-webkit-details-marker]:hidden"
                        style={{ color: "#374151", fontSize: "14px" }}
                    >
                        <span>Table of Contents</span>
                        <span className="text-gray-500 select-none group-open:rotate-180 transition-transform">
                            ▼
                        </span>
                    </summary>
                    <div className="px-4 py-3" style={{ backgroundColor: "#F9FAFB" }}>
                        <nav aria-label="Article table of contents" id="mobile-toc">
                            {tocLinkList(items)}
                        </nav>
                    </div>
                </details>
            </div>
        </>
    );
}

// Helper function to generate TOC items for Article 1
export function generateTOCItems(): TOCItem[] {
    return [
        {
            id: "the-first-rule",
            title: "The first rule: two truths",
            level: 2,
        },
        {
            id: "five-mechanisms",
            title: "Five mechanisms of discrepancy",
            level: 2,
            children: [
                { id: "mechanism-1-double-counting", title: "Mechanism 1: Double counting", level: 3 },
                { id: "mechanism-2-attribution-windows", title: "Mechanism 2: Attribution windows", level: 3 },
                { id: "mechanism-3-view-through-credit", title: "Mechanism 3: View-through credit", level: 3 },
                { id: "mechanism-4-signal-loss", title: "Mechanism 4: Signal loss", level: 3 },
                { id: "mechanism-5-revenue-messiness", title: "Mechanism 5: Revenue messiness", level: 3 },
            ],
        },
        {
            id: "the-emotional-trap",
            title: "The emotional trap",
            level: 2,
        },
        {
            id: "10-minute-checklist",
            title: "10-minute discrepancy checklist",
            level: 2,
            children: [
                { id: "step-1-define-numbers", title: "Step 1: Define numbers", level: 3 },
                { id: "step-2-check-windows", title: "Step 2: Check windows", level: 3 },
                { id: "step-3-look-for-overlap", title: "Step 3: Look for overlap", level: 3 },
                { id: "step-4-identify-signal-loss", title: "Step 4: Identify signal loss", level: 3 },
                { id: "step-5-revenue-hygiene", title: "Step 5: Revenue hygiene", level: 3 },
            ],
        },
        {
            id: "decision-rules",
            title: "Decision rules",
            level: 2,
        },
        {
            id: "skeptic-ready-explanation",
            title: "Skeptic-ready explanation",
            level: 2,
        },
        {
            id: "scenario-drill",
            title: "Scenario drill",
            level: 2,
        },
        {
            id: "actionable-takeaway",
            title: "Actionable takeaway",
            level: 2,
        },
    ];
}

// Helper function to generate TOC items for Article 2
export function generateTOCItems2(): TOCItem[] {
    return [
        {
            id: "what-roas-actually-is",
            title: "What ROAS actually is",
            level: 2,
        },
        {
            id: "why-single-roas-is-a-trap",
            title: "Why a single ROAS is a trap",
            level: 2,
        },
        {
            id: "confidence-range-meaning",
            title: "What a confidence range means",
            level: 2,
        },
        {
            id: "where-range-comes-from",
            title: "Where the range comes from",
            level: 2,
        },
        {
            id: "range-is-a-signal",
            title: "The range is a signal",
            level: 2,
        },
        {
            id: "why-ranges-widen",
            title: "Why ranges widen",
            level: 2,
            children: [
                { id: "cause-1-sparse-data", title: "1) Sparse or unstable data", level: 3 },
                { id: "cause-2-correlated-channels", title: "2) Channels that move together", level: 3 },
                { id: "cause-3-delayed-effects", title: "3) Delayed and diminishing effects", level: 3 },
                { id: "cause-4-measurement-loss", title: "4) Measurement loss", level: 3 },
            ],
        },
        {
            id: "what-to-do-with-range",
            title: "Three action rules",
            level: 2,
            children: [
                { id: "rule-1-worst-case", title: "Rule 1: Act on worst-case", level: 3 },
                { id: "rule-2-reallocate-confidently", title: "Rule 2: Reallocate confidently", level: 3 },
                { id: "rule-3-information-gain", title: "Rule 3: Information gain", level: 3 },
            ],
        },
        {
            id: "range-to-action-playbook",
            title: "Range-to-Action playbook",
            level: 2,
        },
        {
            id: "questions-when-range-wide",
            title: "Questions when range is wide",
            level: 2,
        },
        {
            id: "uncertainty-theatre-warning",
            title: "Warning about uncertainty theatre",
            level: 2,
        },
        {
            id: "scenario-drill",
            title: "Scenario drill",
            level: 2,
        },
        {
            id: "truth-underneath",
            title: "The truth underneath",
            level: 2,
        },
    ];
}

// Helper function to generate TOC items for Article 3
export function generateTOCItems3(): TOCItem[] {
    return [
        {
            id: "four-questions",
            title: "The four questions",
            level: 2,
        },
        {
            id: "method-1-rules-based",
            title: "Method 1: Rules-based attribution",
            level: 2,
        },
        {
            id: "method-2-platform-reported",
            title: "Method 2: Platform-reported attribution",
            level: 2,
        },
        {
            id: "method-3-multi-touch",
            title: "Method 3: Multi-touch attribution",
            level: 2,
        },
        {
            id: "method-4-experiments",
            title: "Method 4: Experiments and incrementality",
            level: 2,
        },
        {
            id: "method-5-mmm",
            title: "Method 5: Marketing mix modeling",
            level: 2,
        },
        {
            id: "method-6-bayesian-mmm",
            title: "Method 6: Bayesian MMM",
            level: 2,
        },
        {
            id: "practical-map",
            title: "A practical map",
            level: 2,
        },
        {
            id: "triangulation-playbook",
            title: "The triangulation playbook",
            level: 2,
        },
        {
            id: "two-misconceptions",
            title: "Two misconceptions to kill",
            level: 2,
        },
        {
            id: "scenario-drill",
            title: "Scenario drill",
            level: 2,
        },
        {
            id: "the-truth",
            title: "The part nobody says out loud",
            level: 2,
        },
    ];
}

// Helper function to generate TOC items for Article 4
export function generateTOCItems4(): TOCItem[] {
    return [
        {
            id: "core-mistake",
            title: "The core mistake",
            level: 2,
        },
        {
            id: "why-numbers-feel-soft",
            title: "Why marketing numbers feel soft",
            level: 2,
        },
        {
            id: "evidence-chain",
            title: "The evidence chain",
            level: 2,
            children: [
                { id: "step-1-anchor-outcomes", title: "1) Anchor outcomes to something real", level: 3 },
                { id: "step-2-define-measurement", title: "2) Define what the measurement claims", level: 3 },
                { id: "step-3-uncertainty", title: "3) Treat uncertainty as first-class", level: 3 },
                { id: "step-4-tie-action", title: "4) Tie action to uncertainty", level: 3 },
                { id: "step-5-guardrails", title: "5) Add guardrails", level: 3 },
                { id: "step-6-validation", title: "6) Commit to validation", level: 3 },
            ],
        },
    ];
}

const ARTICLE_TOC_GENERATORS: Record<string, () => TOCItem[]> = {
    "why-your-attribution-numbers-never-match": generateTOCItems,
    "roas-is-not-a-number-its-a-range": generateTOCItems2,
    "attribution-methods-answer-different-questions": generateTOCItems3,
    "confidently-defend-budget-shift": generateTOCItems4,
};

(function assertTocRegistryParity() {
    const fromData = new Set(articles.map((a) => a.slug));
    const fromMap = new Set(Object.keys(ARTICLE_TOC_GENERATORS));
    const missing = [...fromData].filter((s) => !fromMap.has(s));
    const extra = [...fromMap].filter((s) => !fromData.has(s));
    if (missing.length || extra.length) {
        throw new Error(
            `[TableOfContents] TOC slug map must match articlesData exactly.\n` +
                `  Missing TOC for: ${missing.join(", ") || "none"}\n` +
                `  Extra TOC keys: ${extra.join(", ") || "none"}`
        );
    }
})();

// Get TOC items by article slug
export function getTOCItemsBySlug(slug: string): TOCItem[] {
    const generator = ARTICLE_TOC_GENERATORS[slug];
    return generator ? generator() : [];
}
