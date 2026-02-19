"use client";

import React from "react";

// ============================================================================
// RECONCILIATION NETWORK SECTION
// Section 4 of Product Page
// Implements: Inverted Layout (Text Left, Visual Right), Network Diagram
// ============================================================================

// --- Network Diagram Component ---

function NetworkDiagram() {
    return (
        <div style={{ position: "relative", width: "100%", maxWidth: "600px", margin: "0 auto", aspectRatio: "1/1" }}>
            {/* Background Glow - Right Side */}
            <div
                style={{
                    position: "absolute",
                    top: "50%",
                    left: "50%",
                    width: "120%",
                    height: "120%",
                    background: "radial-gradient(circle, rgba(37, 99, 235, 0.15) 0%, rgba(139, 92, 246, 0.1) 30%, rgba(236, 72, 153, 0.05) 60%, transparent 80%)",
                    transform: "translate(-50%, -50%)",
                    filter: "blur(60px)",
                    zIndex: 0,
                    pointerEvents: "none",
                }}
            />

            {/* Dot Grid Pattern */}
            <div
                style={{
                    position: "absolute",
                    top: "50%",
                    left: "50%",
                    width: "100%",
                    height: "100%",
                    transform: "translate(-50%, -50%)",
                    pointerEvents: "none",
                    zIndex: 1,
                    backgroundImage: `radial-gradient(circle, rgba(37, 99, 235, 0.3) 1.5px, transparent 1.5px)`,
                    backgroundSize: "24px 24px",
                    maskImage: "radial-gradient(ellipse at center, black 0%, black 40%, transparent 70%)",
                    WebkitMaskImage: "radial-gradient(ellipse at center, black 0%, black 40%, transparent 70%)",
                }}
            />

            {/* SVG Diagram */}
            <svg
                viewBox="0 0 500 500"
                style={{
                    width: "100%",
                    height: "100%",
                    position: "relative",
                    zIndex: 2,
                    overflow: "visible",
                }}
            >
                {/* Defs for gradients/filters */}
                <defs>
                    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                        <feDropShadow dx="0" dy="4" stdDeviation="8" floodColor="rgba(0,0,0,0.08)" />
                    </filter>
                    <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="#94A3B8" />
                        <stop offset="50%" stopColor="#64748B" />
                        <stop offset="100%" stopColor="#94A3B8" />
                    </linearGradient>
                </defs>

                {/* Connection Lines */}
                {/* Coordinates based on 60-degree distribution around center (250, 250) with radius ~160 */}
                {/* Top (Google Ads) */}
                <line x1="250" y1="250" x2="250" y2="90" stroke="#94A3B8" strokeWidth="2.5" strokeDasharray="5 3" opacity="0.7" />
                {/* Top Right (TikTok) */}
                <line x1="250" y1="250" x2="389" y2="170" stroke="#94A3B8" strokeWidth="2.5" strokeDasharray="5 3" opacity="0.7" />
                {/* Bottom Right (Shopify) */}
                <line x1="250" y1="250" x2="389" y2="330" stroke="#94A3B8" strokeWidth="2.5" strokeDasharray="5 3" opacity="0.7" />
                {/* Bottom (PayPal) */}
                <line x1="250" y1="250" x2="250" y2="410" stroke="#94A3B8" strokeWidth="2.5" strokeDasharray="5 3" opacity="0.7" />
                {/* Bottom Left (Stripe) */}
                <line x1="250" y1="250" x2="111" y2="330" stroke="#94A3B8" strokeWidth="2.5" strokeDasharray="5 3" opacity="0.7" />
                {/* Top Left (Meta) */}
                <line x1="250" y1="250" x2="111" y2="170" stroke="#94A3B8" strokeWidth="2.5" strokeDasharray="5 3" opacity="0.7" />

                {/* Central Hub - Magnifying Glass */}
                <g transform="translate(250, 250)">
                    {/* Hub Circle Background */}
                    <circle cx="0" cy="0" r="48" fill="#FFFFFF" filter="url(#shadow)" />
                    <circle cx="0" cy="0" r="48" fill="url(#hubGradient)" opacity="0.05" />

                    {/* Magnifying Glass Icon */}
                    <g transform="translate(-24, -24) scale(2)">
                        <path
                            d="M11 19C15.4183 19 19 15.4183 19 11C19 6.58172 15.4183 3 11 3C6.58172 3 3 6.58172 3 11C3 15.4183 6.58172 19 11 19Z"
                            stroke="#3B82F6"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            fill="none"
                        />
                        <path
                            d="M21 21L16.65 16.65"
                            stroke="#3B82F6"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        />
                    </g>
                </g>

                {/* Satellite Nodes */}
                {/* Google Ads (Top) */}
                <g transform="translate(250, 90)">
                    <circle r="32" fill="#FFFFFF" filter="url(#shadow)" />
                    <image href="/images/google-ads-icon.webp" x="-16" y="-16" width="32" height="32" />
                </g>

                {/* TikTok (Top Right) */}
                <g transform="translate(389, 170)">
                    <circle r="32" fill="#FFFFFF" filter="url(#shadow)" />
                    <image href="/images/tiktok-icon.png" x="-16" y="-16" width="32" height="32" />
                </g>

                {/* Shopify (Bottom Right) */}
                <g transform="translate(389, 330)">
                    <circle r="32" fill="#FFFFFF" filter="url(#shadow)" />
                    <image href="/images/shopify-logo.webp" x="-24" y="-24" width="48" height="48" />
                </g>

                {/* PayPal (Bottom) */}
                <g transform="translate(250, 410)">
                    <circle r="32" fill="#FFFFFF" filter="url(#shadow)" />
                    {/* PayPal Logo - Clean SVG */}
                    <g transform="translate(-16, -16)">
                        <svg viewBox="5.8 1.3 52.7 61.4" width="32" height="32" preserveAspectRatio="xMidYMid meet">
                            <path d="m50.3 5.9c-2.8-3.2-8-4.6-14.5-4.6h-19.1c-1.3 0-2.5 1-2.7 2.3l-8 50.4c-.2 1 .6 1.9 1.6 1.9h11.8l3-18.8-.1.6c.2-1.3 1.3-2.3 2.7-2.3h5.6c11 0 19.6-4.5 22.1-17.4.1-.4.1-.8.2-1.1-.3-.2-.3-.2 0 0 .7-4.8 0-8-2.6-11" fill="#263b80" />
                            <path d="m52.9 16.9c-.1.4-.1.7-.2 1.1-2.5 12.9-11.1 17.4-22.1 17.4h-5.6c-1.3 0-2.5 1-2.7 2.3l-3.7 23.3c-.1.9.5 1.7 1.4 1.7h9.9c1.2 0 2.2-.9 2.4-2l.1-.5 1.9-11.8.1-.7c.2-1.2 1.2-2 2.4-2h1.5c9.6 0 17.1-3.9 19.3-15.2.9-4.7.4-8.7-2-11.4-.8-.9-1.7-1.6-2.7-2.2" fill="#139ad6" />
                            <path d="m50.2 15.9-1.2-.3c-.4-.1-.8-.2-1.3-.2-1.5-.3-3.2-.4-4.9-.4h-14.9c-.4 0-.7.1-1 .2-.7.3-1.2 1-1.3 1.8l-3.2 20.1-.1.6c.2-1.3 1.3-2.3 2.7-2.3h5.6c11 0 19.6-4.5 22.1-17.4.1-.4.1-.8.2-1.1-.6-.3-1.3-.6-2.1-.9-.2 0-.4-.1-.6-.1" fill="#232c65" />
                            <path d="m35.7 1.3h-19c-1.3 0-2.5 1-2.7 2.3l-4.6 28.8 30.8-30.8c-1.4-.2-2.9-.3-4.5-.3z" fill="#2a4dad" />
                            <path d="m56.5 20.5c-.3-.5-.5-1-.9-1.5-.7-.8-1.7-1.5-2.7-2.1-.1.4-.1.7-.2 1.1-2.5 12.9-11.1 17.4-22.1 17.4h-5.6c-1.3 0-2.5 1-2.7 2.3l-3.2 20.2z" fill="#0d7dbc" />
                            <path d="m7.6 55.9h11.8l2.9-18.2c0-.3.1-.5.2-.7l-16.4 16.4-.1.6c-.1 1 .6 1.9 1.6 1.9z" fill="#232c65" />
                            <path d="m32.1 1.3h-15.4c-.4 0-.7.1-1 .2l-1.5 1.5c-.1.2-.2.4-.2.6l-3 18.8z" fill="#436bc4" />
                        </svg>
                    </g>
                </g>

                {/* Stripe (Bottom Left) */}
                <g transform="translate(111, 330)">
                    <circle r="32" fill="#FFFFFF" filter="url(#shadow)" />
                    <image href="/images/stripe-logo.png" x="-16" y="-16" width="32" height="32" style={{ objectFit: "contain" }} />
                </g>

                {/* Meta (Top Left) */}
                <g transform="translate(111, 170)">
                    <circle r="32" fill="#FFFFFF" filter="url(#shadow)" />
                    <image href="/images/meta-logo-new.png" x="-16" y="-16" width="32" height="32" />
                </g>

            </svg>
        </div>
    );
}

