import { PRICING_TIER_2_NAME } from "@/components/pricing/pricingTier2Copy";

/** Tier 3 pricing card — single source of truth (home + /pricing) */
export const PRICING_TIER_3_NAME = "Infrastructure";

export const PRICING_TIER_3_PRICE = "$999";
export const PRICING_TIER_3_PRICE_SUFFIX = "/month";

export const PRICING_TIER_3_AUDIENCE =
  "For agencies and multi-brand operators running Skeldir as the verified revenue layer across their entire stack.";

export const PRICING_TIER_3_PLUS_HEADING = `Everything in ${PRICING_TIER_2_NAME}, plus:`;

export const PRICING_TIER_3_FEATURES = [
  "Multi-account management under a single verified trust layer",
  "Policy governance controls—define authority boundaries for what agents can query and propose",
  "Allowlisted outbound trust events—your downstream systems receive signed discrepancy and approval-required signals automatically",
  "White-label verified outputs and client-facing LLM explanations, branded for delivery",
  "Guaranteed response SLAs",
  "Built for always-on, multi-tenant, business-critical use",
] as const;

export const PRICING_TIER_3_REPLACES_HEADING = "What this replaces:";

export const PRICING_TIER_3_REPLACES_ITEMS = [
  "Fragmented reporting stacks",
  "Manual client reporting",
  "Unverifiable third-party data your automations act on",
] as const;

export const PRICING_TIER_3_CTA_LABEL = "Contact sales";
