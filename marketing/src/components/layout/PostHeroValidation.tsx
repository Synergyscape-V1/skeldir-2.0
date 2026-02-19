"use client";

import Link from "next/link";

/* ------------------------------------------------------------------ */
/*  Post-Hero Validation Section                                       */
/*  Stats Row → Testimonial → Feature Cards                           */
/*  Light (enterprise) background for readability                      */
/* ------------------------------------------------------------------ */

/* ---------- Stats Pillar Data ---------- */
const STATS = [
  {
    primary: "Statistical transparency",
    secondary: "confidence ranges, not black-box guesses",
  },
  {
    primary: "Multi-client",
    secondary: "portfolios managed from unified dashboard",
  },
  {
    primary: "Revenue verification",
    secondary: "exposing platform over-reporting",
  },
  {
    primary: "API-first design",
    secondary: "white-label ready for agency workflows",
  },
] as const;

/* ---------- Feature Card Data ---------- */
const FEATURES = [
  {
    title: "Statistical Transparency Engine",
    description:
      "Bayesian confidence ranges show which channels actually drive revenue, with statistical rigor that survives CFO scrutiny.",
    mockupLabel: "Bayesian Confidence Range UI",
    mockupBg: "#EAF6F3",
  },
  {
    title: "Revenue Verification Ground Truth",
    description:
      "Direct Stripe/PayPal integration exposes 16-40% platform over-reporting, ending the attribution guessing game.",
    mockupLabel: "Revenue Verification Dashboard",
    mockupBg: "#FDF4E1",
  },
  {
    title: "Budget Optimization Guidance",
    description:
      "Deterministic calculations + AI synthesis recommend optimal allocations, preventing $175K-$250K annual misallocation.",
    mockupLabel: "Budget Optimization Interface",
    mockupBg: "#EEF2FF",
  },
] as const;

/* ---------- Shared Typography Stacks ---------- */
const FONT_SERIF =
  "var(--font-playfair), 'Playfair Display', 'Georgia', 'Times New Roman', serif";
const FONT_SANS =
  "'DM Sans', var(--font-dm-sans), 'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

/* ================================================================== */
/*  Component                                                          */
/* ================================================================== */

