"use client";

import React from "react";

export function IntegrationsShowcase() {
    // Logo data - reusing assets from PlatformLogoStrip + placeholders for variety if needed
    // We need enough logos to fill a row. 
    // Primary: Google Ads, Meta, TikTok, Shopify, Stripe, PayPal
    // Secondary: We'll repeat the primary ones or add generic placeholders if we don't have assets.

    const baseLogos = [
        { id: "google", name: "Google Ads", src: "/images/google-ads-icon.webp", height: "40px" },
        { id: "meta", name: "Meta", src: "/images/meta-logo-new.png", height: "32px" },
        { id: "tiktok", name: "TikTok", src: "/images/tiktok-icon.png", height: "36px" },
        { id: "shopify", name: "Shopify", src: "/images/shopify-logo.webp", height: "48px" },
        { id: "stripe", name: "Stripe", src: "/images/stripe-logo.png", height: "36px" },
        {
            id: "paypal",
            name: "PayPal",
            component: (
                <svg viewBox="5.8 1.3 52.7 61.4" height="36" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: "auto" }}>
                    <path d="m50.3 5.9c-2.8-3.2-8-4.6-14.5-4.6h-19.1c-1.3 0-2.5 1-2.7 2.3l-8 50.4c-.2 1 .6 1.9 1.6 1.9h11.8l3-18.8-.1.6c.2-1.3 1.3-2.3 2.7-2.3h5.6c11 0 19.6-4.5 22.1-17.4.1-.4.1-.8.2-1.1-.3-.2-.3-.2 0 0 .7-4.8 0-8-2.6-11" fill="#263b80" />
                    <path d="m52.9 16.9c-.1.4-.1.7-.2 1.1-2.5 12.9-11.1 17.4-22.1 17.4h-5.6c-1.3 0-2.5 1-2.7 2.3l-3.7 23.3c-.1.9.5 1.7 1.4 1.7h9.9c1.2 0 2.2-.9 2.4-2l.1-.5 1.9-11.8.1-.7c.2-1.2 1.2-2 2.4-2h1.5c9.6 0 17.1-3.9 19.3-15.2.9-4.7.4-8.7-2-11.4-.8-.9-1.7-1.6-2.7-2.2" fill="#139ad6" />
                    <path d="m50.2 15.9-1.2-.3c-.4-.1-.8-.2-1.3-.2-1.5-.3-3.2-.4-4.9-.4h-14.9c-.4 0-.7.1-1 .2-.7.3-1.2 1-1.3 1.8l-3.2 20.1-.1.6c.2-1.3 1.3-2.3 2.7-2.3h5.6c11 0 19.6-4.5 22.1-17.4.1-.4.1-.8.2-1.1-.6-.3-1.3-.6-2.1-.9-.2 0-.4-.1-.6-.1" fill="#232c65" />
                    <path d="m35.7 1.3h-19c-1.3 0-2.5 1-2.7 2.3l-4.6 28.8 30.8-30.8c-1.4-.2-2.9-.3-4.5-.3z" fill="#2a4dad" />
                    <path d="m56.5 20.5c-.3-.5-.5-1-.9-1.5-.7-.8-1.7-1.5-2.7-2.1-.1.4-.1.7-.2 1.1-2.5 12.9-11.1 17.4-22.1 17.4h-5.6c-1.3 0-2.5 1-2.7 2.3l-3.2 20.2z" fill="#0d7dbc" />
                    <path d="m7.6 55.9h11.8l2.9-18.2c0-.3.1-.5.2-.7l-16.4 16.4-.1.6c-.1 1 .6 1.9 1.6 1.9z" fill="#232c65" />
                    <path d="m32.1 1.3h-15.4c-.4 0-.7.1-1 .2l-1.5 1.5c-.1.2-.2.4-.2.6l-3 18.8z" fill="#436bc4" />
                </svg>
            )
        },
    ];

    // Manually curated sequences to ensure variety and no repetition within ~5 positions
    // We map the base logos by ID to create these sequences
    const getLogo = (id: string) => baseLogos.find(l => l.id === id) || baseLogos[0];

    const row1Ids = ['google', 'stripe', 'meta', 'shopify', 'tiktok', 'paypal', 'google', 'stripe', 'meta', 'shopify', 'tiktok', 'paypal'];
    const row2Ids = ['meta', 'paypal', 'google', 'shopify', 'stripe', 'tiktok', 'meta', 'paypal', 'google', 'shopify', 'stripe', 'tiktok'];
    const row3Ids = ['tiktok', 'shopify', 'stripe', 'paypal', 'google', 'meta', 'tiktok', 'shopify', 'stripe', 'paypal', 'google', 'meta'];
    const row4Ids = ['stripe', 'google', 'paypal', 'meta', 'tiktok', 'shopify', 'stripe', 'google', 'paypal', 'meta', 'tiktok', 'shopify'];
    const row5Ids = ['shopify', 'meta', 'google', 'tiktok', 'paypal', 'stripe', 'shopify', 'meta', 'google', 'tiktok', 'paypal', 'stripe'];
    const row6Ids = ['paypal', 'tiktok', 'shopify', 'google', 'stripe', 'meta', 'paypal', 'tiktok', 'shopify', 'google', 'stripe', 'meta'];

    const rows = [
        row1Ids.map(getLogo),
        row2Ids.map(getLogo),
        row3Ids.map(getLogo),
    ];

    return (
        <section
            className="integrations-showcase"
            aria-label="Platform integrations"
            style={{
                position: "relative",
                width: "100%",
                padding: "85px 0 40px 0", // More top padding to prevent logo clipping
                overflow: "hidden",
                // Enhanced blue-purple gradient with more blue tones
                background: "linear-gradient(135deg, rgba(59, 130, 246, 0.18) 0%, rgba(37, 99, 235, 0.22) 30%, rgba(79, 70, 229, 0.20) 60%, rgba(99, 102, 241, 0.18) 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                minHeight: "245px",
                height: "auto",
                maxHeight: "285px",
            }}
        >
            {/* Radial Gradient Overlay for Vignette - Enhanced Blue Glow */}
            <div
                style={{
                    position: "absolute",
                    inset: 0,
                    background: "radial-gradient(ellipse at center, rgba(59, 130, 246, 0.15) 0%, rgba(37, 99, 235, 0.25) 30%, rgba(79, 70, 229, 0.20) 60%, rgba(99, 102, 241, 0.15) 100%)",
                    pointerEvents: "none",
                    zIndex: 1,
                }}
            />
            
            {/* Additional Blue Glow Layer */}
            <div
                style={{
                    position: "absolute",
                    inset: 0,
                    background: "radial-gradient(ellipse at center, rgba(37, 99, 235, 0.12) 0%, rgba(59, 130, 246, 0.18) 40%, transparent 80%)",
                    pointerEvents: "none",
                    zIndex: 1,
                }}
            />

            {/* Animated Logo Background */}
            <div
                className="logo-background"
                style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "center",
                    gap: "20px", // Reduced gap for strip
                    zIndex: 2,
                    pointerEvents: "none",
                    opacity: 0.7, // Slightly higher opacity for visibility against richer background
                }}
            >
                {rows.map((rowLogos, rowIndex) => {
                    // Triple the logos for seamless loop
                    const loopedLogos = [...rowLogos, ...rowLogos, ...rowLogos];
                    // Alternate direction
                    const direction = rowIndex % 2 === 0 ? "scroll-left" : "scroll-right";
                    // Stagger duration slightly for organic feel
                    const duration = 35 + (rowIndex * 2) + "s";

                    return (
                        <div
                            key={`row-${rowIndex}`}
                            className={`logo-row ${direction}`}
                            style={{
                                display: "flex",
                                gap: "32px",
                                width: "max-content",
                                animationDuration: duration,
                                marginLeft: rowIndex % 2 === 0 ? "0" : "-100px" // Offset alternate rows
                            }}
                        >
                            {loopedLogos.map((logo, index) => (
                                <LogoItem key={`r${rowIndex}-${index}`} logo={logo} />
                            ))}
                        </div>
                    );
                })}
            </div>

            {/* Content Card Overlay - Two-column layout matching reference */}
            <div
                className="content-card"
                style={{
                    position: "relative",
                    zIndex: 10,
                    // Highly translucent glass-like opacity with enhanced blur
                    background: "rgba(255, 255, 255, 0.45)",
                    backdropFilter: "blur(28px)",
                    WebkitBackdropFilter: "blur(28px)",
                    borderRadius: "16px",
                    padding: "20px 28px",
                    maxWidth: "800px",
                    width: "75%",
                    // Enhanced layered shadows for floating effect
                    boxShadow: "0px 4px 12px rgba(0, 0, 0, 0.08), 0px 12px 32px rgba(0, 0, 0, 0.12), 0px 24px 64px rgba(0, 0, 0, 0.08), 0px 0 0 1px rgba(255, 255, 255, 0.4) inset",
                    border: "1px solid rgba(255, 255, 255, 0.4)",
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "24px",
                    alignItems: "center",
                    transform: "translateY(0)",
                    transition: "transform 0.3s ease, box-shadow 0.3s ease",
                }}
            >
                {/* Left Column: Heading */}
                <div style={{ textAlign: "left" }}>
                    <h2
                        className="integrations-heading"
                        style={{
                            fontSize: "1.5rem",
                            fontWeight: "400",
                            color: "#0F172A",
                            lineHeight: "1.4",
                            margin: "0",
                            letterSpacing: "0",
                            fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif",
                            wordWrap: "break-word",
                            overflowWrap: "break-word",
                        }}
                    >
                        Skeldir unifies and verifies your marketing data across every platform.
                    </h2>
                </div>

                {/* Right Column: Description */}
                <div style={{ textAlign: "left" }}>
                    <p
                        style={{
                            fontSize: "0.8125rem",
                            color: "#1E293B",
                            lineHeight: "1.6",
                            margin: "0",
                            fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif",
                            wordWrap: "break-word",
                            overflowWrap: "break-word",
                        }}
                    >
                        Native integrations with Google Ads, Meta, TikTok, Shopify, Stripe, and more—with privacy-first architecture—so you get decision-ready insights, not data chaos.
                    </p>
                </div>
            </div>

            {/* Styles for Animations & Responsiveness */}
            <style jsx>{`
                @keyframes scroll-left {
                    0% { transform: translateX(0); }
                    100% { transform: translateX(-33.33%); } /* Move 1/3 because we tripled the list */
                }
                @keyframes scroll-right {
                    0% { transform: translateX(-33.33%); }
                    100% { transform: translateX(0); }
                }

                .scroll-left {
                    animation: scroll-left 40s linear infinite;
                    will-change: transform;
                }
                .scroll-right {
                    animation: scroll-right 45s linear infinite;
                    will-change: transform;
                }

                @media (max-width: 1024px) {
                    .integrations-showcase {
                        min-height: 220px;
                        padding: 70px 0 32px 0;
                    }
                    .content-card {
                        padding: 16px 24px;
                        grid-template-columns: 1fr !important;
                        gap: 16px;
                    }
                    h2,
                    .integrations-heading {
                        font-size: 1.25rem !important;
                        text-align: center !important;
                    }
                    .content-card > div:last-child {
                        text-align: center !important;
                    }
                }
                @media (max-width: 768px) {
                    .integrations-showcase {
                        min-height: 200px;
                        padding: 60px 0 24px 0;
                    }
                    .content-card {
                        padding: 14px 16px !important;
                        width: 92% !important;
                        grid-template-columns: 1fr 1fr !important;
                        gap: 16px !important;
                        display: grid !important;
                        align-items: center !important;
                    }
                    h2,
                    .integrations-heading {
                        font-size: 1rem !important;
                        text-align: left !important;
                        color: #000000 !important;
                        font-weight: 500 !important;
                    }
                    p {
                        font-size: 0.7rem !important;
                        text-align: left !important;
                        line-height: 1.5 !important;
                    }
                    .content-card > div:first-child {
                        text-align: left !important;
                    }
                    .content-card > div:last-child {
                        text-align: left !important;
                    }
                    .logo-row {
                        gap: 20px !important;
                    }
                }
                
                @media (prefers-reduced-motion: reduce) {
                    .scroll-left, .scroll-right {
                        animation: none;
                    }
                }
            `}</style>
        </section>
    );
}

function LogoItem({ logo }: { logo: any }) {
    return (
        <div
            style={{
                width: "64px",
                height: "64px",
                background: "rgba(255, 255, 255, 0.7)", // Slightly higher opacity
                borderRadius: "12px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)",
                backdropFilter: "blur(4px)",
                flexShrink: 0,
            }}
        >
            {logo.component ? (
                logo.component
            ) : (
                <img
                    src={logo.src}
                    alt={logo.name}
                    loading="lazy"
                    decoding="async"
                    style={{
                        height: logo.height,
                        width: "auto",
                        maxWidth: "60%",
                        objectFit: "contain",
                        opacity: 0.9,
                    }}
                />
            )}
        </div>
    );
}
