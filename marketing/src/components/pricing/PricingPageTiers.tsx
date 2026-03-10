"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

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
// CARD 1: "GET THE TRUTH" - TIER 1
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
    const benefits = ["Spot inflated or misleading performance numbers", "Stop making decisions based on bad data", "Save 10\u201315 hours per week on reporting"];

    const handleAction = () => {
        router.push('/signup');
    };

    return (
        <div style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB", borderRadius: "16px", boxShadow: "0px 4px 24px rgba(0, 0, 0, 0.08)", padding: "32px 28px", display: "flex", flexDirection: "column", transform: "scale(0.97)", opacity: 0.95, transition: "transform 0.3s ease, opacity 0.3s ease" }}>
            <h3 style={{ fontFamily: "Inter, sans-serif", fontSize: "24px", fontWeight: 700, lineHeight: 1.2, color: "#111827", margin: 0 }}>Get the Truth</h3>
            <div style={{ display: "inline-flex", alignItems: "baseline", marginTop: "8px" }}>
                <span style={{ fontFamily: "Inter, sans-serif", fontSize: "48px", fontWeight: 700, color: "#111827" }}>$199</span>
                <span style={{ fontFamily: "Inter, sans-serif", fontSize: "16px", fontWeight: 400, color: "#6B7280", marginLeft: "2px" }}>/month</span>
            </div>
            <div style={{ marginTop: "20px" }}>
                <span style={{ fontFamily: "Inter, sans-serif", fontSize: "12px", fontWeight: 300, color: "#111827" }}>Best for </span>
                <span style={{ fontFamily: "Inter, sans-serif", fontSize: "12px", fontWeight: 300, lineHeight: 1.5, color: "#111827" }}>business owners who want to see what&apos;s really happening with their ad spend.</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "32px" }}>
                {features.map((feature, index) => <FeatureItem key={index} text={feature} />)}
            </div>
            <div style={{ marginTop: "24px" }}>
                <h4 style={{ fontFamily: "Inter, sans-serif", fontSize: "14px", fontWeight: 600, color: "#111827", margin: 0, marginBottom: "10px" }}>What this helps you do:</h4>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {benefits.map((benefit, index) => <BenefitItem key={index} text={benefit} />)}
                </div>
            </div>

            <button
                onClick={handleAction}
                style={{ display: "flex", justifyContent: "center", alignItems: "center", width: "100%", height: "52px", backgroundColor: "#2563EB", color: "#FFFFFF", fontFamily: "Inter, sans-serif", fontSize: "16px", fontWeight: 600, border: "none", borderRadius: "8px", cursor: "pointer", transition: "all 0.2s", marginTop: "24px" }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "#1d4ed8"; e.currentTarget.style.transform = "translateY(-1px)"; e.currentTarget.style.boxShadow = "0 4px 12px rgba(37, 99, 235, 0.3)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "#2563EB"; e.currentTarget.style.transform = "none"; e.currentTarget.style.boxShadow = "none"; }}
            >
                Get started for $199/month
            </button>
        </div>
    );
}