export function PostHeroValidation() {
  return (
    <section
      className="phv-section"
      style={{
        backgroundColor: "#FFFFFF",
        color: "#111827",
        position: "relative",
        overflow: "hidden",
      }}
      aria-label="Skeldir platform capabilities and social proof"
    >
      {/* ─── STATS ROW ─── */}
      <div
        className="phv-stats-row"
        style={{
          maxWidth: "1400px",
          margin: "0 auto",
          padding: "56px 48px",
        }}
      >
        <div className="phv-stats-grid">
          {STATS.map((stat, i) => (
            <div
              key={i}
              className="phv-stat-col"
              style={{
                textAlign: "center",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "12px",
              }}
            >
              <h3
                className="phv-stat-primary"
                style={{
                  fontFamily: FONT_SERIF,
                  fontSize: "3.25rem",
                  fontWeight: 650,
                  lineHeight: 1.2,
                  letterSpacing: "-0.03em",
                  color: "#0B1220",
                  textShadow: "0 1px 0 rgba(255,255,255,0.7)",
                  margin: 0,
                }}
              >
                {stat.primary}
              </h3>
              <p
                className="phv-stat-secondary"
                style={{
                  fontFamily: FONT_SANS,
                  fontSize: "1rem",
                  fontWeight: 400,
                  lineHeight: 1.6,
                  color: "#4B5563",
                  margin: 0,
                  maxWidth: "280px",
                }}
              >
                {stat.secondary}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* ─── TESTIMONIAL ─── */}
      <div
        className="phv-testimonial-wrapper"
        style={{
          maxWidth: "900px",
          margin: "0 auto",
          padding: "72px 48px",
          textAlign: "center",
          position: "relative",
        }}
      >
        {/* Decorative opening quote marks */}
        <span
          aria-hidden="true"
          className="phv-quote-mark"
          style={{
            fontFamily: FONT_SERIF,
            fontSize: "120px",
            lineHeight: 1,
            color: "rgba(17, 24, 39, 0.08)",
            position: "absolute",
            top: "28px",
            left: "0",
            userSelect: "none",
            pointerEvents: "none",
          }}
        >
          &ldquo;
        </span>

        {/* Main quote */}
        <blockquote
          style={{ margin: 0, padding: 0 }}
        >
          <p
            className="phv-quote-text"
            style={{
              fontFamily: FONT_SERIF,
              fontStyle: "italic",
              fontSize: "2rem",
              fontWeight: 400,
              lineHeight: 1.5,
              color: "#111827",
              maxWidth: "800px",
              margin: "0 auto",
            }}
          >
            Finally, confidence ranges instead of single-point estimates. Our
            clients actually trust the attribution data now.
          </p>
        </blockquote>

        {/* Attribution */}
        <p
          className="phv-attribution"
          style={{
            fontFamily: FONT_SANS,
            fontWeight: 600,
            fontSize: "1rem",
            color: "#111827",
            marginTop: "24px",
            marginBottom: 0,
          }}
        >
          &mdash;Catherine Hayden, National Director of Marketing @ City
          Analytics
        </p>

        {/* Spend credential */}
        <p
          className="phv-spend-credential"
          style={{
            fontFamily: FONT_SANS,
            fontWeight: 400,
            fontSize: "0.875rem",
            color: "#6B7280",
            marginTop: "8px",
            marginBottom: 0,
          }}
        >
          $2M annual ad spend across Google, Meta, and TikTok
        </p>

        {/* CTA Button */}
        <div style={{ marginTop: "32px" }}>
          <Link
            href="/book-demo"
            className="phv-cta-button"
            style={{
              display: "inline-flex",
              alignItems: "center",
              fontFamily: FONT_SANS,
              fontWeight: 600,
              fontSize: "1rem",
              color: "#000000",
              textDecoration: "none",
              gap: "8px",
              transition: "color 200ms ease, text-decoration-color 200ms ease",
              textDecorationLine: "underline",
              textDecorationThickness: "2px",
              textUnderlineOffset: "4px",
              textDecorationColor: "rgba(37, 99, 235, 0.35)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "#000000";
              e.currentTarget.style.textDecorationColor =
                "rgba(37, 99, 235, 0.7)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "#000000";
              e.currentTarget.style.textDecorationColor =
                "rgba(37, 99, 235, 0.35)";
            }}
          >
            See Skeldir&rsquo;s Bayesian attribution in action
            <span aria-hidden="true" style={{ lineHeight: 1 }}>
              →
            </span>
          </Link>
        </div>
      </div>

      {/* ─── FEATURE CARDS ─── */}
      <div
        className="phv-features-wrapper"
        style={{
          maxWidth: "1400px",
          margin: "0 auto",
          padding: "0 48px 64px",
        }}
      >
        {/* Section header */}
        <h2
          className="phv-features-header"
          style={{
            fontFamily: FONT_SERIF,
            fontSize: "2.5rem",
            fontWeight: 500,
            lineHeight: 1.2,
            letterSpacing: "-0.01em",
            color: "#111827",
            textAlign: "center",
            marginTop: 0,
            marginBottom: "64px",
          }}
        >
          The Bayesian difference: From statistical rigor to verified revenue
        </h2>

        {/* 3-card grid */}
        <div className="phv-cards-grid">
          {FEATURES.map((feature, i) => (
            <div
              key={i}
              className="phv-card"
              style={{
                backgroundColor: "#FFFFFF",
                borderRadius: "12px",
                overflow: "hidden",
                border: "1px solid #E5E7EB",
                display: "flex",
                flexDirection: "column",
                boxShadow:
                  "0 1px 2px rgba(15, 23, 42, 0.06), 0 8px 24px rgba(15, 23, 42, 0.06)",
              }}
            >
              {/* Mockup placeholder */}
              <div
                className="phv-card-mockup"
                style={{
                  backgroundColor: feature.mockupBg,
                  height: "220px",
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  position: "relative",
                  overflow: "hidden",
                  borderBottom: "1px solid #E5E7EB",
                }}
                aria-label={feature.mockupLabel}
              >
                {i === 0 ? (
                  <img
                    src="/agencies/final-image-3-1.png"
                    alt="Bayesian Confidence Range UI"
                    loading="lazy"
                    decoding="async"
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                      objectPosition: "center",
                      display: "block",
                      maxWidth: "100%",
                      maxHeight: "100%",
                      borderRadius: "inherit",
                    }}
                  />
                ) : i === 1 ? (
                  <img
                    src="/agencies/final-image-1-2.png"
                    alt="Revenue Verification Dashboard"
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                      objectPosition: "center",
                      display: "block",
                      maxWidth: "100%",
                      maxHeight: "100%",
                      borderRadius: "inherit",
                    }} loading="lazy" decoding="async" />
                ) : i === 2 ? (
                  <img
                    src="/agencies/final-image-2-2.png"
                    alt="Budget Optimization Interface"
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                      objectPosition: "center",
                      display: "block",
                    }} loading="lazy" decoding="async" />
                ) : (
                  /* Wireframe placeholder */
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: "12px",
                      opacity: 0.7,
                    }}
                  >
                    {/* Mini chart bars */}
                    <div
                      style={{ display: "flex", gap: "6px", alignItems: "flex-end" }}
                    >
                      <div
                        style={{
                          width: "18px",
                          height: "40px",
                          backgroundColor: "rgba(17, 24, 39, 0.12)",
                          borderRadius: "3px",
                        }}
                      />
                      <div
                        style={{
                          width: "18px",
                          height: "65px",
                          backgroundColor: "rgba(17, 24, 39, 0.16)",
                          borderRadius: "3px",
                        }}
                      />
                      <div
                        style={{
                          width: "18px",
                          height: "50px",
                          backgroundColor: "rgba(17, 24, 39, 0.14)",
                          borderRadius: "3px",
                        }}
                      />
                      <div
                        style={{
                          width: "18px",
                          height: "75px",
                          backgroundColor: "rgba(37, 99, 235, 0.55)",
                          borderRadius: "3px",
                        }}
                      />
                      <div
                        style={{
                          width: "18px",
                          height: "55px",
                          backgroundColor: "rgba(17, 24, 39, 0.12)",
                          borderRadius: "3px",
                        }}
                      />
                    </div>
                    <span
                      style={{
                        fontFamily: FONT_SANS,
                        fontSize: "11px",
                        fontWeight: 500,
                        color: "rgba(17, 24, 39, 0.55)",
                        letterSpacing: "0.05em",
                        textTransform: "uppercase",
                      }}
                    >
                      {feature.mockupLabel}
                    </span>
                  </div>
                )}
              </div>

              {/* Text content */}
              <div style={{ padding: "24px 24px 32px" }}>
                <h3
                  className="phv-card-title"
                  style={{
                    fontFamily: FONT_SANS,
                    fontWeight: 700,
                    fontSize: "1.25rem",
                    lineHeight: 1.3,
                    color: "#111827",
                    margin: "0 0 12px 0",
                  }}
                >
                  {feature.title}
                </h3>
                <p
                  className="phv-card-desc"
                  style={{
                    fontFamily: FONT_SANS,
                    fontWeight: 400,
                    fontSize: "1rem",
                    lineHeight: 1.6,
                    color: "#4B5563",
                    margin: 0,
                  }}
                >
                  {feature.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ─── SCOPED RESPONSIVE STYLES ─── */}
      <style>{`
        /* ===== Base layout ===== */
        .phv-section {
          display: flex;
          flex-direction: column;
        }

        /* ===== Stats Grid ===== */
        .phv-stats-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 48px;
        }

        /* ===== Feature Cards Grid ===== */
        .phv-cards-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 32px;
        }

        .phv-card {
          transition: transform 200ms ease, box-shadow 200ms ease;
        }
        .phv-card:hover {
          transform: translateY(-4px);
          box-shadow: 0 16px 44px rgba(15, 23, 42, 0.14);
        }

        /* ===== Desktop: >=1024px ===== */
        @media (min-width: 1024px) {
          .phv-section {
            /* Condensed desktop: reduce viewport consumption */
            min-height: 62vh;
          }

          /* Keep stats header high in viewport and tighten vertical rhythm */
          .phv-stats-row {
            padding-top: 40px !important;
            padding-bottom: 28px !important;
          }

          .phv-testimonial-wrapper {
            padding-top: 44px !important;
            padding-bottom: 36px !important;
          }

          /* Let feature cards peek above the fold */
          .phv-features-wrapper {
            padding-top: 24px !important;
            padding-bottom: 40px !important;
          }

          /* Slightly tighten typography for above-fold fit */
          .phv-stat-primary {
            font-size: 2.6rem !important;
            line-height: 1.1 !important;
          }
          .phv-quote-text {
            font-size: 1.35rem !important;
            line-height: 1.42 !important;
          }
          .phv-features-header {
            font-size: 1.85rem !important;
            margin-bottom: 32px !important;
          }

          /* Reduce internal spacing so cards start sooner */
          .phv-features-wrapper > .phv-features-header {
            margin-bottom: 28px !important;
          }
          .phv-cards-grid {
            gap: 20px !important;
          }
        }

        /* ===== Tablet: 768px – 1023px ===== */
        @media (max-width: 1023px) {
          .phv-stats-row {
            padding: 48px 32px !important;
          }

          .phv-stat-primary {
            font-size: 2.25rem !important;
          }

          .phv-stat-secondary {
            font-size: 0.875rem !important;
          }

          .phv-testimonial-wrapper {
            padding: 56px 32px !important;
          }

          .phv-quote-text {
            font-size: 1.75rem !important;
            max-width: 90vw !important;
          }

          .phv-quote-mark {
            font-size: 80px !important;
            top: 18px !important;
          }

          .phv-features-wrapper {
            padding: 0 32px 56px !important;
          }

          .phv-features-header {
            font-size: 2rem !important;
            margin-bottom: 48px !important;
          }

          .phv-cards-grid {
            grid-template-columns: 1fr !important;
            max-width: 600px;
            margin: 0 auto;
          }
        }

        /* ===== Mobile: <768px ===== */
        @media (max-width: 767px) {
          .phv-stats-row {
            padding: 40px 20px !important;
          }

          .phv-stats-grid {
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 32px 24px !important;
          }

          .phv-stat-primary {
            font-size: 1.75rem !important;
          }

          .phv-stat-secondary {
            font-size: 0.875rem !important;
            max-width: 200px !important;
          }

          .phv-testimonial-wrapper {
            padding: 44px 20px !important;
          }

          .phv-quote-text {
            font-size: 1.5rem !important;
          }

          .phv-attribution {
            font-size: 0.875rem !important;
          }

          .phv-spend-credential {
            font-size: 0.8125rem !important;
          }

          .phv-quote-mark {
            font-size: 64px !important;
            top: 14px !important;
            left: 4px !important;
          }

          .phv-features-wrapper {
            padding: 0 16px 44px !important;
          }

          .phv-features-header {
            font-size: 1.625rem !important;
            margin-bottom: 32px !important;
          }

          .phv-cards-grid {
            grid-template-columns: 1fr !important;
            gap: 24px !important;
          }

          .phv-card-mockup {
            height: 180px !important;
          }

          .phv-cta-button {
            padding: 14px 24px !important;
            font-size: 0.9375rem !important;
          }
        }

        /* ===== Very small screens: <375px ===== */
        @media (max-width: 374px) {
          .phv-stat-primary {
            font-size: 1.5rem !important;
          }

          .phv-stat-secondary {
            font-size: 0.8125rem !important;
          }

          .phv-quote-text {
            font-size: 1.25rem !important;
          }

          .phv-features-header {
            font-size: 1.375rem !important;
          }
        }
      `}</style>
    </section>
  );
}
