"use client";

import React from "react";
import { PlatformLogoStrip } from "./PlatformLogoStrip";

// ============================================================================
// MARKETING DEFENSE SECTION
// Replaces "How Skeldir Works" on Product Page
// Implements: 2-Column Layout, "Investigate" UI Card, Persuasive Copy
// ============================================================================

// --- UI Card Components ---

function InvestigateCard() {
    return (
        <div style={{ position: "relative", maxWidth: "600px", width: "100%", margin: "0 auto" }}>
            {/* Glow Effect Behind Card */}
            <div
                style={{
                    position: "absolute",
                    top: "50%",
                    left: "50%",
                    transform: "translate(-50%, -50%)",
                    width: "120%",
                    height: "120%",
                    background: "radial-gradient(circle, rgba(37, 99, 235, 0.25) 0%, rgba(139, 92, 246, 0.2) 30%, rgba(236, 72, 153, 0.15) 60%, transparent 80%)",
                    borderRadius: "20px",
                    filter: "blur(60px)",
                    zIndex: 0,
                    pointerEvents: "none",
                }}
            />
            <div
                style={{
                    backgroundColor: "#FFFFFF",
                    borderRadius: "16px",
                    boxShadow: "0 20px 40px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.04), 0 0 80px rgba(37, 99, 235, 0.15)",
                    overflow: "hidden",
                    fontFamily: "'Inter', sans-serif",
                    width: "100%",
                    position: "relative",
                    zIndex: 2,
                }}
            >
            {/* Card Header / Search Bar */}
            <div
                style={{
                    padding: "32px 24px 20px 24px",
                    borderBottom: "1px solid #F1F5F9",
                }}
            >
                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        backgroundColor: "#F8FAFC",
                        borderRadius: "8px",
                        padding: "12px 16px",
                        border: "1px solid #E2E8F0",
                    }}
                >
                    {/* Search Icon */}
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M7.33333 12.6667C10.2789 12.6667 12.6667 10.2789 12.6667 7.33333C12.6667 4.38781 10.2789 2 7.33333 2C4.38781 2 2 4.38781 2 7.33333C2 10.2789 4.38781 12.6667 7.33333 12.6667Z" stroke="#64748B" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        <path d="M14 14L11.1 11.1" stroke="#64748B" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <span
                        className="investigate-card-search-text"
                        style={{
                            fontSize: "14px",
                            color: "#0F172A",
                            fontWeight: 500,
                        }}
                    >
                        Investigate: &apos;Why is Meta ads revenue so different from claimed?&apos;
                    </span>
                </div>
            </div>

            {/* Card Body */}
            <div style={{ padding: "32px 24px 24px 24px" }}>
                {/* Show Thinking Header */}
                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        marginBottom: "20px",
                    }}
                >
                    <svg width="12" height="8" viewBox="0 0 12 8" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M1 1L6 6L11 1" stroke="#64748B" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <span className="investigate-card-show-thinking" style={{ fontSize: "13px", color: "#64748B", fontWeight: 500 }}>
                        Show thinking • 4 sources
                    </span>
                </div>

                {/* Checklist Items */}
                <div className="investigate-card-checklist" style={{ display: "flex", flexDirection: "column", gap: "16px", marginBottom: "24px" }}>
                    {/* Item 1 */}
                    <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                        <div style={{ marginTop: "2px", flexShrink: 0 }}>
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <circle cx="8" cy="8" r="8" fill="#F1F5F9" />
                                <path d="M5 8L7 10L11 6" stroke="#64748B" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                        </div>
                        <span className="investigate-card-item-text" style={{ fontSize: "13px", lineHeight: "1.5", color: "#334155" }}>
                            Querying attribution database: Fetched Meta attribution: ROAS 1.8 [1.2-2.4], 12% allocation
                        </span>
                    </div>

                    {/* Item 2 */}
                    <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                        <div style={{ marginTop: "2px", flexShrink: 0 }}>
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <circle cx="8" cy="8" r="8" fill="#F1F5F9" />
                                <path d="M5 8L7 10L11 6" stroke="#64748B" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                        </div>
                        <span className="investigate-card-item-text" style={{ fontSize: "13px", lineHeight: "1.5", color: "#334155" }}>
                            Checking commerce webhooks: Verified revenue: $1.35K vs Platform claimed $6.6K (-80% discrepancy)
                        </span>
                    </div>

                    {/* Item 3 */}
                    <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                        <div style={{ marginTop: "2px", flexShrink: 0 }}>
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <circle cx="8" cy="8" r="8" fill="#F1F5F9" />
                                <path d="M5 8L7 10L11 6" stroke="#64748B" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                        </div>
                        <span className="investigate-card-item-text" style={{ fontSize: "13px", lineHeight: "1.5", color: "#334155" }}>
                            Cross-referencing UTM parameters: Meta uses 7-day attribution window (your config: 30-day)
                        </span>
                    </div>

                    {/* Item 4 */}
                    <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                        <div style={{ marginTop: "2px", flexShrink: 0 }}>
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <circle cx="8" cy="8" r="8" fill="#F1F5F9" />
                                <path d="M5 8L7 10L11 6" stroke="#64748B" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                        </div>
                        <span className="investigate-card-item-text" style={{ fontSize: "13px", lineHeight: "1.5", color: "#334155" }}>
                            Platform documentation lookup: Meta includes unconfigured view-through conversions
                        </span>
                    </div>
                </div>

                {/* Divider */}
                <div style={{ height: "1px", backgroundColor: "#E2E8F0", marginBottom: "24px" }} />

                {/* Analysis Content */}
                <div style={{ marginBottom: "24px" }}>
                    <p style={{ fontSize: "13px", color: "#64748B", marginBottom: "12px" }}>
                        Based on verified revenue data, attribution models, and platform behavior:
                    </p>
                    <p className="investigate-card-analysis-title" style={{ fontSize: "14px", fontWeight: 600, color: "#0F172A", marginBottom: "8px" }}>
                        Meta Revenue Discrepancy Analysis:
                    </p>
                    <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: "13px", color: "#334155", display: "flex", flexDirection: "column", gap: "6px" }}>
                        <li style={{ display: "flex", gap: "6px" }}>
                            <span style={{ color: "#64748B" }}>•</span>
                            Platform claims $6.8K, Stripe verifies $1.35K (80% over-reporting)
                        </li>
                        <li style={{ display: "flex", gap: "6px" }}>
                            <span style={{ color: "#64748B" }}>•</span>
                            Cause: Meta 7-day window + view-through conversions (not pixel-configured)
                        </li>
                        <li style={{ display: "flex", gap: "6px" }}>
                            <span style={{ color: "#64748B" }}>•</span>
                            Confidence: High (narrow ROAS range, 400+ ESS samples)
                        </li>
                        <li style={{ display: "flex", gap: "6px" }}>
                            <span style={{ color: "#64748B" }}>•</span>
                            Impact: Inflates Meta allocation by 8 points
                        </li>
                    </ul>
                </div>

                {/* Recommendation */}
                <div className="recommendation-container" style={{ marginBottom: "24px" }}>
                    <p className="recommendation-text" style={{ fontSize: "13px", color: "#0F172A", fontWeight: 700 }}>
                        Recommendation: Reduce Meta 40% → Google
                    </p>
                </div>

                {/* Action Buttons */}
                <div className="investigate-card-actions" style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
                    <button
                        className="investigate-card-button"
                        style={{
                            backgroundColor: "#DCFCE7",
                            color: "#166534",
                            border: "1px solid #86EFAC",
                            borderRadius: "6px",
                            padding: "8px 16px",
                            fontSize: "13px",
                            fontWeight: 500,
                            cursor: "pointer",
                            whiteSpace: "nowrap",
                            flexShrink: 0,
                        }}
                    >
                        Accept Findings
                    </button>
                    <button
                        className="investigate-card-button"
                        style={{
                            backgroundColor: "#FFFFFF",
                            color: "#334155",
                            border: "1px solid #E2E8F0",
                            borderRadius: "6px",
                            padding: "8px 16px",
                            fontSize: "13px",
                            fontWeight: 500,
                            cursor: "pointer",
                            whiteSpace: "nowrap",
                            flexShrink: 0,
                        }}
                    >
                        Refine: &apos;Include view-through?&apos;
                    </button>
                    <button
                        className="investigate-card-button"
                        style={{
                            backgroundColor: "#FEF2F2",
                            color: "#991B1B",
                            border: "1px solid #FECACA",
                            borderRadius: "6px",
                            padding: "8px 16px",
                            fontSize: "13px",
                            fontWeight: 500,
                            cursor: "pointer",
                            whiteSpace: "nowrap",
                            flexShrink: 0,
                        }}
                    >
                        Discard
                    </button>
                </div>

                {/* Platform Logo Strip */}
                <PlatformLogoStrip />
            </div>
        </div>
        </div>
    );
}

