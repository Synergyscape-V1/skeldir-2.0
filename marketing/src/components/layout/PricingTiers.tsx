"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

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
// CARD 1: "GET THE TRUTH" - TIER 1
// Border: 1px solid #E5E7EB, Shadow: rgba(0,0,0,0.08), CTA: FILLED
// =============================================================================
function Card1() {
  const router = useRouter();
  const features = [
    "See real revenue next to what ad platforms report",
    "Attribution across up to 3 ad platforms",
    "Automatic reconciliation (no spreadsheets)",
    "Live in 48 hours with self-serve setup",
    "Standard email support included",
    "AI-generated explanations that clarify why your numbers look the way they do",
  ];

  const benefits = [
    "Spot inflated or misleading performance numbers",
    "Stop making decisions based on bad data",
    "Save 10\u201315 hours per week on reporting", // en-dash (–) U+2013
  ];

  const handleClick = () => {
    router.push('/signup');
  };

  return (
    <div
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
      {/* Tier Name */}
      <h3
        style={{
          fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
          fontSize: "24px",
          fontWeight: 700,
          lineHeight: 1.2,
          color: "#111827",
          margin: 0,
        }}
      >
        Get the Truth
      </h3>

      {/* Price */}
      <div
        style={{
          display: "inline-flex",
          alignItems: "baseline",
          marginTop: "8px",
        }}
      >
        <span
          style={{
            fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            fontSize: "48px",
            fontWeight: 700,
            color: "#111827",
          }}
        >
          $149
        </span>
        <span
          style={{
            fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            fontSize: "16px",
            fontWeight: 400,
            color: "#6B7280",
            marginLeft: "2px",
          }}
        >
          /month
        </span>
      </div>

        {/* Best for Section */}
        <div style={{ marginTop: "20px" }}>
          <span
            style={{
              fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
              fontSize: "12px",
              fontWeight: 300,
              color: "#111827",
            }}
          >
            Best for{" "}
          </span>
        <span
          style={{
            fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            fontSize: "12px",
            fontWeight: 300,
            lineHeight: 1.5,
            color: "#111827",
          }}
        >
          business owners who want to see what's really happening with their ad spend.
        </span>
      </div>

      {/* Feature List */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "10px",
          marginTop: "32px",
        }}
      >
        {features.map((feature, index) => (
          <FeatureItem key={index} text={feature} />
        ))}
      </div>

      {/* What this helps you do Section */}
      <div style={{ marginTop: "24px" }}>
        <h4
          style={{
            fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            fontSize: "14px",
            fontWeight: 600,
            color: "#111827",
            margin: 0,
            marginBottom: "10px",
          }}
        >
          What this helps you do:
        </h4>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          {benefits.map((benefit, index) => (
            <BenefitItem key={index} text={benefit} />
          ))}
        </div>
      </div>

      {/* CTA Button - FILLED Style */}
      <button
        onClick={handleClick}
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          width: "100%",
          height: "48px",
          backgroundColor: "#2563EB",
          color: "#FFFFFF",
          fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
          fontSize: "16px",
          fontWeight: 600,
          border: "none",
          borderRadius: "8px",
          cursor: "pointer",
          marginTop: "24px",
          transition: "background-color 150ms ease",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = "#1D4ED8";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = "#2563EB";
        }}
      >
        GET STARTED
      </button>

    </div>
  );
}

