import { PRICING_TIER_1_NAME } from "@/components/pricing/pricingTier1Copy";

/** Tier 2 pricing card — single source of truth (home + /pricing) */
export const PRICING_TIER_2_NAME = "Optimize";

export const PRICING_TIER_2_PRICE = "$499";
export const PRICING_TIER_2_PRICE_SUFFIX = "/month";

export const PRICING_TIER_2_AUDIENCE =
  "For operators actively reallocating budget who need verified evidence before moving dollars—and agents that can act on it.";

export const PRICING_TIER_2_PLUS_HEADING = `Everything in ${PRICING_TIER_1_NAME}, plus:`;

export const PRICING_TIER_2_FEATURES = [
  "Unlimited ad platform connections",
  "Deterministic budget simulation—model reallocation scenarios against verified baselines before committing spend",
  "Human-reviewable proposals generated from simulation outputs",
  "Cross-channel benchmark intelligence—see how your discrepancy profile compares to anonymized market data",
  "Expanded agent tool scope: budget simulation queries available to connected AI agents",
  "Priority support",
] as const;

export const PRICING_TIER_2_REPLACES_HEADING = "What this replaces:";

export const PRICING_TIER_2_REPLACES_ITEMS = [
  "Gut-feel reallocation",
  "Black-box recommendations",
  "Post-ad spend regret",
] as const;

export const PRICING_TIER_2_BADGE_LABEL = "Most popular";
export const PRICING_TIER_2_CTA_LABEL = "Contact sales";
