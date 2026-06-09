"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SECTION_DISPLAY_TITLE_CLASS } from "@/components/layout/sectionDisplayFont";
import { PricingCardFeatureRow } from "@/components/pricing/PricingCardFeatureRow";
import {
  PRICING_CARD_AUDIENCE_CLASS,
  PRICING_CARD_BODY_CLASS,
  PRICING_CARD_PLUS_FEATURE_LIST_CLASS,
  PRICING_CARD_PLUS_HEADING_CLASS,
  PRICING_CARD_REPLACES_BLOCK_CLASS,
  PRICING_CARD_REPLACES_LIST_CLASS,
  PRICING_CARD_ROOT_CLASS,
  PRICING_CARD_SUBHEADING_CLASS,
  PRICING_CARD_TIER_NAME_CLASS,
} from "@/components/pricing/pricingCardTypography";
import {
  PRICING_TIER_2_BADGE_LABEL,
  PRICING_TIER_2_CTA_LABEL,
  PRICING_TIER_2_FEATURES,
  PRICING_TIER_2_HOOK,
  PRICING_TIER_2_NAME,
  PRICING_TIER_2_OVERAGE,
  PRICING_TIER_2_PLUS_HEADING,
  PRICING_TIER_2_PRICE,
  PRICING_TIER_2_PRICE_SUFFIX,
  PRICING_TIER_2_REPLACES_HEADING,
  PRICING_TIER_2_REPLACES_ITEMS,
  PRICING_TIER_2_RIGHT_FOR_YOU,
  PRICING_TIER_2_RIGHT_FOR_YOU_HEADING,
} from "@/components/pricing/pricingTier2Copy";

type PricingTier2CardProps = {
  variant: "home" | "pricing-page";
  ctaLabel?: string;
  ctaHeight?: number;
};

export function PricingTier2Card({
  variant,
  ctaLabel = PRICING_TIER_2_CTA_LABEL,
  ctaHeight,
}: PricingTier2CardProps) {
  const [email, setEmail] = useState("");
  const router = useRouter();
  const badgeTop = variant === "pricing-page" ? "-18px" : "-10px";
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
    router.push(`/contact?tier=plus&email=${encodeURIComponent(email)}`);
  };

  return (
    <div style={{ position: "relative" }}>
      <div
        className={`pricing-tier-2-badge ${SECTION_DISPLAY_TITLE_CLASS}`}
        style={{
          position: "absolute",
          top: badgeTop,
          left: "50%",
          transform: "translateX(-50%)",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          backgroundColor: "#2563EB",
          color: "#FFFFFF",
          fontSize: "15px",
          fontWeight: 600,
          letterSpacing: "0.02em",
          padding: "8px 16px",
          borderRadius: "20px",
          zIndex: 3,
          whiteSpace: "nowrap",
        }}
      >
        {PRICING_TIER_2_BADGE_LABEL}
      </div>

      <div
        className={`pricing-card pricing-tier-2-card ${PRICING_CARD_ROOT_CLASS} ${SECTION_DISPLAY_TITLE_CLASS}`}
        style={{
          backgroundColor: "#FFFFFF",
          border: "2px solid #2563EB",
          borderRadius: "16px",
          boxShadow:
            "0px 12px 40px rgba(37, 99, 235, 0.25), 0px 4px 16px rgba(37, 99, 235, 0.15)",
          padding: "32px 28px",
          display: "flex",
          flexDirection: "column",
          position: "relative",
          zIndex: 2,
          transform: "scale(1.05)",
          transition: "transform 0.3s ease, box-shadow 0.3s ease",
        }}
      >
        <h3 className={PRICING_CARD_TIER_NAME_CLASS} style={{ marginTop: "16px" }}>
          {PRICING_TIER_2_NAME}
        </h3>

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
            {PRICING_TIER_2_PRICE}
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
            {PRICING_TIER_2_PRICE_SUFFIX}
          </span>
        </div>

        <p className={PRICING_CARD_BODY_CLASS} style={{ marginTop: "20px" }}>
          {PRICING_TIER_2_HOOK}
        </p>

        <h4 className={PRICING_CARD_SUBHEADING_CLASS} style={{ marginTop: "20px" }}>
          {PRICING_TIER_2_RIGHT_FOR_YOU_HEADING}
        </h4>
        <p className={PRICING_CARD_AUDIENCE_CLASS} style={{ marginTop: "8px" }}>
          {PRICING_TIER_2_RIGHT_FOR_YOU}
        </p>

        <h4 className={PRICING_CARD_PLUS_HEADING_CLASS}>{PRICING_TIER_2_PLUS_HEADING}</h4>

        <div className={PRICING_CARD_PLUS_FEATURE_LIST_CLASS}>
          {PRICING_TIER_2_FEATURES.map((feature) => (
            <PricingCardFeatureRow key={feature} text={feature} />
          ))}
        </div>

        <p
          className={PRICING_CARD_BODY_CLASS}
          style={{ marginTop: "16px", fontSize: "14px", color: "#6B7280" }}
        >
          {PRICING_TIER_2_OVERAGE}
        </p>

        <div className={PRICING_CARD_REPLACES_BLOCK_CLASS}>
          <h4 className={PRICING_CARD_SUBHEADING_CLASS}>{PRICING_TIER_2_REPLACES_HEADING}</h4>
          <div className={PRICING_CARD_REPLACES_LIST_CLASS}>
            {PRICING_TIER_2_REPLACES_ITEMS.map((item) => (
              <PricingCardFeatureRow key={item} text={item} />
            ))}
          </div>
        </div>

        <div style={{ marginTop: "24px", marginBottom: "16px" }}>
          <label className="sr-only" htmlFor="email-tier-2">
            What&apos;s your work email?
          </label>
          <input
            type="email"
            id="email-tier-2"
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
    </div>
  );
}
