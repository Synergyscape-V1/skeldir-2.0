/** Tier 1 pricing card — single source of truth (home + /pricing) */
export const PRICING_TIER_1_NAME = "Verify";

export const PRICING_TIER_1_PRICE = "$199";
export const PRICING_TIER_1_PRICE_SUFFIX = "/month";

export const PRICING_TIER_1_AUDIENCE =
  "For operators who need ground-truth independent proof of what their ad platforms claim—queryable by your team and your AI tools from day one.";

export const PRICING_TIER_1_FEATURES = [
  "Revenue verification against Shopify, Stripe, PayPal, WooCommerce",
  "Cross-verified discrepancy detection the moment platform claims diverge from actual revenue",
  "TrustEnvelope access—every output is signed, versioned, and machine-readable",
  "MCP adapter included: your AI agents query verified revenue directly",
  "LLM-narrated explanations bounded to verified facts—no hallucinated numbers",
  "Live in 48 hours, self-serve",
] as const;

export const PRICING_TIER_1_REPLACES_HEADING = "What this replaces:";

export const PRICING_TIER_1_REPLACES_ITEMS = [
  "Spreadsheets",
  "Manual cross-checks",
  "Blindly trusting ad platform self-attributing dashboards",
] as const;

export const PRICING_TIER_1_CTA_HOME = "GET STARTED";
export const PRICING_TIER_1_CTA_PRICING_PAGE = "Get started for $199/month";
