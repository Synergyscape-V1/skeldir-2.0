"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SECTION_DISPLAY_TITLE_CLASS } from "@/components/layout/sectionDisplayFont";
import { PricingCardFeatureRow } from "@/components/pricing/PricingCardFeatureRow";
import {
  PRICING_CARD_AUDIENCE_CLASS,
  PRICING_CARD_PLUS_FEATURE_LIST_CLASS,
  PRICING_CARD_PLUS_HEADING_CLASS,
  PRICING_CARD_REPLACES_BLOCK_CLASS,
  PRICING_CARD_REPLACES_LIST_CLASS,
  PRICING_CARD_ROOT_CLASS,
  PRICING_CARD_SUBHEADING_CLASS,
  PRICING_CARD_TIER_NAME_CLASS,
} from "@/components/pricing/pricingCardTypography";
import {
  PRICING_TIER_3_AUDIENCE,
  PRICING_TIER_3_CTA_LABEL,
  PRICING_TIER_3_FEATURES,
  PRICING_TIER_3_NAME,
  PRICING_TIER_3_PLUS_HEADING,
  PRICING_TIER_3_PRICE,
  PRICING_TIER_3_PRICE_SUFFIX,
  PRICING_TIER_3_REPLACES_HEADING,
  PRICING_TIER_3_REPLACES_ITEMS,
} from "@/components/pricing/pricingTier3Copy";

type PricingTier3CardProps = {
  variant: "home" | "pricing-page";
  ctaLabel?: string;
  ctaHeight?: number;
};

export function PricingTier3Card({
  variant,
  ctaLabel = PRICING_TIER_3_CTA_LABEL,
  ctaHeight,
}: PricingTier3CardProps) {
  const [email, setEmail] = useState("");
  const router = useRouter();
  const buttonHeight = ctaHeight ?? (variant === "pricing-page" ? 52 : 48);
  const isPricingPage = variant === "pricing-page";

  const handleAction = () => {
    if (isPricingPage) {
      router.push("/book-demo");
      return;
    }
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      alert("Please enter a valid email address");
      return;
    }
    router.push(`/contact?tier=enterprise&email=${encodeURIComponent(email)}`);
  };

  return (
    <div
      className={`pricing-tier-3-card ${PRICING_CARD_ROOT_CLASS} ${SECTION_DISPLAY_TITLE_CLASS}`}
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
      <h3 className={PRICING_CARD_TIER_NAME_CLASS}>{PRICING_TIER_3_NAME}</h3>

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
          {PRICING_TIER_3_PRICE}
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
          {PRICING_TIER_3_PRICE_SUFFIX}
        </span>
      </div>

      <p className={PRICING_CARD_AUDIENCE_CLASS}>{PRICING_TIER_3_AUDIENCE}</p>

      <h4 className={PRICING_CARD_PLUS_HEADING_CLASS}>{PRICING_TIER_3_PLUS_HEADING}</h4>

      <div className={PRICING_CARD_PLUS_FEATURE_LIST_CLASS}>
        {PRICING_TIER_3_FEATURES.map((feature) => (
          <PricingCardFeatureRow key={feature} text={feature} />
        ))}
      </div>

      <div className={PRICING_CARD_REPLACES_BLOCK_CLASS}>
        <h4 className={PRICING_CARD_SUBHEADING_CLASS}>{PRICING_TIER_3_REPLACES_HEADING}</h4>
        <div className={PRICING_CARD_REPLACES_LIST_CLASS}>
          {PRICING_TIER_3_REPLACES_ITEMS.map((item) => (
            <PricingCardFeatureRow key={item} text={item} />
          ))}
        </div>
      </div>

      <div style={{ marginTop: "24px", marginBottom: "16px" }}>
        <label className="sr-only" htmlFor="email-tier-3">
          What&apos;s your work email?
        </label>
        <input
          type="email"
          id="email-tier-3"
          placeholder="What's your work email?"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="email-input"
          style={{
            width: "100%",
            height: "48px",
            padding: "12px 16px",
            fontSize: "16px",
            border: "1px solid rgba(0, 0, 0, 0.15)",
            borderRadius: "8px",
            backgroundColor: "white",
            color: "#1a1a1a",
            outline: "none",
          }}
        />
      </div>

      <button
        type="button"
        onClick={handleAction}
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          width: "100%",
          height: `${buttonHeight}px`,
          backgroundColor: "#FFFFFF",
          color: isPricingPage ? "#1a1a1a" : "#2563EB",
          fontSize: "17px",
          fontWeight: 600,
          letterSpacing: "0.02em",
          border: isPricingPage ? "2px solid #1a1a1a" : "2px solid #2563EB",
          borderRadius: "8px",
          cursor: "pointer",
          transition: isPricingPage ? "all 0.2s" : "background-color 150ms ease",
        }}
        onMouseEnter={(e) => {
          if (isPricingPage) {
            e.currentTarget.style.backgroundColor = "#f9fafb";
            e.currentTarget.style.transform = "translateY(-1px)";
          } else {
            e.currentTarget.style.backgroundColor = "#EFF6FF";
          }
        }}
        onMouseLeave={(e) => {
          if (isPricingPage) {
            e.currentTarget.style.backgroundColor = "#FFFFFF";
            e.currentTarget.style.transform = "none";
          } else {
            e.currentTarget.style.backgroundColor = "#FFFFFF";
          }
        }}
      >
        {ctaLabel}
      </button>
    </div>
  );
}
