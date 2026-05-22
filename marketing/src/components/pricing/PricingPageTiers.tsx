"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PricingTier1Card } from "@/components/pricing/PricingTier1Card";
import { PricingTier2Card } from "@/components/pricing/PricingTier2Card";
import { PricingTier3Card } from "@/components/pricing/PricingTier3Card";
import { PRICING_TIER_1_CTA_PRICING_PAGE } from "@/components/pricing/pricingTier1Copy";

// ============================================================================
// PRICING TIERS SECTION - ADAPTED FOR PRICING PAGE
// Includes Email Capture and Conversion Optimization
// ============================================================================

// =============================================================================
// ICONS
// =============================================================================
function CheckmarkIcon() {
    return (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0, marginTop: "2px" }}>
            <path d="M13.5 4.5L6 12L2.5 8.5" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    );
}





function FeatureItem({ text }: { text: string }) {
    return (
        <div style={{ display: "flex", flexDirection: "row", alignItems: "flex-start", gap: "10px" }}>
            <CheckmarkIcon />
            <span style={{ fontFamily: "Inter, sans-serif", fontSize: "14px", fontWeight: 400, lineHeight: 1.5, color: "#374151" }}>{text}</span>
        </div>
    );
}

function BenefitItem({ text }: { text: string }) {
    return (
        <div style={{ display: "flex", flexDirection: "row", alignItems: "flex-start", gap: "10px" }}>
            <CheckmarkIcon />
            <span style={{ fontFamily: "Inter, sans-serif", fontSize: "14px", fontWeight: 400, lineHeight: 1.5, color: "#374151" }}>{text}</span>
        </div>
    );
}

// =============================================================================
// CARD 1: VERIFY - shared copy (pricingTier1Copy.ts)
// =============================================================================
function Card1() {
    return (
        <PricingTier1Card
            ctaLabel={PRICING_TIER_1_CTA_PRICING_PAGE}
            ctaHeight={52}
        />
    );
}

// =============================================================================
// CARD 2: OPTIMIZE - shared copy (pricingTier2Copy.ts)
// =============================================================================
function Card2() {
    return <PricingTier2Card variant="pricing-page" />;
}

// =============================================================================
// CARD 3: INFRASTRUCTURE - shared copy (pricingTier3Copy.ts)
// =============================================================================
function Card3() {
    return <PricingTier3Card variant="pricing-page" />;
}

// =============================================================================
// MAIN SECTION EXPORT
// =============================================================================
export function PricingPageTiers() {
    return (
        <section className="pricing-page-tiers-section" style={{ backgroundColor: "#FFFFFF", paddingBottom: "80px", width: "100%", position: "relative" }}>
            <div style={{ maxWidth: "1200px", marginLeft: "auto", marginRight: "auto", paddingLeft: "24px", paddingRight: "24px", position: "relative", zIndex: 2 }}>
                <div className="pricing-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "24px", alignItems: "stretch" }}>
                    <Card1 />
                    <Card2 />
                    <Card3 />
                </div>
            </div>

            <style jsx global>{`
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
          .pricing-page-tiers-section {
            padding-bottom: 48px !important;
          }

          .pricing-grid {
            grid-template-columns: 1fr !important;
            max-width: 100% !important;
            gap: 24px !important;
            padding: 0 20px !important;
          }

          .pricing-page-tiers-section > div {
            padding-left: 0 !important;
            padding-right: 0 !important;
          }

          .pricing-page-tiers-section [style*="padding: 32px 28px"] {
            padding: 24px 20px !important;
          }

          .pricing-page-tiers-section [style*="transform: scale"] {
            transform: scale(1) !important;
            opacity: 1 !important;
          }

          .pricing-page-tiers-section h3 {
            font-size: 22px !important;
            line-height: 1.3 !important;
          }

          .pricing-page-tiers-section [style*="fontSize: 48px"] {
            font-size: 40px !important;
          }

          .pricing-page-tiers-section button {
            min-height: 48px !important;
            height: 48px !important;
            font-size: 16px !important;
          }
        }
      `}</style>
        </section>
    );
}
