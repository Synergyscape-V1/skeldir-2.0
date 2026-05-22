"use client";

import Image from "next/image";
import { useState } from "react";

/* ------------------------------------------------------------------ */
/*  Section 4 — Statistical Authority & Lead Capture                   */
/*  Upper: 50/50 split (laptop mockup left, text right)                */
/*  Lower: Centered lead capture form (playbook download)              */
/*  Dark charcoal background (#1C1C1E)                                 */
/* ------------------------------------------------------------------ */

const FONT_SANS =
  "'DM Sans', var(--font-dm-sans), 'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
const FONT_SERIF =
  "var(--font-playfair), 'Playfair Display', 'Georgia', 'Times New Roman', serif";

const COUNTRIES = [
  "United States",
  "United Kingdom",
  "Canada",
  "Australia",
  "Germany",
  "France",
  "Netherlands",
  "Sweden",
  "Norway",
  "Denmark",
  "Finland",
  "Ireland",
  "New Zealand",
  "Singapore",
  "Japan",
  "South Korea",
  "India",
  "Brazil",
  "Mexico",
  "South Africa",
  "United Arab Emirates",
  "Saudi Arabia",
  "Spain",
  "Italy",
  "Portugal",
  "Switzerland",
  "Austria",
  "Belgium",
  "Poland",
  "Czech Republic",
  "Israel",
  "Argentina",
  "Chile",
  "Colombia",
  "Philippines",
  "Thailand",
  "Malaysia",
  "Indonesia",
  "Vietnam",
  "Nigeria",
  "Kenya",
  "Egypt",
  "Other",
];