// =============================================================================
// CARD 2: "OPTIMIZE FOR PROFIT" - TIER 2 (EMPHASIZED)
// Border: 2px solid #2563EB, Shadow: rgba(37,99,235,0.15), CTA: OUTLINED
// Has floating "Most popular" badge above card
// =============================================================================
function Card2() {
  const [email, setEmail] = useState("");
  const router = useRouter();
  const features = [
    "Connect all ad platforms (no limits)",
    "See which results are reliable and which aren't",
    "Test budget changes before spending real money",
    "Clear guidance on where to increase or pull back spend",
    "Priority support for active decision questions",
    "Full Proprietary Intelligence models with reliability indicators across channels",
    "AI-assisted budget analysis that explains tradeoffs and constraints",
  ];

  const benefits = [
    "Reduce wasted ad spend",
    "Move money with more confidence",
    "Justify decisions with clear evidence",
  ];

  const handleAction = () => {
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      alert("Please enter a valid email address");
      return;
    }
    router.push(`/contact?tier=plus&email=${encodeURIComponent(email)}`);
  };

  return (
    <div style={{ position: "relative" }}>
      {/* Floating "Most popular" Badge - ABOVE card */}
      <div
        style={{
          position: "absolute",
          top: "-10px",
          left: "50%",
          transform: "translateX(-50%)",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          gap: "6px",
          backgroundColor: "#2563EB",
          color: "#FFFFFF",
          fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
          fontSize: "14px",
          fontWeight: 600,
          padding: "8px 16px",
          borderRadius: "20px",
          zIndex: 3,
          whiteSpace: "nowrap",
        }}
      >
        Most popular
      </div>

      {/* Card Container */}
      <div
        className="pricing-card"
        style={{
          backgroundColor: "#FFFFFF",
          border: "2px solid #2563EB",
          borderRadius: "16px",
          boxShadow: "0px 12px 40px rgba(37, 99, 235, 0.25), 0px 4px 16px rgba(37, 99, 235, 0.15)",
          padding: "32px 28px",
          display: "flex",
          flexDirection: "column",
          position: "relative",
          zIndex: 2,
          transform: "scale(1.05)",
          transition: "transform 0.3s ease, box-shadow 0.3s ease",
          }}
        >
        {/* Tier Name */}
        <h3
          style={{
            fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            fontSize: "24px",
            fontWeight: 700,
            lineHeight: 1.2,
            color: "#111827",
            margin: 0,
            marginTop: "16px",
          }}
        >
          Optimize for Profit
        </h3>

        {/* Price */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "baseline",
            marginTop: "8px",
          }}
        >
          <span
            style={{
              fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
              fontSize: "48px",
              fontWeight: 700,
              color: "#111827",
            }}
          >
            $349
          </span>
          <span
            style={{
              fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
              fontSize: "16px",
              fontWeight: 400,
              color: "#6B7280",
              marginLeft: "2px",
            }}
          >
            /month
          </span>
        </div>

        {/* Best for Section */}
        <div style={{ marginTop: "20px" }}>
          <span
            style={{
              fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
              fontSize: "12px",
              fontWeight: 300,
              color: "#111827",
            }}
          >
            Perfect for{" "}
          </span>
          <span
            style={{
              fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
              fontSize: "12px",
              fontWeight: 300,
              lineHeight: 1.5,
              color: "#111827",
            }}
          >
            owners and operators actively reallocating ad budget who value confidence before moving real dollars.
          </span>
        </div>

        {/* Everything in Tier 1, plus: Header */}
        <h4
          style={{
            fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            fontSize: "14px",
            fontWeight: 600,
            color: "#374151",
            margin: 0,
            marginTop: "32px",
          }}
        >
          Everything in Tier 1, plus:
        </h4>

        {/* Feature List */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "10px",
            marginTop: "12px",
          }}
        >
          {features.map((feature, index) => (
            <FeatureItem key={index} text={feature} />
          ))}
        </div>

        {/* What this helps you do Section */}
        <div style={{ marginTop: "24px" }}>
          <h4
            style={{
              fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
              fontSize: "14px",
              fontWeight: 600,
              color: "#111827",
              margin: 0,
              marginBottom: "10px",
            }}
          >
            What this helps you do:
          </h4>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
            }}
          >
            {benefits.map((benefit, index) => (
              <BenefitItem key={index} text={benefit} />
            ))}
          </div>
        </div>

        {/* Email Capture */}
        <div style={{ marginTop: "24px", marginBottom: "16px" }}>
          <label className="sr-only" htmlFor="email-tier-2">What&apos;s your work email?</label>
          <input
            type="email"
            id="email-tier-2"
            placeholder="What's your work email?"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="email-input"
            style={{ width: "100%", height: "48px", padding: "12px 16px", fontSize: "15px", border: "1px solid rgba(0, 0, 0, 0.15)", borderRadius: "8px", backgroundColor: "white", color: "#1a1a1a", outline: "none" }}
          />
        </div>

        {/* CTA Button - OUTLINED Style */}
        <button
          onClick={handleAction}
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            width: "100%",
            height: "48px",
            backgroundColor: "#FFFFFF",
            color: "#2563EB",
            fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            fontSize: "16px",
            fontWeight: 600,
            border: "2px solid #2563EB",
            borderRadius: "8px",
            cursor: "pointer",
            marginTop: "0",
            transition: "background-color 150ms ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = "#EFF6FF";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = "#FFFFFF";
          }}
        >
          Contact sales
        </button>
      </div>
    </div>
  );
}

