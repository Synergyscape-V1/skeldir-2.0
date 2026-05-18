"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PricingTier1Card } from "@/components/pricing/PricingTier1Card";
import { PricingTier2Card } from "@/components/pricing/PricingTier2Card";
import { PricingTier3Card } from "@/components/pricing/PricingTier3Card";
import {
  PRICING_TIER_1_CTA_HOME,
} from "@/components/pricing/pricingTier1Copy";

// ============================================================================
// PRICING TIERS SECTION
// Reference: Pricing Tiers Section Forensic Visual Specification v1.0.0
// Pixel-Perfect Implementation per Exact Specifications
// ============================================================================

// =============================================================================
// CHECKMARK ICON COMPONENT
// Size: 16x16px, Color: #2563EB (Skeldir Blue), Stroke: 2px
// =============================================================================
function CheckmarkIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{
        flexShrink: 0,
        marginTop: "2px",
      }}
    >
      <path
        d="M13.5 4.5L6 12L2.5 8.5"
        stroke="#2563EB"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// =============================================================================
// TRUST BADGE ICON (Small checkmark in circle)
// =============================================================================
function TrustBadgeIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ flexShrink: 0 }}
    >
      <circle cx="7" cy="7" r="6.5" stroke="#6B7280" strokeWidth="1" />
      <path
        d="M4 7L6 9L10 5"
        stroke="#6B7280"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// =============================================================================
// STAR ICON for "Most popular" badge
// =============================================================================
function StarIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ flexShrink: 0 }}
    >
      <path
        d="M7 1L8.5 5H12.5L9.25 7.5L10.5 12L7 9.5L3.5 12L4.75 7.5L1.5 5H5.5L7 1Z"
        fill="#FFFFFF"
      />
    </svg>
  );
}

// =============================================================================
// FEATURE LIST ITEM COMPONENT
// =============================================================================
function FeatureItem({ text }: { text: string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "row",
        alignItems: "flex-start",
        gap: "10px",
      }}
    >
      <CheckmarkIcon />
      <span
        style={{
          fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
          fontSize: "14px",
          fontWeight: 400,
          lineHeight: 1.5,
          color: "#374151",
        }}
      >
        {text}
      </span>
    </div>
  );
}

// =============================================================================
// BENEFIT LIST ITEM COMPONENT
// =============================================================================
function BenefitItem({ text }: { text: string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "row",
        alignItems: "flex-start",
        gap: "10px",
      }}
    >
      <CheckmarkIcon />
      <span
        style={{
          fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
          fontSize: "14px",
          fontWeight: 400,
          lineHeight: 1.5,
          color: "#374151",
        }}
      >
        {text}
      </span>
    </div>
  );
}

// =============================================================================
// CARD 1: VERIFY - shared copy (pricingTier1Copy.ts)
// =============================================================================
function Card1() {
  return <PricingTier1Card ctaLabel={PRICING_TIER_1_CTA_HOME} />;
}

// =============================================================================
// CARD 2: OPTIMIZE - shared copy (pricingTier2Copy.ts)
// =============================================================================
function Card2() {
  return <PricingTier2Card variant="home" />;
}

// =============================================================================
// CARD 3: INFRASTRUCTURE - shared copy (pricingTier3Copy.ts)
// =============================================================================
function Card3() {
  return <PricingTier3Card variant="home" />;
}

// =============================================================================
// MAIN SECTION EXPORT
// =============================================================================
export function PricingTiers() {
  return (
    <section
      className="pricing-tiers-section"
      style={{
        backgroundColor: "#FFFFFF",
        paddingTop: "80px",
        paddingBottom: "80px",
        paddingLeft: "0px",
        paddingRight: "0px",
        width: "100%",
        position: "relative",
      }}
    >
      {/* Gradient transition overlay at the top */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: "120px",
          background: "linear-gradient(to bottom, rgba(255, 255, 255, 1) 0%, rgba(255, 255, 255, 1) 100%)",
          pointerEvents: "none",
          zIndex: 1,
        }}
      />
      {/* Content Container */}
      <div
        style={{
          maxWidth: "1200px",
          marginLeft: "auto",
          marginRight: "auto",
          paddingLeft: "24px",
          paddingRight: "24px",
          position: "relative",
          zIndex: 2,
        }}
      >
        {/* 3-Card Grid */}
        <div
          className="pricing-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: "24px",
            alignItems: "stretch",
          }}
        >
          <Card1 />
          <Card2 />
          <Card3 />
        </div>
      </div>

      {/* Responsive Styles */}
      <style>{`
        .email-input:focus {
          border-color: #3b82f6 !important;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
        }
        @media (max-width: 1024px) {
          .pricing-grid {
            grid-template-columns: 1fr !important;
            max-width: 480px !important;
            margin: 0 auto !important;
          }
        }
        @media (max-width: 767px) {
          .pricing-tiers-section {
            padding-top: 48px !important;
            padding-bottom: 48px !important;
          }

          .pricing-grid {
            grid-template-columns: 1fr !important;
            max-width: 100% !important;
            gap: 24px !important;
          }

          .pricing-card {
            padding: 24px 20px !important;
            transform: scale(1) !important;
            opacity: 1 !important;
          }

          .pricing-card h3 {
            font-size: 22px !important;
            line-height: 1.3 !important;
          }

          .pricing-card span[style*="font-size: 48px"] {
            font-size: 40px !important;
          }

          .pricing-card button {
            min-height: 48px !important;
            height: 48px !important;
            font-size: 16px !important;
          }
        }
      `}</style>
    </section>
  );
}