// =============================================================================
// CARD 2: "OPTIMIZE FOR PROFIT" - TIER 2
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
    const benefits = ["Reduce wasted ad spend", "Move money with more confidence", "Justify decisions with clear evidence"];

    const handleAction = () => {
        router.push('/book-demo');
    };

    return (
        <div style={{ position: "relative" }}>
            <div style={{ position: "absolute", top: "-18px", left: "50%", transform: "translateX(-50%)", display: "flex", justifyContent: "center", alignItems: "center", gap: "6px", backgroundColor: "#2563EB", color: "#FFFFFF", fontFamily: "Inter, sans-serif", fontSize: "14px", fontWeight: 600, padding: "8px 16px", borderRadius: "20px", zIndex: 3, whiteSpace: "nowrap" }}>
                Most popular
            </div>
            <div style={{ backgroundColor: "#FFFFFF", border: "2px solid #2563EB", borderRadius: "16px", boxShadow: "0px 12px 40px rgba(37, 99, 235, 0.25), 0px 4px 16px rgba(37, 99, 235, 0.15)", padding: "32px 28px", display: "flex", flexDirection: "column", position: "relative", zIndex: 2, transform: "scale(1.05)", transition: "transform 0.3s ease, box-shadow 0.3s ease" }}>
                <h3 style={{ fontFamily: "Inter, sans-serif", fontSize: "24px", fontWeight: 700, lineHeight: 1.2, color: "#111827", margin: 0, marginTop: "16px" }}>Optimize for Profit</h3>
                <div style={{ display: "inline-flex", alignItems: "baseline", marginTop: "8px" }}>
                    <span style={{ fontFamily: "Inter, sans-serif", fontSize: "48px", fontWeight: 700, color: "#111827" }}>$499</span>
                    <span style={{ fontFamily: "Inter, sans-serif", fontSize: "16px", fontWeight: 400, color: "#6B7280", marginLeft: "2px" }}>/month</span>
                </div>
                <div style={{ marginTop: "20px" }}>
                    <span style={{ fontFamily: "Inter, sans-serif", fontSize: "12px", fontWeight: 300, color: "#111827" }}>Perfect for </span>
                    <span style={{ fontFamily: "Inter, sans-serif", fontSize: "12px", fontWeight: 300, lineHeight: 1.5, color: "#111827" }}>owners and operators actively reallocating ad budget who value confidence before moving real dollars.</span>
                </div>
                <h4 style={{ fontFamily: "Inter, sans-serif", fontSize: "14px", fontWeight: 600, color: "#374151", margin: 0, marginTop: "32px" }}>Everything in Tier 1, plus:</h4>
                <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "12px" }}>
                    {features.map((feature, index) => <FeatureItem key={index} text={feature} />)}
                </div>
                <div style={{ marginTop: "24px" }}>
                    <h4 style={{ fontFamily: "Inter, sans-serif", fontSize: "14px", fontWeight: 600, color: "#111827", margin: 0, marginBottom: "10px" }}>What this helps you do:</h4>
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                        {benefits.map((benefit, index) => <BenefitItem key={index} text={benefit} />)}
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

                <button
                    onClick={handleAction}
                    style={{ display: "flex", justifyContent: "center", alignItems: "center", width: "100%", height: "52px", backgroundColor: "#FFFFFF", color: "#1a1a1a", fontFamily: "Inter, sans-serif", fontSize: "16px", fontWeight: 600, border: "2px solid #1a1a1a", borderRadius: "8px", cursor: "pointer", transition: "all 0.2s" }}
                    onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "#f9fafb"; e.currentTarget.style.transform = "translateY(-1px)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "#FFFFFF"; e.currentTarget.style.transform = "none"; }}
                >
                    Contact sales
                </button>
            </div>
        </div>
    );
}

// =============================================================================
// CARD 3: "RUN AT SCALE" - TIER 3
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
    const benefits = ["Reduce operational overhead", "Standardize reporting across teams or clients", "Rely on Skeldir as core infrastructure"];

    const handleAction = () => {
        router.push('/book-demo');
    };

    return (
        <div style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E7EB", borderRadius: "16px", boxShadow: "0px 4px 24px rgba(0, 0, 0, 0.08)", padding: "32px 28px", display: "flex", flexDirection: "column", transform: "scale(0.97)", opacity: 0.95, transition: "transform 0.3s ease, opacity 0.3s ease" }}>
            <h3 style={{ fontFamily: "Inter, sans-serif", fontSize: "24px", fontWeight: 700, lineHeight: 1.2, color: "#111827", margin: 0, marginTop: "16px" }}>Run at Scale</h3>
            <div style={{ display: "inline-flex", alignItems: "baseline", marginTop: "8px" }}>
                <span style={{ fontFamily: "Inter, sans-serif", fontSize: "48px", fontWeight: 700, color: "#111827" }}>$999</span>
                <span style={{ fontFamily: "Inter, sans-serif", fontSize: "16px", fontWeight: 400, color: "#6B7280", marginLeft: "2px" }}>/month</span>
            </div>
            <div style={{ marginTop: "20px" }}>
                <span style={{ fontFamily: "Inter, sans-serif", fontSize: "12px", fontWeight: 300, color: "#111827" }}>Specifically made for </span>
                <span style={{ fontFamily: "Inter, sans-serif", fontSize: "12px", fontWeight: 300, lineHeight: 1.5, color: "#111827" }}>agencies or businesses managing multiple brands or accounts.</span>
            </div>
            <h4 style={{ fontFamily: "Inter, sans-serif", fontSize: "14px", fontWeight: 600, color: "#374151", margin: 0, marginTop: "32px" }}>Everything in Tier 2, plus:</h4>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "12px" }}>
                {features.map((feature, index) => <FeatureItem key={index} text={feature} />)}
            </div>
            <div style={{ marginTop: "24px" }}>
                <h4 style={{ fontFamily: "Inter, sans-serif", fontSize: "14px", fontWeight: 600, color: "#111827", margin: 0, marginBottom: "10px" }}>What this helps you do:</h4>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {benefits.map((benefit, index) => <BenefitItem key={index} text={benefit} />)}
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

            <button
                onClick={handleAction}
                style={{ display: "flex", justifyContent: "center", alignItems: "center", width: "100%", height: "52px", backgroundColor: "#FFFFFF", color: "#1a1a1a", fontFamily: "Inter, sans-serif", fontSize: "16px", fontWeight: 600, border: "2px solid #1a1a1a", borderRadius: "8px", cursor: "pointer", transition: "all 0.2s" }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "#f9fafb"; e.currentTarget.style.transform = "translateY(-1px)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "#FFFFFF"; e.currentTarget.style.transform = "none"; }}
            >
                Contact sales
            </button>
        </div>
    );
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
