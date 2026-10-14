/**
 * Article SEO copy — shared by `resources/[slug]/layout.tsx` (metadata) and JSON-LD (D4 parity).
 */
export const articleSeoBySlug: Record<
  string,
  {
    description: string;
    keywords: string[];
  }
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

export function getArticleSeoDescription(slug: string): string | undefined {
  return articleSeoBySlug[slug]?.description;
}