export function AgenciesSection4() {
  const [email, setEmail] = useState("");
  const [country, setCountry] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !country) return;
    setIsSubmitting(true);
    // Simulate form submission — replace with actual endpoint
    await new Promise((resolve) => setTimeout(resolve, 1200));
    setIsSubmitting(false);
    setIsSubmitted(true);
  };

  return (
    <section
      className="s4-section"
      style={{
        backgroundColor: "#1C1C1E",
        color: "#FFFFFF",
        position: "relative",
        overflow: "hidden",
        width: "100%",
      }}
      aria-label="Statistical methodology and playbook download"
    >
      {/* ─── UPPER: Split Layout — Image Left, Text Right ─── */}
      <div
        className="s4-upper-container"
        style={{
          maxWidth: "1280px",
          margin: "0 auto",
          padding: "96px 48px 72px",
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          alignItems: "center",
          gap: "64px",
        }}
      >
        {/* LEFT COLUMN: Laptop Mockup */}
        <div
          className="s4-image-col"
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            position: "relative",
          }}
        >
          <div
            className="s4-laptop-wrapper"
            style={{
              position: "relative",
              maxWidth: "560px",
              width: "100%",
            }}
          >
            <Image
              src="/agencies/final-image-5-1.png"
              alt="The Attribution Transparency Playbook displayed on a laptop — Bayesian Intelligence for Mid-Market Agencies whitepaper by Skeldir and WARC"
              width={560}
              height={620}
              quality={90}
              priority={false}
              className="s4-laptop-img"
              style={{
                display: "block",
                width: "100%",
                height: "auto",
                borderRadius: "12px",
              }}
            />
          </div>
        </div>

        {/* RIGHT COLUMN: Text Stack */}
        <div
          className="s4-text-col"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "0",
          }}
        >
          {/* Headline */}
          <h2
            className="s4-headline"
            style={{
              fontFamily: FONT_SERIF,
              fontSize: "2.5rem",
              fontWeight: 500,
              lineHeight: 1.2,
              letterSpacing: "-0.015em",
              color: "#FFFFFF",
              margin: "0 0 28px 0",
            }}
          >
            Attribution transparency for agencies that can&rsquo;t afford $300K data teams
          </h2>

          {/* Body */}
          <p
            className="s4-body"
            style={{
              fontFamily: FONT_SANS,
              fontSize: "1.125rem",
              fontWeight: 400,
              lineHeight: 1.7,
              color: "#F5F1E8",
              opacity: 0.9,
              margin: 0,
              maxWidth: "540px",
            }}
          >
            Bayesian statistics isn&rsquo;t marketing jargon&mdash;it&rsquo;s the mathematical framework that quantifies uncertainty in your attribution data. This approach separates signal from noise, so you can assess which channels actually drive revenue, identify where platform reporting conflicts with reality, and defend budget recommendations with statistical confidence.
          </p>
        </div>
      </div>

      {/* ─── Divider ─── */}
      <div
        style={{
          maxWidth: "1280px",
          margin: "0 auto",
          padding: "0 48px",
        }}
      >
        <div
          className="s4-divider"
          style={{
            height: "1px",
            backgroundColor: "rgba(255, 255, 255, 0.1)",
            width: "100%",
          }}
        />
      </div>

      {/* ─── LOWER: Lead Capture Form ─── */}
      <div
        className="s4-lower-container"
        style={{
          maxWidth: "900px",
          margin: "0 auto",
          padding: "72px 48px 96px",
          textAlign: "center",
        }}
      >
        {/* Playbook Heading */}
        <h3
          className="s4-playbook-heading"
          style={{
            fontFamily: FONT_SERIF,
            fontSize: "2rem",
            fontWeight: 500,
            lineHeight: 1.25,
            color: "#FFFFFF",
            margin: "0 0 20px 0",
            maxWidth: "800px",
            marginLeft: "auto",
            marginRight: "auto",
          }}
        >
          The Attribution Transparency Playbook: Bayesian Intelligence for Mid-Market Agencies
        </h3>

        {/* Subheading */}
        <p
          className="s4-playbook-sub"
          style={{
            fontFamily: FONT_SANS,
            fontSize: "1.125rem",
            fontWeight: 400,
            lineHeight: 1.65,
            color: "#F5F1E8",
            opacity: 0.85,
            margin: "0 auto 48px",
            maxWidth: "700px",
          }}
        >
          Download our implementation guide to benchmark your attribution maturity against industry standards, assess your statistical readiness, and eliminate the operational gaps blocking scalable client growth.
        </p>

        {/* Form */}
        {!isSubmitted ? (
          <form
            onSubmit={handleSubmit}
            className="s4-form"
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "24px",
              maxWidth: "680px",
              margin: "0 auto",
            }}
            noValidate={false}
          >
            {/* Form Fields Row */}
            <div
              className="s4-form-row"
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "20px",
              }}
            >
              {/* Email Field */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                  textAlign: "left",
                }}
              >
                <label
                  htmlFor="s4-email"
                  style={{
                    fontFamily: FONT_SANS,
                    fontSize: "0.875rem",
                    fontWeight: 500,
                    color: "#F5F1E8",
                  }}
                >
                  Business Email Address
                </label>
                <input
                  id="s4-email"
                  name="email"
                  type="email"
                  required
                  placeholder="Enter Business Email Address"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="s4-input"
                  style={{
                    fontFamily: FONT_SANS,
                    fontSize: "1rem",
                    fontWeight: 400,
                    height: "50px",
                    padding: "0 16px",
                    backgroundColor: "#FFFFFF",
                    color: "#1A1A1A",
                    border: "1.5px solid #D1D5DB",
                    borderRadius: "8px",
                    outline: "none",
                    width: "100%",
                    boxSizing: "border-box",
                    transition: "border-color 200ms ease, box-shadow 200ms ease",
                  }}
                  onFocus={(e) => {
                    e.currentTarget.style.borderColor = "#FFD700";
                    e.currentTarget.style.boxShadow =
                      "0 0 0 3px rgba(255, 215, 0, 0.2)";
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.borderColor = "#D1D5DB";
                    e.currentTarget.style.boxShadow = "none";
                  }}
                />
              </div>

              {/* Country Dropdown */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                  textAlign: "left",
                }}
              >
                <label
                  htmlFor="s4-country"
                  style={{
                    fontFamily: FONT_SANS,
                    fontSize: "0.875rem",
                    fontWeight: 500,
                    color: "#F5F1E8",
                  }}
                >
                  Country
                </label>
                <select
                  id="s4-country"
                  name="country"
                  required
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  className="s4-select"
                  style={{
                    fontFamily: FONT_SANS,
                    fontSize: "1rem",
                    fontWeight: 400,
                    height: "50px",
                    padding: "0 16px",
                    backgroundColor: "#FFFFFF",
                    color: country ? "#1A1A1A" : "#9CA3AF",
                    border: "1.5px solid #D1D5DB",
                    borderRadius: "8px",
                    outline: "none",
                    width: "100%",
                    boxSizing: "border-box",
                    appearance: "none",
                    backgroundImage:
                      'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'12\' height=\'8\' viewBox=\'0 0 12 8\'%3E%3Cpath d=\'M1 1l5 5 5-5\' stroke=\'%236B7280\' stroke-width=\'1.5\' fill=\'none\' stroke-linecap=\'round\' stroke-linejoin=\'round\'/%3E%3C/svg%3E")',
                    backgroundRepeat: "no-repeat",
                    backgroundPosition: "right 16px center",
                    cursor: "pointer",
                    transition: "border-color 200ms ease, box-shadow 200ms ease",
                  }}
                  onFocus={(e) => {
                    e.currentTarget.style.borderColor = "#FFD700";
                    e.currentTarget.style.boxShadow =
                      "0 0 0 3px rgba(255, 215, 0, 0.2)";
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.borderColor = "#D1D5DB";
                    e.currentTarget.style.boxShadow = "none";
                  }}
                >
                  <option value="" disabled>
                    Please select your country
                  </option>
                  {COUNTRIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Privacy Notice */}
            <p
              style={{
                fontFamily: FONT_SANS,
                fontSize: "0.75rem",
                fontWeight: 400,
                lineHeight: 1.5,
                color: "rgba(255, 255, 255, 0.5)",
                margin: 0,
                textAlign: "left",
              }}
            >
              By requesting this content, you agree to permit Skeldir to use the
              information provided to contact you about its products and services.
              Your information will be processed as described in our{" "}
              <a
                href="/privacy"
                style={{
                  color: "rgba(255, 255, 255, 0.65)",
                  textDecoration: "underline",
                  textUnderlineOffset: "2px",
                }}
              >
                Global Privacy Statement
              </a>
              .
            </p>

            {/* Required Fields Note */}
            <p
              style={{
                fontFamily: FONT_SANS,
                fontSize: "0.75rem",
                fontWeight: 400,
                color: "rgba(255, 255, 255, 0.45)",
                margin: "0",
                textAlign: "left",
              }}
            >
              Please select an item in the list.
            </p>

            {/* Submit Button */}
            <div style={{ display: "flex", justifyContent: "center", marginTop: "8px" }}>
              <button
                type="submit"
                disabled={isSubmitting}
                className="s4-submit-btn"
                style={{
                  fontFamily: FONT_SANS,
                  fontSize: "1rem",
                  fontWeight: 600,
                  height: "50px",
                  padding: "0 40px",
                  backgroundColor: "#FFD700",
                  color: "#1A1A1A",
                  border: "none",
                  borderRadius: "50px",
                  cursor: isSubmitting ? "wait" : "pointer",
                  transition:
                    "background-color 200ms ease, transform 150ms ease, box-shadow 200ms ease",
                  opacity: isSubmitting ? 0.7 : 1,
                  letterSpacing: "0.01em",
                }}
                onMouseEnter={(e) => {
                  if (!isSubmitting) {
                    e.currentTarget.style.backgroundColor = "#FFC800";
                    e.currentTarget.style.transform = "translateY(-1px)";
                    e.currentTarget.style.boxShadow =
                      "0 4px 16px rgba(255, 215, 0, 0.35)";
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = "#FFD700";
                  e.currentTarget.style.transform = "translateY(0)";
                  e.currentTarget.style.boxShadow = "none";
                }}
              >
                {isSubmitting ? "Submitting..." : "Download now"}
              </button>
            </div>
          </form>
        ) : (
          /* Success State */
          <div
            style={{
              padding: "48px 32px",
              border: "1px solid rgba(255, 215, 0, 0.3)",
              borderRadius: "12px",
              backgroundColor: "rgba(255, 215, 0, 0.05)",
              maxWidth: "680px",
              margin: "0 auto",
            }}
          >
            <p
              style={{
                fontFamily: FONT_SANS,
                fontSize: "1.25rem",
                fontWeight: 600,
                color: "#FFD700",
                margin: "0 0 12px 0",
              }}
            >
              Your playbook is on its way.
            </p>
            <p
              style={{
                fontFamily: FONT_SANS,
                fontSize: "1rem",
                fontWeight: 400,
                color: "#F5F1E8",
                opacity: 0.85,
                margin: 0,
              }}
            >
              Check your inbox for the Attribution Transparency Playbook. If you
              don&rsquo;t see it within a few minutes, check your spam folder.
            </p>
          </div>
        )}
      </div>

      {/* ─── SCOPED RESPONSIVE STYLES ─── */}
      <style>{`
        /* ===== Large desktop: >=1440px ===== */
        @media (min-width: 1440px) {
          .s4-upper-container {
            max-width: 1400px !important;
            padding: 112px 64px 80px !important;
          }
          .s4-headline {
            font-size: 2.75rem !important;
          }
          .s4-playbook-heading {
            font-size: 2.25rem !important;
          }
        }

        /* ===== Ultra-wide: >=2560px ===== */
        @media (min-width: 2560px) {
          .s4-upper-container {
            max-width: 1600px !important;
          }
          .s4-headline {
            font-size: 3rem !important;
          }
        }

        /* ===== Tablet: 768px – 1023px ===== */
        @media (min-width: 768px) and (max-width: 1023px) {
          .s4-upper-container {
            grid-template-columns: 2fr 3fr !important;
            padding: 72px 32px 56px !important;
            gap: 40px !important;
          }
          .s4-headline {
            font-size: 2rem !important;
          }
          .s4-body {
            font-size: 1rem !important;
          }
          .s4-lower-container {
            padding: 56px 32px 72px !important;
          }
          .s4-playbook-heading {
            font-size: 1.75rem !important;
          }
          .s4-playbook-sub {
            font-size: 1rem !important;
          }
          .s4-form-row {
            grid-template-columns: 1fr !important;
          }
          .s4-divider {
            margin: 0 !important;
          }
        }

        /* ===== Mobile: <768px ===== */
        @media (max-width: 767px) {
          .s4-upper-container {
            grid-template-columns: 1fr !important;
            padding: 64px 24px 48px !important;
            gap: 36px !important;
          }
          .s4-image-col {
            order: 1 !important;
          }
          .s4-text-col {
            order: 2 !important;
          }
          .s4-laptop-wrapper {
            max-width: 100% !important;
          }
          .s4-laptop-img {
            max-height: 350px !important;
            width: auto !important;
            margin: 0 auto !important;
            display: block !important;
          }
          .s4-headline {
            font-size: 1.875rem !important;
          }
          .s4-body {
            font-size: 1rem !important;
            max-width: 100% !important;
          }
          .s4-lower-container {
            padding: 48px 24px 64px !important;
          }
          .s4-playbook-heading {
            font-size: 1.5rem !important;
          }
          .s4-playbook-sub {
            font-size: 0.9375rem !important;
            margin-bottom: 36px !important;
          }
          .s4-form-row {
            grid-template-columns: 1fr !important;
          }
          .s4-submit-btn {
            width: 100% !important;
          }
          .s4-divider {
            margin: 0 !important;
          }
        }

        /* ===== Very small screens: <375px ===== */
        @media (max-width: 374px) {
          .s4-upper-container {
            padding: 48px 16px 40px !important;
            gap: 28px !important;
          }
          .s4-headline {
            font-size: 1.625rem !important;
          }
          .s4-body {
            font-size: 0.9375rem !important;
          }
          .s4-lower-container {
            padding: 40px 16px 56px !important;
          }
          .s4-playbook-heading {
            font-size: 1.375rem !important;
          }
          .s4-playbook-sub {
            font-size: 0.875rem !important;
          }
        }

        /* ===== Focus visible for accessibility ===== */
        .s4-input:focus-visible,
        .s4-select:focus-visible {
          border-color: #FFD700 !important;
          box-shadow: 0 0 0 3px rgba(255, 215, 0, 0.25) !important;
          outline: none !important;
        }

        .s4-submit-btn:focus-visible {
          outline: 2px solid #FFD700 !important;
          outline-offset: 3px !important;
        }

        .s4-submit-btn:active:not(:disabled) {
          transform: translateY(0) !important;
          background-color: #E6C200 !important;
        }
      `}</style>
    </section>
  );
}
