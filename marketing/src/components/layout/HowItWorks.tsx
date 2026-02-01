"use client";

// ============================================================================
// HOW IT WORKS TIMELINE SECTION
// Reference: HIW-TIMELINE-001 Directive v1.1 (CORRECTED)
// Pixel-Perfect Implementation per Forensic Specifications
// ============================================================================

// =============================================================================
// PLATFORM LOGO COMPONENTS - VERIFIED AUTHENTIC BRAND MARKS
// =============================================================================

// Stripe wordmark logo - grayscale
function StripeLogo() {
  return (
    <img
      src="/images/stripe-logo.png"
      alt="Stripe"
      loading="lazy"
      decoding="async"
      style={{
        width: "50px",
        height: "21px",
        objectFit: "contain",
        display: "block",
        margin: 0,
        padding: 0,
        lineHeight: 0,
        flexShrink: 0
      }}
    />
  );
}

// Shopify logo with shopping bag icon + wordmark
function ShopifyLogo() {
  return (
    <img 
      src="/images/shopify-logo.webp" 
      alt="Shopify" 
      style={{ 
        height: "64.6px", 
        width: "auto",
        objectFit: "contain",
        display: "block",
        margin: 0,
        padding: 0,
        lineHeight: 0,
        flexShrink: 0
      }} loading="lazy" decoding="async" />
  );
}

// Google Ads logo - COLORED TRIANGLE icon (NOT Google "G")
function GoogleAdsLogo() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
      {/* Google Ads icon */}
      <img 
        src="/images/google-ads-icon.webp" 
        alt="Google Ads" 
        style={{ 
          width: "18px", 
          height: "18px", 
          objectFit: "contain",
          display: "block",
          margin: 0,
          padding: 0,
          lineHeight: 0,
          flexShrink: 0
        }} loading="lazy" decoding="async" />
      <span style={{
        fontFamily: "Inter, system-ui, sans-serif",
        fontSize: "13px",
        fontWeight: 500,
        color: "#5F6368",
        letterSpacing: "-0.01em"
      }}>
        Google Ads
      </span>
    </div>
  );
}

// Meta logo - INFINITY LOOP icon (NOT Facebook "f")
function MetaLogo() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
      {/* Meta logo icon */}
      <img 
        src="/images/meta-ads-logo-vector.png" 
        alt="Meta" 
        style={{ 
          width: "24px", 
          height: "16px", 
          objectFit: "contain",
          display: "block",
          margin: 0,
          padding: 0,
          lineHeight: 0,
          flexShrink: 0
        }} loading="lazy" decoding="async" />
      <span style={{
        fontFamily: "Inter, system-ui, sans-serif",
        fontSize: "13px",
        fontWeight: 500,
        color: "#0668E1",
      }}>
        Meta
      </span>
    </div>
  );
}

// TikTok Ads logo - SINGLE LINE layout (NOT stacked)
function TikTokAdsLogo() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
      {/* TikTok musical note icon */}
      <svg width="14" height="16" viewBox="0 0 16 18" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path
          d="M11.5 0H9V12.3C9 13.8 7.8 15 6.3 15C4.8 15 3.6 13.8 3.6 12.3C3.6 10.8 4.8 9.7 6.2 9.6V6.6C3.1 6.7 0.6 9.2 0.6 12.3C0.6 15.5 3.1 18 6.3 18C9.5 18 12 15.5 12 12.3V5.7C13 6.5 14.3 7 15.7 7V4C13.4 3.9 11.5 2.2 11.5 0Z"
          fill="#000000"
        />
        {/* TikTok color accent */}
        <path
          d="M11.5 0H9V12.3C9 13.8 7.8 15 6.3 15C4.8 15 3.6 13.8 3.6 12.3C3.6 10.8 4.8 9.7 6.2 9.6V6.6C3.1 6.7 0.6 9.2 0.6 12.3C0.6 15.5 3.1 18 6.3 18C9.5 18 12 15.5 12 12.3V5.7C13 6.5 14.3 7 15.7 7V4C13.4 3.9 11.5 2.2 11.5 0Z"
          fill="url(#tiktok-gradient)"
        />
        <defs>
          <linearGradient id="tiktok-gradient" x1="0" y1="0" x2="16" y2="18" gradientUnits="userSpaceOnUse">
            <stop stopColor="#25F4EE" stopOpacity="0.3"/>
            <stop offset="1" stopColor="#FE2C55" stopOpacity="0.3"/>
          </linearGradient>
        </defs>
      </svg>
      <span style={{
        fontFamily: "Inter, system-ui, sans-serif",
        fontSize: "13px",
        fontWeight: 600,
        color: "#000000",
        letterSpacing: "-0.01em",
        whiteSpace: "nowrap",
      }}>
        TikTok Ads
      </span>
    </div>
  );
}

