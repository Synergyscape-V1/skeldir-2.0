"use client";

import { useRouter } from "next/navigation";
import { SECTION_DISPLAY_TITLE_CLASS } from "@/components/layout/sectionDisplayFont";
import { PricingCardFeatureRow } from "@/components/pricing/PricingCardFeatureRow";
import {
  PRICING_CARD_AUDIENCE_CLASS,
  PRICING_CARD_FEATURE_LIST_CLASS,
  PRICING_CARD_REPLACES_BLOCK_CLASS,
  PRICING_CARD_REPLACES_LIST_CLASS,
  PRICING_CARD_ROOT_CLASS,
  PRICING_CARD_SUBHEADING_CLASS,
  PRICING_CARD_TIER_NAME_CLASS,
} from "@/components/pricing/pricingCardTypography";
import {
  PRICING_TIER_1_AUDIENCE,
  PRICING_TIER_1_FEATURES,
  PRICING_TIER_1_NAME,
  PRICING_TIER_1_PRICE,
  PRICING_TIER_1_PRICE_SUFFIX,
  PRICING_TIER_1_REPLACES_HEADING,
  PRICING_TIER_1_REPLACES_ITEMS,
} from "@/components/pricing/pricingTier1Copy";

type PricingTier1CardProps = {
  ctaLabel: string;
  ctaHeight?: number;
};

export function PricingTier1Card({
  ctaLabel,
  ctaHeight = 48,
}: PricingTier1CardProps) {
  const router = useRouter();

  return (
    <div
      className={`pricing-tier-1-card ${PRICING_CARD_ROOT_CLASS} ${SECTION_DISPLAY_TITLE_CLASS}`}
      style={{
        backgroundColor: "#FFFFFF",
        border: "1px solid #E5E7EB",
        borderRadius: "16px",
        boxShadow: "0px 4px 24px rgba(0, 0, 0, 0.08)",
        padding: "32px 28px",
        display: "flex",
        flexDirection: "column",
        transform: "scale(0.97)",
        opacity: 0.95,
        transition: "transform 0.3s ease, opacity 0.3s ease",
      }}
    >
      <h3 className={PRICING_CARD_TIER_NAME_CLASS}>{PRICING_TIER_1_NAME}</h3>

      <div
        style={{
          display: "inline-flex",
          alignItems: "baseline",
          marginTop: "8px",
        }}
      >
        <span
          style={{
            fontSize: "48px",
            fontWeight: 700,
            lineHeight: 1,
            letterSpacing: "-0.02em",
            color: "#111827",
          }}
        >
          {PRICING_TIER_1_PRICE}
        </span>
        <span
          style={{
            fontSize: "18px",
            fontWeight: 400,
            lineHeight: 1.2,
            color: "#6B7280",
            marginLeft: "4px",
          }}
        >
          {PRICING_TIER_1_PRICE_SUFFIX}
        </span>
      </div>

      <p className={PRICING_CARD_AUDIENCE_CLASS}>{PRICING_TIER_1_AUDIENCE}</p>

      <div className={PRICING_CARD_FEATURE_LIST_CLASS}>
        {PRICING_TIER_1_FEATURES.map((feature) => (
          <PricingCardFeatureRow key={feature} text={feature} />
        ))}
      </div>

      <div className={PRICING_CARD_REPLACES_BLOCK_CLASS}>
        <h4 className={PRICING_CARD_SUBHEADING_CLASS}>{PRICING_TIER_1_REPLACES_HEADING}</h4>
        <div className={PRICING_CARD_REPLACES_LIST_CLASS}>
          {PRICING_TIER_1_REPLACES_ITEMS.map((item) => (
            <PricingCardFeatureRow key={item} text={item} />
          ))}
        </div>
      </div>

      <button
        type="button"
        onClick={() => router.push("/signup")}
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          width: "100%",
          height: `${ctaHeight}px`,
          backgroundColor: "#2563EB",
          color: "#FFFFFF",
          fontSize: "17px",
          fontWeight: 600,
          letterSpacing: "0.02em",
          border: "none",
          borderRadius: "8px",
          cursor: "pointer",
          marginTop: "28px",
          transition: "background-color 150ms ease",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = "#1D4ED8";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = "#2563EB";
        }}
      >
        {ctaLabel}
      </button>
    </div>
  );
}