// --- Main Component ---

export function ReconciliationNetwork() {
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
                className="reconciliation-network-grid"
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
                {/* Left Column: Content (INVERTED from Section 3) */}
                <div className="reconciliation-network__content">
                    <h2
                        style={{
                            fontSize: "3.5rem",
                            fontWeight: 500,
                            color: "#0F172A",
                            lineHeight: "1.1",
                            marginBottom: "40px",
                            fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                            letterSpacing: "-0.02em",
                        }}
                    >
                        Eliminate repetitive reconciliation — connect once, trust always.
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
                        Stop bouncing between ad platforms, Stripe dashboards, and spreadsheet VLOOKUPs. Skeldir connects to Google Ads, Meta, Shopify, and payment providers—automatically reconciling discrepancies so you see verified performance in one place.
                    </p>
                </div>

                {/* Right Column: Visual (Network Diagram) */}
                <div className="reconciliation-network__visual">
                    <NetworkDiagram />
                </div>
            </div>

            {/* Responsive Styles */}
            <style>
                {`
          @media (max-width: 1024px) {
            .reconciliation-network__content {
              order: 1; /* Keep content first on tablet/mobile */
              text-align: center;
            }
            .reconciliation-network__visual {
              order: 2;
              width: 100% !important;
              overflow: visible !important;
            }
            section {
              padding: 80px 32px !important;
              overflow-x: hidden !important;
            }
            .reconciliation-network-grid {
              display: flex !important;
              flex-direction: column !important;
              gap: 60px !important;
              width: 100% !important;
            }
            h2 {
              fontSize: 2.5rem !important;
            }
            p {
              margin: 0 auto;
            }
            /* Ensure NetworkDiagram scales properly */
            .reconciliation-network__visual > div {
              width: 100% !important;
              max-width: 100% !important;
            }
          }
          @media (max-width: 767px) {
            section {
              padding: 60px 20px !important;
              overflow-x: hidden !important;
            }
            
            .reconciliation-network-grid {
              display: flex !important;
              flex-direction: column !important;
              gap: 48px !important;
              width: 100% !important;
              max-width: 100% !important;
              padding: 0 !important;
              margin: 0 !important;
            }
            
            .reconciliation-network__content {
              width: 100% !important;
              max-width: 100% !important;
              padding: 0 !important;
              margin: 0 !important;
              text-align: center !important;
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
            
            .reconciliation-network__visual {
              width: 100% !important;
              max-width: 100% !important;
              padding: 0 !important;
              margin: 0 auto !important;
              position: relative !important;
              left: 0 !important;
              right: 0 !important;
            }
            
            /* Ensure NetworkDiagram is fully visible on mobile */
            .reconciliation-network__visual > div[style*="position: relative"] {
              width: 100% !important;
              max-width: 100% !important;
              margin: 0 auto !important;
              left: 0 !important;
              right: 0 !important;
            }
            
            /* Ensure SVG is properly contained */
            .reconciliation-network__visual svg {
              width: 100% !important;
              max-width: 100% !important;
              height: auto !important;
              position: relative !important;
              left: 0 !important;
              right: 0 !important;
            }
            
            /* Scale down SVG on very small screens */
            @media (max-width: 375px) {
              .reconciliation-network__visual svg {
                transform: scale(0.9) !important;
                transform-origin: center !important;
              }
            }
          }
        `}
            </style>
        </section>
    );
}