// =============================================================================
// DASHBOARD PREVIEW - PROFESSIONAL QUALITY (per directive v1.1)
// Contains: Sidebar, KPI cards, Line chart with area fill, Table hints
// =============================================================================
function DashboardPreview() {
  return (
    <svg width="80" height="48" viewBox="0 0 80 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Container with shadow */}
      <rect x="0.5" y="0.5" width="79" height="47" rx="5.5" fill="white" stroke="#E5E7EB"/>

      {/* Sidebar */}
      <rect x="1" y="1" width="12" height="46" rx="5" fill="#F3F4F6"/>
      {/* Sidebar nav icons */}
      <rect x="4" y="6" width="6" height="4" rx="1" fill="#D1D5DB"/>
      <rect x="4" y="13" width="6" height="4" rx="1" fill="#D1D5DB"/>
      <rect x="4" y="20" width="6" height="4" rx="1" fill="#9CA3AF"/>

      {/* KPI Card 1 - White with border */}
      <rect x="16" y="4" width="20" height="12" rx="2" fill="white" stroke="#E5E7EB" strokeWidth="0.5"/>
      <rect x="18" y="6" width="10" height="2" rx="0.5" fill="#9CA3AF"/>
      <rect x="18" y="10" width="14" height="3" rx="0.5" fill="#374151"/>

      {/* KPI Card 2 - Green accent */}
      <rect x="40" y="4" width="20" height="12" rx="2" fill="#F0FDF4" stroke="#10B981" strokeWidth="0.5"/>
      <rect x="42" y="6" width="10" height="2" rx="0.5" fill="#6EE7B7"/>
      <rect x="42" y="10" width="14" height="3" rx="0.5" fill="#10B981"/>

      {/* Chart Area Fill */}
      <path
        d="M 18 38 L 26 32 L 34 35 L 44 26 L 54 30 L 66 22 L 66 42 L 18 42 Z"
        fill="#2563EB"
        fillOpacity="0.1"
      />

      {/* Chart Line */}
      <path
        d="M 18 38 L 26 32 L 34 35 L 44 26 L 54 30 L 66 22"
        stroke="#2563EB"
        strokeWidth="1.5"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Chart dots */}
      <circle cx="18" cy="38" r="1.5" fill="#2563EB"/>
      <circle cx="44" cy="26" r="1.5" fill="#2563EB"/>
      <circle cx="66" cy="22" r="1.5" fill="#2563EB"/>

      {/* Table row hints */}
      <line x1="16" y1="44" x2="50" y2="44" stroke="#E5E7EB" strokeWidth="0.75"/>
      <line x1="16" y1="46" x2="40" y2="46" stroke="#E5E7EB" strokeWidth="0.75"/>
    </svg>
  );
}

// =============================================================================
// CHECKMARK ICON
// =============================================================================
function CheckIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#10B981"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

// =============================================================================
// STEP DATA
// =============================================================================
const steps = [
  {
    id: 1,
    badge: "Hour 0-4",
    headline: "Connect Your Stack",
    description:
      "Link Stripe/PayPal for revenue verification and ad platforms for campaign data. OAuth takes 2 minutes per platform.",
    logos: ["stripe", "shopify"],
    hasPreview: false,
  },
  {
    id: 2,
    badge: "Hour 4-24",
    headline: "Import Historical Data",
    description:
      "Automatic 90-day historical pull from all connected platforms. No CSV uploads, no manual entry. Processing happens in the background.",
    logos: ["google-ads", "meta", "tiktok"],
    hasPreview: false,
  },
  {
    id: 3,
    badge: "Hour 24-48",
    headline: "Launch Live Dashboard",
    description:
      "Your first attribution report is ready. Review confidence ranges, verify revenue discrepancies, and approve budget recommendations.",
    logos: [],
    hasPreview: true,
  },
];

// =============================================================================
// PLATFORM LOGO RENDERER
// =============================================================================
function PlatformLogo({ name }: { name: string }) {
  switch (name) {
    case "stripe":
      return <StripeLogo />;
    case "shopify":
      return <ShopifyLogo />;
    case "google-ads":
      return <GoogleAdsLogo />;
    case "meta":
      return <MetaLogo />;
    case "tiktok":
      return <TikTokAdsLogo />;
    default:
      return null;
  }
}

