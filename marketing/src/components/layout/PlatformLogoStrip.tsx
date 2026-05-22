"use client";

import React from "react";

export function PlatformLogoStrip() {
    const logos = [
        {
            name: "Stripe",
            src: "/images/stripe-logo.png",
            height: "26px",
        },
        {
            name: "PayPal",
            component: (
                <svg viewBox="5.8 1.3 52.7 61.4" height="26" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: "auto" }}>
                    <path d="m50.3 5.9c-2.8-3.2-8-4.6-14.5-4.6h-19.1c-1.3 0-2.5 1-2.7 2.3l-8 50.4c-.2 1 .6 1.9 1.6 1.9h11.8l3-18.8-.1.6c.2-1.3 1.3-2.3 2.7-2.3h5.6c11 0 19.6-4.5 22.1-17.4.1-.4.1-.8.2-1.1-.3-.2-.3-.2 0 0 .7-4.8 0-8-2.6-11" fill="#263b80"/>
                    <path d="m52.9 16.9c-.1.4-.1.7-.2 1.1-2.5 12.9-11.1 17.4-22.1 17.4h-5.6c-1.3 0-2.5 1-2.7 2.3l-3.7 23.3c-.1.9.5 1.7 1.4 1.7h9.9c1.2 0 2.2-.9 2.4-2l.1-.5 1.9-11.8.1-.7c.2-1.2 1.2-2 2.4-2h1.5c9.6 0 17.1-3.9 19.3-15.2.9-4.7.4-8.7-2-11.4-.8-.9-1.7-1.6-2.7-2.2" fill="#139ad6"/>
                    <path d="m50.2 15.9-1.2-.3c-.4-.1-.8-.2-1.3-.2-1.5-.3-3.2-.4-4.9-.4h-14.9c-.4 0-.7.1-1 .2-.7.3-1.2 1-1.3 1.8l-3.2 20.1-.1.6c.2-1.3 1.3-2.3 2.7-2.3h5.6c11 0 19.6-4.5 22.1-17.4.1-.4.1-.8.2-1.1-.6-.3-1.3-.6-2.1-.9-.2 0-.4-.1-.6-.1" fill="#232c65"/>
                    <path d="m35.7 1.3h-19c-1.3 0-2.5 1-2.7 2.3l-4.6 28.8 30.8-30.8c-1.4-.2-2.9-.3-4.5-.3z" fill="#2a4dad"/>
                    <path d="m56.5 20.5c-.3-.5-.5-1-.9-1.5-.7-.8-1.7-1.5-2.7-2.1-.1.4-.1.7-.2 1.1-2.5 12.9-11.1 17.4-22.1 17.4h-5.6c-1.3 0-2.5 1-2.7 2.3l-3.2 20.2z" fill="#0d7dbc"/>
                    <path d="m7.6 55.9h11.8l2.9-18.2c0-.3.1-.5.2-.7l-16.4 16.4-.1.6c-.1 1 .6 1.9 1.6 1.9z" fill="#232c65"/>
                    <path d="m32.1 1.3h-15.4c-.4 0-.7.1-1 .2l-1.5 1.5c-.1.2-.2.4-.2.6l-3 18.8z" fill="#436bc4"/>
                </svg>
            ),
        },
        {
            name: "Shopify",
            src: "/images/shopify-logo.webp",
            height: "59px",
        },
        {
            name: "Meta",
            src: "/images/meta-logo-new.png",
            height: "20px",
        },
        {
            name: "Google Ads",
            src: "/images/google-ads-icon.webp",
            height: "24px",
        },
        {
            name: "TikTok",
            src: "/images/tiktok-icon.png",
            height: "24px",
        },
    ];

    return (
        <div
            className="platform-logo-strip-container"
            style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "24px",
                marginTop: "32px",
                flexWrap: "wrap",
                paddingTop: "24px",
                borderTop: "1px solid #F1F5F9",
            }}
        >
            {logos.map((logo) => (
                <div
                    key={logo.name}
                    className={`platform-logo ${logo.name === "Shopify" ? "platform-logo-shopify" : ""}`}
                    style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        opacity: 0.6,
                        filter: "grayscale(100%)",
                        transition: "all 0.2s ease",
                        cursor: "default",
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
                                objectFit: "contain",
                            }}
                        />
                    )}
                </div>
            ))}
            <style jsx>{`
        .platform-logo:hover {
          opacity: 1 !important;
          filter: grayscale(0%) !important;
        }

        @media (max-width: 767px) {
          .platform-logo-strip-container {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 16px !important;
            flex-wrap: wrap !important;
          }

          .platform-logo {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            height: auto !important;
            line-height: 0 !important;
            vertical-align: middle !important;
          }

          /* Keep Shopify logo at its current size (59px) */
          .platform-logo-shopify img {
            height: 59px !important;
            width: auto !important;
          }

          /* Align all logos to the same baseline by ensuring consistent vertical alignment */
          .platform-logo img,
          .platform-logo svg {
            vertical-align: middle !important;
            display: block !important;
            margin: 0 !important;
          }

          /* Ensure all logos are on the same horizontal plane - use flexbox alignment */
          .platform-logo-strip-container {
            align-items: center !important;
          }
        }
      `}</style>
        </div>
    );
}
