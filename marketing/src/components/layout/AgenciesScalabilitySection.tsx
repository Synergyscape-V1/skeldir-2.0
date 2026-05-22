"use client";

import Image from "next/image";

/* ------------------------------------------------------------------ */
/*  Section 3 — Agency Scalability Proof                               */
/*  50/50 split: text stack (left) + phone mockup (right)              */
/*  Warm cream background (#F5F1E8)                                    */
/* ------------------------------------------------------------------ */

const FONT_SANS =
  "'DM Sans', var(--font-dm-sans), 'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

export function AgenciesScalabilitySection() {
  return (
    <section
      className="scalability-section"
      style={{
        backgroundColor: "#F5F1E8",
        color: "#1A1A1A",
        position: "relative",
        overflow: "hidden",
        width: "100%",
      }}
      aria-label="Agency scalability and white-label readiness"
    >
      <div
        className="scalability-container"
        style={{
          maxWidth: "1280px",
          margin: "0 auto",
          padding: "96px 48px",
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          alignItems: "center",
          gap: "64px",
        }}
      >
        {/* ─── LEFT COLUMN: Text Stack ─── */}
        <div
          className="scalability-text"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "0",
          }}
        >
          {/* Eyebrow */}
          <span
            className="scalability-eyebrow"
            style={{
              fontFamily: FONT_SANS,
              fontSize: "0.8125rem",
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "#6B7280",
              marginBottom: "20px",
            }}
          >
            White-label ready
          </span>

          {/* Headline */}
          <h2
            className="scalability-headline"
            style={{
              fontFamily: FONT_SANS,
              fontSize: "2.5rem",
              fontWeight: 600,
              lineHeight: 1.15,
              letterSpacing: "-0.025em",
              color: "#1A1A1A",
              margin: "0 0 24px 0",
            }}
          >
            Grow client portfolios with unified Bayesian attribution
          </h2>

          {/* Body */}
          <p
            className="scalability-body"
            style={{
              fontFamily: FONT_SANS,
              fontSize: "1.125rem",
              fontWeight: 400,
              lineHeight: 1.7,
              color: "#1A1A1A",
              opacity: 0.85,
              margin: "0 0 32px 0",
              maxWidth: "520px",
            }}
          >
            Skeldir&rsquo;s API-first design lets you add new clients in days,
            not months. Deploy white-label attribution dashboards that expose
            platform discrepancies and build client trust through transparent
            confidence ranges.
          </p>

          {/* CTA Button */}
          <div>
            <a
              href="/product"
              className="scalability-cta"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "12px",
                fontFamily: FONT_SANS,
                fontSize: "1rem",
                fontWeight: 600,
                color: "#1A1A1A",
                textDecoration: "none",
                cursor: "pointer",
                transition: "opacity 200ms ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.opacity = "0.75";
                const arrow = e.currentTarget.querySelector(
                  ".scalability-cta-arrow"
                ) as HTMLElement;
                if (arrow) arrow.style.transform = "translateX(4px)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.opacity = "1";
                const arrow = e.currentTarget.querySelector(
                  ".scalability-cta-arrow"
                ) as HTMLElement;
                if (arrow) arrow.style.transform = "translateX(0)";
              }}
            >
              <span>Learn more</span>
              <span
                className="scalability-cta-arrow"
                aria-hidden="true"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "36px",
                  height: "36px",
                  borderRadius: "50%",
                  backgroundColor: "#1E40AF",
                  color: "#FFFFFF",
                  fontSize: "1.125rem",
                  transition: "transform 200ms ease",
                  flexShrink: 0,
                }}
              >
                &rarr;
              </span>
            </a>
          </div>
        </div>

        {/* ─── RIGHT COLUMN: Phone Mockup ─── */}
        <div
          className="scalability-visual"
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            position: "relative",
          }}
        >
          <div
            className="scalability-phone-wrapper"
            style={{
              position: "relative",
              transform: "rotate(-6deg)",
              transition: "transform 400ms ease",
              marginLeft: "-40px",
            }}
          >
            <Image
              src="/agencies/final-image-4-3.png"
              alt="Skeldir white-label attribution dashboard on mobile device with Harvard Business Review partnership"
              width={420}
              height={560}
              quality={85}
              priority={false}
              className="scalability-phone-img"
              style={{
                display: "block",
                maxWidth: "100%",
                height: "auto",
                borderRadius: "24px",
                boxShadow: "0 20px 60px rgba(0, 0, 0, 0.18), 0 8px 24px rgba(0, 0, 0, 0.1)",
              }}
            />
          </div>
        </div>
      </div>

      {/* ─── SCOPED RESPONSIVE STYLES ─── */}
      <style>{`
        /* ===== Large desktop: >=1440px ===== */
        @media (min-width: 1440px) {
          .scalability-container {
            max-width: 1400px !important;
            padding: 112px 64px !important;
          }
          .scalability-headline {
            font-size: 2.75rem !important;
          }
        }

        /* ===== Ultra-wide: >=2560px ===== */
        @media (min-width: 2560px) {
          .scalability-container {
            max-width: 1600px !important;
          }
          .scalability-headline {
            font-size: 3rem !important;
          }
        }

        /* ===== Tablet: 768px – 1023px ===== */
        @media (min-width: 768px) and (max-width: 1023px) {
          .scalability-container {
            grid-template-columns: 1.4fr 1fr !important;
            padding: 72px 32px !important;
            gap: 40px !important;
          }
          .scalability-headline {
            font-size: 2rem !important;
          }
          .scalability-body {
            font-size: 1rem !important;
          }
          .scalability-phone-wrapper {
            margin-left: 0 !important;
          }
        }

        /* ===== Mobile: <768px ===== */
        @media (max-width: 767px) {
          .scalability-container {
            grid-template-columns: 1fr !important;
            padding: 64px 24px !important;
            gap: 48px !important;
          }
          .scalability-text {
            order: 2 !important;
          }
          .scalability-visual {
            order: 1 !important;
          }
          .scalability-headline {
            font-size: 1.875rem !important;
          }
          .scalability-body {
            font-size: 1rem !important;
            max-width: 100% !important;
          }
          .scalability-phone-wrapper {
            transform: rotate(0deg) !important;
            margin-left: 0 !important;
          }
          .scalability-phone-img {
            max-width: 400px !important;
            margin: 0 auto !important;
            display: block !important;
          }
        }

        /* ===== Very small screens: <375px ===== */
        @media (max-width: 374px) {
          .scalability-container {
            padding: 48px 16px !important;
            gap: 36px !important;
          }
          .scalability-headline {
            font-size: 1.625rem !important;
          }
          .scalability-body {
            font-size: 0.9375rem !important;
          }
          .scalability-phone-img {
            max-width: 280px !important;
          }
          .scalability-eyebrow {
            font-size: 0.75rem !important;
          }
        }
      `}</style>
    </section>
  );
}
