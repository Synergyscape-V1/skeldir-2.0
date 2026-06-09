/** Tier 1 pricing card — single source of truth (home + /pricing) */
export const PRICING_TIER_1_NAME = "Verify";

export const PRICING_TIER_1_PRICE = "$399";
export const PRICING_TIER_1_PRICE_SUFFIX = "/month";
/** CTAs + secondary surfaces — derived from tier price */
export const PRICING_TIER_1_PRICE_MO = "$399/mo";
/** schema.org Offer.price (numeric string, USD) */
export const PRICING_TIER_1_SCHEMA_PRICE = "399";

export const PRICING_TIER_1_HOOK =
  "What are unverified ad platform claims costing me right now?";

export const PRICING_TIER_1_RIGHT_FOR_YOU_HEADING = "Right for you if:";

export const PRICING_TIER_1_RIGHT_FOR_YOU =
  "You spend $5K–$50K/month on ads. You've noticed your ad platform ROAS and actual revenue don't reconcile cleanly.";

export const PRICING_TIER_1_INCLUDED_HEADING = "What's included:";

export const PRICING_TIER_1_FEATURES = [
  "3,000 verified orders/month — every order cross-checked against Shopify, Stripe, PayPal, WooCommerce",
  "Live discrepancy flagging — platform overclaim surfaced at the order level, not the monthly summary",
  "Signed, versioned audit artifacts — every verification output is machine-readable and traceable",
  "AI integrations — your agents query ground-truth revenue, bounded to verified facts",
  "Unlimited users — no seat tax on your finance, marketing, or leadership team",
] as const;

export const PRICING_TIER_1_OVERAGE =
  "$0.06/order beyond 3,000 · Maximum bill: $579";

export const PRICING_TIER_1_REPLACES_HEADING = "What this replaces:";

export const PRICING_TIER_1_REPLACES_ITEMS = [
  "Ad platform dashboards as the source of truth for revenue reporting.",
  "Reporting ROAS your teams can't independently verify.",
] as const;

export const PRICING_TIER_1_CTA_HOME = "GET STARTED";
export const PRICING_TIER_1_CTA_PRICING_PAGE = "Test Your Integration";
