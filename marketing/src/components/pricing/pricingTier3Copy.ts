import { PRICING_TIER_2_NAME } from "@/components/pricing/pricingTier2Copy";

/** Tier 3 pricing card — single source of truth (home + /pricing) */
export const PRICING_TIER_3_NAME = "Infrastructure";

export const PRICING_TIER_3_PRICE = "Custom";
export const PRICING_TIER_3_PRICE_SUFFIX = "";

export const PRICING_TIER_3_HOOK =
  "Can I deliver verified revenue proof to clients without rebuilding the reconciliation stack for each one?";

export const PRICING_TIER_3_RIGHT_FOR_YOU_HEADING = "Right for you if:";

export const PRICING_TIER_3_RIGHT_FOR_YOU =
  "Performance agencies or multi-brand operators where client trust depends on independently verified, not platform-reported, revenue data.";

export const PRICING_TIER_3_PLUS_HEADING = `Everything in ${PRICING_TIER_2_NAME}, plus:`;

export const PRICING_TIER_3_FEATURES = [
  "Multi-account verified order reconciliation — one trust layer, unlimited brands or clients",
  "Agent authority controls — define query scope, proposal boundaries, and human-approval gates per account",
  "Signed verification signals routed automatically to downstream systems — CRMs, BI tools, budget automations",
  "Branded client-facing verification outputs — signed, versioned, audit-grade",
  "Contractual uptime and response SLAs · Custom volume and integrations",
] as const;

export const PRICING_TIER_3_REPLACES_HEADING = "What this replaces:";

export const PRICING_TIER_3_REPLACES_ITEMS = [
  "Rebuilding reconciliation logic per client.",
  "Delivering reports your clients can't independently audit.",
  "AI Agents acting on platform self-reports your own team doesn't trust.",
] as const;

export const PRICING_TIER_3_CTA_LABEL = "Contact sales";