// --- Main Component ---

export function MarketingDefense() {
    return (
        <section
            style={{
                width: "100%",
                backgroundColor: "#F8FAFC", // Match Product Page background
                padding: "120px 60px",
                position: "relative",
                overflow: "hidden",
            }}
        >
            <div
                className="marketing-defense-grid"
                style={{
                    maxWidth: "1400px",
                    margin: "0 auto",
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr", // 2 Columns
                    gap: "120px",
                    alignItems: "center",
                    position: "relative",
                    zIndex: 1,
                }}
            >
                {/* Left Column: UI Card */}
                <div className="marketing-defense__visual" style={{ position: "relative" }}>
                    {/* Background Gradient Blob - Positioned directly behind card */}
                    <div
                        className="marketing-defense__glow"
                        style={{
                            position: "absolute",
                            top: "50%",
                            left: "50%",
                            width: "700px",
                            height: "800px",
                            background: "radial-gradient(circle at center, rgba(37, 99, 235, 0.35) 0%, rgba(139, 92, 246, 0.28) 20%, rgba(236, 72, 153, 0.22) 40%, rgba(255, 214, 232, 0.15) 60%, transparent 80%)",
                            transform: "translate(-50%, -50%)",
                            pointerEvents: "none",
                            zIndex: 0,
                            filter: "blur(70px)",
                        }}
                    />
                    
                    {/* Dot Grid Pattern - Positioned exactly where glow is, fading out from center */}
                    <div
                        className="marketing-defense__dot-grid"
                        style={{
                            position: "absolute",
                            top: "50%",
                            left: "50%",
                            width: "700px",
                            height: "800px",
                            transform: "translate(-50%, -50%)",
                            pointerEvents: "none",
                            zIndex: 1,
                            backgroundImage: `radial-gradient(circle, rgba(37, 99, 235, 0.5) 1.7px, transparent 1.7px)`,
                            backgroundSize: "20px 20px",
                            backgroundPosition: "0 0",
                            maskImage: "radial-gradient(ellipse at center, black 0%, black 35%, rgba(0, 0, 0, 0.7) 50%, rgba(0, 0, 0, 0.3) 65%, transparent 80%)",
                            WebkitMaskImage: "radial-gradient(ellipse at center, black 0%, black 35%, rgba(0, 0, 0, 0.7) 50%, rgba(0, 0, 0, 0.3) 65%, transparent 80%)",
                        }}
                    />
                    <InvestigateCard />
                </div>

                {/* Right Column: Content */}
                <div className="marketing-defense__content">
                    <h2
                        style={{
                            fontSize: "3.5rem", // Large, impactful headline
                            fontWeight: 500,
                            color: "#0F172A",
                            lineHeight: "1.1",
                            marginBottom: "40px",
                            fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                            letterSpacing: "-0.02em",
                        }}
                    >
                        Defend your marketing spend with confidence.
                    </h2>
                    <p
                        style={{
                            fontSize: "1.25rem",
                            color: "#475569",
                            lineHeight: "1.6",
                            fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                            maxWidth: "540px",
                            marginTop: "0",
                        }}
                    >
                        Whether defending ad spend or reallocating budget, Skeldir combines
                        verified revenue, statistical confidence, and discrepancy detection—so
                        teams trust your recommendations, not question your data.
                    </p>
                </div>
            </div>

            {/* Responsive Styles */}
            <style>
                {`
          @media (max-width: 1024px) {
            .marketing-defense__visual {
              order: 2; /* Visual below text on tablet/mobile if desired, or keep as is */
            }
            .marketing-defense__glow {
              width: 100% !important;
              max-width: 500px !important;
              height: 600px !important;
            }
            .marketing-defense__dot-grid {
              width: 100% !important;
              max-width: 500px !important;
              height: 600px !important;
            }
            section {
              padding: 80px 32px !important;
              overflow-x: hidden !important;
            }
            .marketing-defense-grid {
              display: flex !important;
              flex-direction: column !important;
              gap: 60px !important;
              width: 100% !important;
              text-align: center;
            }
            h2 {
              fontSize: 2.5rem !important;
            }
            p {
              margin: 0 auto;
            }
          }
          @media (max-width: 767px) {
            section {
              padding: 60px 20px !important;
              overflow-x: hidden !important;
            }
            
            .marketing-defense-grid {
              display: flex !important;
              flex-direction: column !important;
              gap: 48px !important;
              width: 100% !important;
              max-width: 100% !important;
              padding: 0 !important;
              margin: 0 !important;
            }
            
            .marketing-defense__content {
                order: 1 !important;
                width: 100% !important;
                max-width: 100% !important;
                padding: 0 !important;
                margin: 0 !important;
                text-align: center !important;
            }
            
            .marketing-defense__visual {
                order: 2 !important;
                width: 100% !important;
                max-width: 100% !important;
                overflow: visible !important;
                position: relative !important;
                left: 0 !important;
                right: 0 !important;
                margin: 0 auto !important;
                padding: 0 !important;
            }
            
            .marketing-defense__glow {
              width: 100% !important;
              max-width: 100% !important;
              height: 500px !important;
            }
            
            .marketing-defense__dot-grid {
              width: 100% !important;
              max-width: 100% !important;
              height: 500px !important;
            }
            
            h2 {
              fontSize: 28px !important;
              line-height: 1.25 !important;
              margin-bottom: 32px !important;
            }
            
            p {
              font-size: 18px !important;
              line-height: 1.6 !important;
            }
            
            /* Ensure InvestigateCard is fully visible */
            .marketing-defense__visual > div[style*="position: relative"] {
              width: 100% !important;
              max-width: 100% !important;
              padding: 0 !important;
              margin: 0 auto !important;
              left: 0 !important;
              right: 0 !important;
            }

            /* InvestigateCard: smaller font on mobile */
            .investigate-card-analysis-title {
              font-size: 12px !important;
            }
            .investigate-card-search-text {
              font-size: 12px !important;
            }
            .investigate-card-show-thinking {
              font-size: 11px !important;
            }
            .investigate-card-item-text {
              font-size: 11px !important;
              line-height: 1.45 !important;
            }

            /* Fix button alignment on mobile */
            .investigate-card-actions {
              flex-direction: column !important;
              align-items: stretch !important;
              gap: 10px !important;
            }

            .investigate-card-button {
              width: 100% !important;
              min-height: 44px !important;
              padding: 10px 16px !important;
              font-size: 14px !important;
              display: flex !important;
              align-items: center !important;
              justify-content: center !important;
            }

            /* Ensure buttons stay on same horizontal plane */
            .investigate-card-actions button {
              height: 44px !important;
              line-height: 1.4 !important;
            }

            /* Make recommendation text significantly smaller and keep on same horizontal plane */
            .recommendation-text {
              font-size: 10px !important;
              white-space: nowrap !important;
              line-height: 1.3 !important;
              margin: 0 !important;
              display: block !important;
            }

            .recommendation-container {
              margin-bottom: 20px !important;
            }
          }
        `}
            </style>
        </section>
    );
}
