import { PRICING_TIER_1_NAME } from "@/components/pricing/pricingTier1Copy";

/** Tier 2 pricing card — single source of truth (home + /pricing) */
export const PRICING_TIER_2_NAME = "Optimize";

export const PRICING_TIER_2_PRICE = "$799";
export const PRICING_TIER_2_PRICE_SUFFIX = "/month";
export const PRICING_TIER_2_PRICE_MO = "$799/mo";

export const PRICING_TIER_2_HOOK =
  "Am I reallocating budget on verified evidence or platform self-reports?";

export const PRICING_TIER_2_RIGHT_FOR_YOU_HEADING = "Right for you if:";

export const PRICING_TIER_2_RIGHT_FOR_YOU =
  "$10M+ GMV, marketing and finance teams that need to agree on channel performance before dollars move.";

export const PRICING_TIER_2_PLUS_HEADING = `Everything in ${PRICING_TIER_1_NAME}, plus:`;

export const PRICING_TIER_2_FEATURES = [
  "10,000 verified orders/month",
  "AI integrations — agents query verified revenue and simulation outputs directly",
  "Deterministic budget simulation — model reallocation scenarios against your verified transaction baseline before committing spend",
  "Simulation outputs are human-reviewable and agent-queryable — same signed, versioned artifact standard as verification outputs",
  "Unlimited users — no seat tax on your finance, marketing, or leadership team",
] as const;

export const PRICING_TIER_2_OVERAGE =
  "$0.05/order beyond 10,000 · Maximum bill: $1,279";

export const PRICING_TIER_2_REPLACES_HEADING = "What this replaces:";

export const PRICING_TIER_2_REPLACES_ITEMS = [
  "Reallocating spend based on ad platform ROAS your teams can't independently verify.",
  "Black-box recommendations with no auditable evidence trail.",
] as const;

export const PRICING_TIER_2_BADGE_LABEL = "Most popular";
export const PRICING_TIER_2_CTA_LABEL = "Contact sales";
