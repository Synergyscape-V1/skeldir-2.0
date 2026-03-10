"use client";

// ============================================================================
// FINAL CTA SECTION
// Reference: Final CTA (Expected State).png - Homepage Conversion Finale
// Background Image: final-cta-background.png (contains all visual layers)
// ============================================================================

export function FinalCTA() {
  return (
    <section
      id="final-cta"
      style={{
        position: "relative",
        width: "100%",
        minHeight: "400px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
        padding: "100px 32px 80px 32px",
        backgroundImage: "url('/images/final-cta-background.png')",
        backgroundSize: "cover",
        backgroundPosition: "center",
        backgroundRepeat: "no-repeat",
      }}
    >
      {/* ================================================================== */}
      {/* CONTENT LAYER - z-index: 10                                       */}
      {/* ================================================================== */}
      <div
        style={{
          position: "relative",
          zIndex: 10,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
          maxWidth: "1250px",
          width: "100%",
        }}
      >
        {/* ================================================================ */}
        {/* HEADLINE: 60px display typography, dominance verified           */}
        {/* Font: Inter, weight 700, line-height 1.15, letter-spacing -0.025em */}
        {/* Color: #FFFFFF (pure white) for WCAG AAA contrast               */}
        {/* ================================================================ */}
        <h1
          style={{
            fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            fontSize: "60px",
            fontWeight: 700,
            lineHeight: 1.15,
            letterSpacing: "-0.025em",
            color: "#FFFFFF",
            textAlign: "center",
            margin: "0 0 48px 0",
            padding: "0 32px",
            maxWidth: "1250px",
            WebkitFontSmoothing: "antialiased",
            MozOsxFontSmoothing: "grayscale",
          }}
        >
          Decision intelligence for smarter ad spend
        </h1>

        {/* ================================================================ */}
        {/* CTA BUTTONS: Side by side buttons                                */}
        {/* ================================================================ */}
        <div
          style={{
            display: "flex",
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "center",
            gap: "20px",
            flexWrap: "wrap",
          }}
        >
          <a
            href="/signup"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: "220px",
              height: "60px",
              padding: "0 32px",
              backgroundColor: "#FFFFFF",
              color: "#303ADA",
              fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
              fontSize: "16px",
              fontWeight: 700,
              textDecoration: "none",
              borderRadius: "50px",
              border: "none",
              boxShadow: "0 12px 40px rgba(0, 0, 0, 0.20)",
              cursor: "pointer",
              transition: "all 250ms cubic-bezier(0.4, 0, 0.2, 1)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = "translateY(-2px)";
              e.currentTarget.style.boxShadow = "0 16px 48px rgba(0, 0, 0, 0.28)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = "0 12px 40px rgba(0, 0, 0, 0.20)";
            }}
            onMouseDown={(e) => {
              e.currentTarget.style.transform = "translateY(0) scale(0.98)";
              e.currentTarget.style.boxShadow = "0 8px 32px rgba(0, 0, 0, 0.25)";
            }}
            onMouseUp={(e) => {
              e.currentTarget.style.transform = "translateY(-2px)";
              e.currentTarget.style.boxShadow = "0 16px 48px rgba(0, 0, 0, 0.28)";
            }}
            onFocus={(e) => {
              e.currentTarget.style.outline = "3px solid rgba(255, 255, 255, 0.60)";
              e.currentTarget.style.outlineOffset = "4px";
            }}
            onBlur={(e) => {
              e.currentTarget.style.outline = "none";
            }}
          >
            Get Started  $199/mo
          </a>
          <a
            href="/book-demo"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: "220px",
              height: "60px",
              padding: "0 32px",
              backgroundColor: "#FFFFFF",
              color: "#303ADA",
              fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
              fontSize: "16px",
              fontWeight: 700,
              textDecoration: "none",
              borderRadius: "50px",
              border: "none",
              boxShadow: "0 12px 40px rgba(0, 0, 0, 0.20)",
              cursor: "pointer",
              transition: "all 250ms cubic-bezier(0.4, 0, 0.2, 1)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = "translateY(-2px)";
              e.currentTarget.style.boxShadow = "0 16px 48px rgba(0, 0, 0, 0.28)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = "0 12px 40px rgba(0, 0, 0, 0.20)";
            }}
            onMouseDown={(e) => {
              e.currentTarget.style.transform = "translateY(0) scale(0.98)";
              e.currentTarget.style.boxShadow = "0 8px 32px rgba(0, 0, 0, 0.25)";
            }}
            onMouseUp={(e) => {
              e.currentTarget.style.transform = "translateY(-2px)";
              e.currentTarget.style.boxShadow = "0 16px 48px rgba(0, 0, 0, 0.28)";
            }}
            onFocus={(e) => {
              e.currentTarget.style.outline = "3px solid rgba(255, 255, 255, 0.60)";
              e.currentTarget.style.outlineOffset = "4px";
            }}
            onBlur={(e) => {
              e.currentTarget.style.outline = "none";
            }}
          >
            Get a demo
          </a>
        </div>
      </div>

      {/* ================================================================== */}
      {/* RESPONSIVE STYLES                                                 */}
      {/* Desktop (≥1440px): 60px headline, 470×101px button                */}
      {/* Tablet (768-1439px): 48px headline, 400×88px button               */}
      {/* Mobile (≤767px): 36px headline, fluid button (90vw max 340px)     */}
      {/* ================================================================== */}
      <style>{`
        /* TABLET (768px - 1439px) */
        @media (max-width: 1439px) and (min-width: 768px) {
          #final-cta {
            min-height: 350px !important;
            padding: 80px 24px 60px 24px !important;
          }

          #final-cta h1 {
            font-size: 48px !important;
            line-height: 1.2 !important;
            max-width: 900px !important;
            margin-bottom: 60px !important;
          }

          #final-cta > div > div {
            gap: 16px !important;
          }

          #final-cta a {
            width: 180px !important;
            height: 56px !important;
            font-size: 15px !important;
            padding: 0 24px !important;
          }
        }

        /* MOBILE (≤767px) */
        @media (max-width: 767px) {
          #final-cta {
            min-height: 320px !important;
            padding: 60px 20px 50px 20px !important;
          }

          #final-cta h1 {
            font-size: 32px !important;
            line-height: 1.3 !important;
            max-width: 100% !important;
            margin-bottom: 40px !important;
            letter-spacing: -0.02em !important;
            padding: 0 16px !important;
          }

          #final-cta > div > div {
            flex-direction: column !important;
            gap: 12px !important;
            width: 100% !important;
          }

          #final-cta a {
            width: 100% !important;
            max-width: 100% !important;
            min-height: 48px !important;
            height: 48px !important;
            font-size: 16px !important;
            padding: 0 24px !important;
          }
        }
      `}</style>
    </section>
  );
}