// =============================================================================
// CARD 3: "RUN AT SCALE" - TIER 3
// Border: 1px solid #E5E7EB, Shadow: rgba(0,0,0,0.08), CTA: OUTLINED
// Has 6 features (not 5)
// =============================================================================
function Card3() {
  const [email, setEmail] = useState("");
  const router = useRouter();
  const features = [
    "API access for integrations and automation",
    "White-label reporting with your branding",
    "Guaranteed response times and priority handling",
    "Guaranteed response times and priority",
    "Named account contact for coordination",
    "Built for multi-account, business-critical use",
    "AI-generated explanations designed and tailored for client-facing delivery",
  ];

  const benefits = [
    "Reduce operational overhead",
    "Standardize reporting across teams or clients",
    "Rely on Skeldir as core infrastructure",
  ];

  const handleAction = () => {
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      alert("Please enter a valid email address");
      return;
    }
    router.push(`/contact?tier=enterprise&email=${encodeURIComponent(email)}`);
  };

  return (
    <div
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
      {/* Tier Name */}
      <h3
        style={{
          fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
          fontSize: "24px",
          fontWeight: 700,
          lineHeight: 1.2,
          color: "#111827",
          margin: 0,
          marginTop: "16px",
        }}
      >
        Run at Scale
      </h3>

      {/* Price */}
      <div
        style={{
          display: "inline-flex",
          alignItems: "baseline",
          marginTop: "8px",
        }}
      >
        <span
          style={{
            fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            fontSize: "48px",
            fontWeight: 700,
            color: "#111827",
          }}
        >
          $749
        </span>
        <span
          style={{
            fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            fontSize: "16px",
            fontWeight: 400,
            color: "#6B7280",
            marginLeft: "2px",
          }}
        >
          /month
        </span>
      </div>

      {/* Best for Section */}
      <div style={{ marginTop: "20px" }}>
        <span
          style={{
            fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            fontSize: "12px",
            fontWeight: 300,
            color: "#111827",
          }}
        >
          Specifically made for{" "}
        </span>
        <span
          style={{
            fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            fontSize: "12px",
            fontWeight: 300,
            lineHeight: 1.5,
            color: "#111827",
          }}
        >
          agencies or businesses managing multiple brands or accounts.
        </span>
      </div>

      {/* Everything in Tier 2, plus: Header */}
      <h4
        style={{
          fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
          fontSize: "14px",
          fontWeight: 600,
          color: "#374151",
          margin: 0,
          marginTop: "32px",
        }}
      >
        Everything in Tier 2, plus:
      </h4>

      {/* Feature List - 6 items */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "10px",
          marginTop: "12px",
        }}
      >
        {features.map((feature, index) => (
          <FeatureItem key={index} text={feature} />
        ))}
      </div>

      {/* What this helps you do Section */}
      <div style={{ marginTop: "24px" }}>
        <h4
          style={{
            fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            fontSize: "14px",
            fontWeight: 600,
            color: "#111827",
            margin: 0,
            marginBottom: "10px",
          }}
        >
          What this helps you do:
        </h4>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          {benefits.map((benefit, index) => (
            <BenefitItem key={index} text={benefit} />
          ))}
        </div>
      </div>

      {/* Email Capture */}
      <div style={{ marginTop: "24px", marginBottom: "16px" }}>
        <label className="sr-only" htmlFor="email-tier-3">What&apos;s your work email?</label>
        <input
          type="email"
          id="email-tier-3"
          placeholder="What's your work email?"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="email-input"
          style={{ width: "100%", height: "48px", padding: "12px 16px", fontSize: "15px", border: "1px solid rgba(0, 0, 0, 0.15)", borderRadius: "8px", backgroundColor: "white", color: "#1a1a1a", outline: "none" }}
        />
      </div>

      {/* CTA Button - OUTLINED Style */}
      <button
        onClick={handleAction}
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          width: "100%",
          height: "48px",
          backgroundColor: "#FFFFFF",
          color: "#2563EB",
          fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
          fontSize: "16px",
          fontWeight: 600,
          border: "2px solid #2563EB",
          borderRadius: "8px",
          cursor: "pointer",
          marginTop: "0",
          transition: "background-color 150ms ease",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = "#EFF6FF";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = "#FFFFFF";
        }}
      >
        Contact sales
      </button>
    </div>
  );
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