// =============================================================================
// TIMELINE STEP COMPONENT
// =============================================================================
function TimelineStep({
  step,
  showLeftLabel,
}: {
  step: (typeof steps)[0];
  showLeftLabel: boolean;
}) {
  return (
    <div
      className="timeline-step-row"
      style={{
        display: "flex",
        alignItems: "flex-start",
        position: "relative",
      }}
    >
      {/* Left time label column (only shows text for step 3) */}
      <div
        style={{
          width: "80px",
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-end",
          paddingRight: "16px",
          height: "24px", // Aligns with node vertical center
        }}
      >
      </div>

      {/* Node - SOLID CIRCLE, NO BORDER/SHADOW/OUTLINE per directive v1.1 */}
      <div
        className="timeline-node"
        style={{
          width: "20px",
          height: "20px",
          borderRadius: "50%",
          backgroundColor: "#2563EB",
          border: "none",
          boxShadow: "none",
          outline: "none",
          opacity: 1,
          flexShrink: 0,
          position: "relative",
          zIndex: 2,
          marginTop: "4px",
        }}
      />

      {/* Gap between node and card: 32px */}
      <div style={{ width: "32px", flexShrink: 0 }} />

      {/* For all steps, render image instead of card */}
      {step.id === 1 ? (
        <img 
          src="/images/timeline-1.png" 
          alt={step.headline}
          style={{
            width: "420px",
            height: "auto",
            objectFit: "contain",
            display: "block",
            flexShrink: 0,
          }} loading="lazy" decoding="async" />
      ) : step.id === 2 ? (
        <img 
          src="/images/timeline-2.png" 
          alt={step.headline}
          style={{
            width: "420px",
            height: "auto",
            objectFit: "contain",
            display: "block",
            flexShrink: 0,
          }} loading="lazy" decoding="async" />
      ) : step.id === 3 ? (
        <img 
          src="/images/timeline-3.png" 
          alt={step.headline}
          style={{
            width: "420px",
            height: "auto",
            objectFit: "contain",
            display: "block",
            flexShrink: 0,
          }} loading="lazy" decoding="async" />
      ) : (
        /* Card - 400px width per directive */
        <div
          style={{
            backgroundColor: "#FFFFFF",
            border: "1px solid #E5E7EB",
            borderRadius: "12px",
            boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
            padding: "24px",
            width: "400px",
            position: "relative",
          }}
        >
          {/* Time Badge - top-right */}
          <span
            style={{
              position: "absolute",
              top: "24px",
              right: "24px",
              backgroundColor: "#F0FDF4",
              color: "#166534",
              fontFamily: "Inter, system-ui, sans-serif",
              fontSize: "12px",
              fontWeight: 500,
              padding: "4px 8px",
              borderRadius: "4px",
            }}
          >
            {step.badge}
          </span>

          {/* Headline */}
          <h3
            style={{
              fontFamily: "Inter, system-ui, sans-serif",
              fontSize: "18px",
              fontWeight: 600,
              lineHeight: 1.4,
              color: "#212529",
              margin: "0 0 8px 0",
            }}
          >
            {step.headline}
          </h3>

          {/* Description */}
          <p
            style={{
              fontFamily: "Inter, system-ui, sans-serif",
              fontSize: "14px",
              fontWeight: 400,
              lineHeight: 1.5,
              color: "#6C757D",
              margin: "0 0 16px 0",
            }}
          >
            {step.description}
          </p>

          {/* Logos or Preview + Checkmark */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "2px",
              }}
            >
              {step.logos.length > 0 &&
                step.logos.map((logo) => <PlatformLogo key={logo} name={logo} />)}
              {step.hasPreview && <DashboardPreview />}
            </div>

            {/* Completion Checkmark - bottom-right */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              <CheckIcon />
              <span
                style={{
                  fontFamily: "Inter, system-ui, sans-serif",
                  fontSize: "14px",
                  fontWeight: 500,
                  color: "#10B981",
                }}
              >
                Completed
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// MAIN SECTION EXPORT
// =============================================================================
export function HowItWorks() {
  // Card height estimate for line positioning
  // Each card is ~150px, gap is 32px, node is at marginTop 4px from card top
  // Line should connect node centers exactly (no excess above/below)

  return (
    <section
      className="how-it-works-section"
      style={{
        backgroundColor: "#FFFFFF",
        paddingTop: "64px",
        paddingBottom: "64px",
        paddingLeft: "24px",
        paddingRight: "24px",
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
          background: "linear-gradient(to bottom, rgba(248, 250, 252, 1) 0%, rgba(248, 250, 252, 0.8) 20%, rgba(255, 255, 255, 0.6) 50%, rgba(255, 255, 255, 1) 100%)",
          pointerEvents: "none",
          zIndex: 1,
        }}
      />
      <div
        style={{
          maxWidth: "750px",
          margin: "0 auto",
          position: "relative",
          zIndex: 2,
        }}
      >
        {/* Section Title */}
        <h2
          className="how-it-works-title"
          style={{
            fontFamily: "'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            fontSize: "44px",
            fontWeight: 700,
            lineHeight: 1.2,
            letterSpacing: "-0.025em",
            color: "#111827",
            textAlign: "center",
            marginTop: 0,
            marginBottom: "56px",
          }}
        >
          How It Works
        </h2>

        {/* Timeline Container */}
        <div className="timeline-container" style={{ position: "relative", paddingLeft: "0px", display: "flex", justifyContent: "center", width: "100%", overflow: "hidden" }}>
          {/* Timeline Line Segments - Connect at node centers for seamless appearance */}
          {/*
            Position calculation:
            - Nodes are 20px tall with 4px marginTop
            - First node: top at 4px, center at 14px, bottom at 24px
            - Images are ~240px tall, gap between steps is 32px
            - Second node: top at 276px, center at 286px, bottom at 296px
            - Third node: top at 548px, center at 558px, bottom at 568px
            - Segments connect at node centers so they appear continuous
          */}
          {/* Segment 1: From first node center (14px) to second node center (286px) */}
          <div
            className="timeline-segment timeline-segment-1"
            style={{
              position: "absolute",
              left: "calc(50% - 187.5px)",
              top: "14px", // First node center
              height: "272px", // To second node center (286px - 14px = 272px)
              width: "3px",
              backgroundColor: "#2563EB",
              zIndex: 1,
            }}
          />
          {/* Segment 2: From second node center (286px) to third node center (558px) */}
          <div
            className="timeline-segment timeline-segment-2"
            style={{
              position: "absolute",
              left: "calc(50% - 187.5px)",
              top: "286px", // Second node center
              height: "272px", // To third node center (558px - 286px = 272px)
              width: "3px",
              backgroundColor: "#2563EB",
              zIndex: 1,
            }}
          />
          {/* Segment 3: From third node center (558px) to bottom node center */}
          <div
            className="timeline-segment timeline-segment-3"
            style={{
              position: "absolute",
              left: "calc(50% - 187.5px)",
              top: "558px", // Third node center
              bottom: "12px", // To bottom (will calculate to bottom node center)
              width: "3px",
              backgroundColor: "#2563EB",
              zIndex: 1,
            }}
          />

          {/* Steps - 32px gap between cards */}
          <div
            className="timeline-steps-wrapper"
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "32px",
              alignItems: "center",
            }}
          >
            {steps.map((step, index) => (
              <TimelineStep
                key={step.id}
                step={step}
                showLeftLabel={index === 2}
              />
            ))}
          </div>

          {/* Bottom Timeline Node */}
          <div
            className="timeline-bottom-node"
            style={{
              position: "absolute",
              left: "calc(50% - 196px)",
              bottom: "12px",
              width: "20px",
              height: "20px",
              borderRadius: "50%",
              backgroundColor: "#2563EB",
              border: "none",
              boxShadow: "none",
              outline: "none",
              opacity: 1,
              flexShrink: 0,
              zIndex: 2,
            }}
          />
        </div>
      </div>

      <style>{`
        @media (max-width: 767px) {
          .how-it-works-section {
            padding-top: 48px !important;
            padding-bottom: 48px !important;
            padding-left: 20px !important;
            padding-right: 20px !important;
            overflow-x: hidden !important;
          }

          .how-it-works-title {
            font-size: 32px !important;
            line-height: 1.25 !important;
            margin-bottom: 40px !important;
            padding: 0 8px !important;
          }

          .timeline-container {
            padding-left: 0 !important;
            padding-right: 0 !important;
            overflow: visible !important;
            justify-content: flex-start !important;
            align-items: flex-start !important;
            margin-left: -32px !important;
            width: calc(100% + 32px) !important;
          }

          .timeline-container .timeline-steps-wrapper {
            align-items: flex-start !important;
            width: 100% !important;
            max-width: 100% !important;
          }

          .timeline-segment,
          .timeline-segment-1,
          .timeline-segment-2,
          .timeline-segment-3 {
            display: none !important;
          }

          .timeline-bottom-node {
            display: none !important;
          }

          .timeline-node {
            display: none !important;
          }

          .how-it-works-section img {
            width: 100% !important;
            max-width: 100% !important;
            height: auto !important;
          }

          .how-it-works-section [style*="width: 420px"] {
            width: 100% !important;
            max-width: 100% !important;
          }

          /* Fix timeline step layout on mobile — shift content left so it is not cut off */
          .how-it-works-section .timeline-step-row {
            flex-direction: column !important;
            align-items: flex-start !important;
            width: 100% !important;
            max-width: 100% !important;
            padding-left: 24px !important;
            box-sizing: border-box !important;
          }

          .how-it-works-section .timeline-step-row [style*="width: 80px"] {
            display: none !important;
          }

          .how-it-works-section .timeline-step-row [style*="width: 32px"] {
            display: none !important;
          }
        }
      `}</style>
    </section>
  );
}
