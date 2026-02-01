"use client";

// ============================================================================
// SOLUTION OVERVIEW SECTION - REMEDIATION v2.0
// Fixes: F1-F7 as per Remediation Directive
// Reference: Solution_Overview_Section2.png
// ============================================================================

// Browser Window Chrome Component (F5 Fix)
function BrowserWindow({ children, title = "Skeldir" }: { children: React.ReactNode; title?: string }) {
  return (
    <div
      style={{
        backgroundColor: "#1F2937",
        borderRadius: "8px",
        overflow: "hidden",
        boxShadow: "0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.05)",
      }}
    >
      {/* Browser Header with Traffic Lights */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          padding: "10px 12px",
          backgroundColor: "#374151",
          borderRadius: "8px 8px 0 0",
          boxShadow: "0 2px 8px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.1)",
        }}
      >
        <div style={{ width: "10px", height: "10px", borderRadius: "50%", backgroundColor: "#EF4444" }} />
        <div style={{ width: "10px", height: "10px", borderRadius: "50%", backgroundColor: "#F59E0B" }} />
        <div style={{ width: "10px", height: "10px", borderRadius: "50%", backgroundColor: "#10B981" }} />
        <span
          style={{
            marginLeft: "8px",
            fontSize: "11px",
            color: "#9CA3AF",
            fontFamily: "Inter, sans-serif",
          }}
        >
          {title}
        </span>
      </div>
      {/* Content Area */}
          <div
            style={{
          backgroundColor: "#F3F4F6",
          boxShadow: "inset 0 2px 4px rgba(0,0,0,0.05)",
              }}
            >
        {children}
            </div>
          </div>
  );
}

// Card 1: Revenue Verification Visual (F2, F3, F5 Fixes)
function RevenueVerificationVisual() {
  return (
          <div
            style={{
        position: "relative",
        padding: "8px",
      }}
    >
      {/* Browser Window Screenshot */}
      <BrowserWindow title="Skeldir — Revenue Verification">
        {/* App Interface Mockup */}
        <div style={{ padding: "16px", minHeight: "180px" }}>
          {/* Sidebar + Content Layout */}
          <div style={{ display: "flex", gap: "12px" }}>
            {/* Mini Sidebar */}
            <div
              style={{
                width: "36px",
                backgroundColor: "#F3F4F6",
                borderRadius: "6px",
                padding: "8px 4px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <img 
                src="/images/skeldir-logo-black.png" 
                alt="Skeldir Logo" 
                style={{ width: "32px", height: "32px", objectFit: "contain" }} loading="lazy" decoding="async" />
              <div style={{ width: "16px", height: "16px", backgroundColor: "#E5E7EB", borderRadius: "3px" }} />
              <div style={{ width: "16px", height: "16px", backgroundColor: "#E5E7EB", borderRadius: "3px" }} />
        </div>

            {/* Main Content - Revenue Data Card */}
        <div
          style={{
            flex: 1,
                backgroundColor: "#FFFFFF",
              borderRadius: "8px",
                border: "1px solid #E5E7EB",
                padding: "14px",
                boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
            }}
          >
              {/* Header */}
            <div
              style={{
                  fontSize: "11px",
                fontWeight: 600,
                  color: "#374151",
                  marginBottom: "12px",
                fontFamily: "Inter, sans-serif",
              }}
            >
                Revenue Comparison
            </div>

              {/* Platform Claimed Row */}
            <div
              className="revenue-comparison-row revenue-comparison-row-platform-claimed"
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                  padding: "8px 0",
                  borderBottom: "1px solid #F3F4F6",
              }}
            >
                <span className="revenue-comparison-label" style={{ fontSize: "11px", color: "#6B7280", fontFamily: "Inter, sans-serif" }}>
                Platform Claimed
              </span>
                <span style={{ fontSize: "16px", fontWeight: 700, color: "#111827", fontFamily: "Inter, sans-serif" }}>
                $52,300
              </span>
            </div>

              {/* Verified Revenue Row */}
            <div
              className="revenue-comparison-row"
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                  padding: "8px 0",
                  borderBottom: "1px solid #F3F4F6",
              }}
            >
                <span className="revenue-comparison-label" style={{ fontSize: "11px", color: "#6B7280", fontFamily: "Inter, sans-serif" }}>
                Verified Revenue
              </span>
                <span style={{ fontSize: "16px", fontWeight: 700, color: "#10B981", fontFamily: "Inter, sans-serif" }}>
                $43,800
              </span>
            </div>

              {/* Discrepancy Row */}
            <div
              style={{
                textAlign: "center",
                  padding: "10px 0 4px 0",
              }}
            >
                <span style={{ fontSize: "12px", fontWeight: 600, color: "#EF4444", fontFamily: "Inter, sans-serif" }}>
                Discrepancy: -$8,500 (-16%)
              </span>
              </div>
            </div>
          </div>
        </div>
      </BrowserWindow>

      {/* Arrow Annotation: "What Facebook Claims" - EXTERNAL, positioned in padding (F3 Fix) */}
      <div
        className="revenue-verification-annotation"
        style={{
          position: "absolute",
          left: "-70px",
          top: "115px",
          display: "flex",
          alignItems: "center",
          zIndex: 20,
        }}
      >
        <div
          style={{
            backgroundColor: "#EF4444",
            borderRadius: "4px",
            padding: "4px 8px",
            fontSize: "9px",
            fontWeight: 600,
            color: "#FFFFFF",
            fontFamily: "Inter, sans-serif",
            whiteSpace: "nowrap",
            boxShadow: "0 1px 3px rgba(0,0,0,0.15)",
          }}
        >
          What Meta Ads Claims
        </div>
        <svg width="28" height="12" style={{ marginLeft: "2px" }}>
          <line x1="0" y1="6" x2="20" y2="6" stroke="#EF4444" strokeWidth="2" />
          <polygon points="18,2 26,6 18,10" fill="#EF4444" />
        </svg>
      </div>

      {/* Arrow Annotation: "What Stripe Verifies" - EXTERNAL, positioned in padding (F3 Fix) */}
      <div
        className="revenue-verification-annotation"
        style={{
          position: "absolute",
          left: "-70px",
          top: "155px",
          display: "flex",
          alignItems: "center",
          zIndex: 20,
        }}
      >
        <div
          style={{
            backgroundColor: "#10B981",
            borderRadius: "4px",
            padding: "4px 8px",
            fontSize: "9px",
            fontWeight: 600,
            color: "#FFFFFF",
            fontFamily: "Inter, sans-serif",
            whiteSpace: "nowrap",
            boxShadow: "0 1px 3px rgba(0,0,0,0.15)",
          }}
        >
          What Stripe Verifies
        </div>
        <svg width="28" height="12" style={{ marginLeft: "2px" }}>
          <line x1="0" y1="6" x2="20" y2="6" stroke="#10B981" strokeWidth="2" />
          <polygon points="18,2 26,6 18,10" fill="#10B981" />
        </svg>
      </div>

      {/* "Exposes Over-Reporting" Callout - BELOW screenshot as chip (F2 Fix) */}
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          backgroundColor: "#FFFFFF",
          border: "1px solid #FCA5A5",
          borderRadius: "6px",
          padding: "6px 12px",
          fontSize: "11px",
          fontWeight: 600,
          color: "#DC2626",
          fontFamily: "Inter, sans-serif",
          boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
          marginTop: "12px",
        }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#DC2626" strokeWidth="2">
          <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        Exposes Over-Reporting
      </div>
    </div>
  );
}

// Card 2: Confidence Ranges Visual (F4, F5 Fixes)
function ConfidenceRangesVisual() {
  return (
    <div
      style={{
        position: "relative",
        padding: "8px", // Match first card padding
      }}
    >
      {/* Annotation: "Bayesian Range—Not Single Guess" - ABOVE screenshot (F4 Fix) */}
      <div
        style={{
          position: "absolute",
          top: "-8px",
          left: "50%",
          transform: "translateX(-50%)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          zIndex: 20,
        }}
      >
        <div
          style={{
            backgroundColor: "#1F2937",
            borderRadius: "6px",
            padding: "6px 12px",
            fontSize: "10px",
            fontWeight: 600,
            color: "#FFFFFF",
            fontFamily: "Inter, sans-serif",
            whiteSpace: "nowrap",
            boxShadow: "0 2px 4px rgba(0,0,0,0.15)",
          }}
        >
          Bayesian Range—Not Single Guess
        </div>
        <svg width="12" height="8" style={{ marginTop: "-1px" }}>
          <polygon points="6,8 0,0 12,0" fill="#1F2937" />
        </svg>
      </div>

      {/* Browser Window Screenshot */}
      <BrowserWindow title="Skeldir — Channel Comparison">
        <div style={{ padding: "20px", minHeight: "240px" }}>
          {/* Header */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              marginBottom: "20px",
              paddingBottom: "14px",
              borderBottom: "1px solid #E5E7EB",
            }}
          >
            <span style={{ fontSize: "16px", fontWeight: 600, color: "#111827", fontFamily: "Inter, sans-serif" }}>
            Channel Comparison
          </span>
            <div style={{ display: "flex", gap: "8px" }}>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 500,
                  color: "#10B981",
                  backgroundColor: "#D1FAE5",
                  padding: "4px 8px",
                  borderRadius: "4px",
                  fontFamily: "Inter, sans-serif",
                  whiteSpace: "nowrap",
                }}
              >
                High Confidence
              </span>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 500,
                  color: "#F59E0B",
                  backgroundColor: "#FEF3C7",
                  padding: "4px 8px",
                  borderRadius: "4px",
                  fontFamily: "Inter, sans-serif",
                  whiteSpace: "nowrap",
                }}
              >
                Medium Confidence
              </span>
            </div>
        </div>

          {/* Channel Rows */}
          <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
            {/* Meta Ads ROAS */}
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <img 
                src="/images/meta-ads-logo-vector.png" 
                alt="Meta" 
                style={{ 
                  width: "32px", 
                  height: "32px", 
                  objectFit: "contain",
                  display: "block",
                  flexShrink: 0
                }} loading="lazy" decoding="async" />
              <span style={{ width: "90px", fontSize: "13px", color: "#374151", fontFamily: "Inter, sans-serif", fontWeight: 500, whiteSpace: "nowrap", marginRight: "4px" }}>
                Meta Ads ROAS
              </span>
              <div style={{ flex: 1, position: "relative", height: "12px", backgroundColor: "#E5E7EB", borderRadius: "4px" }}>
                <div
                  style={{
                    position: "absolute",
                    left: "40%",
                    width: "20%",
                    height: "100%",
                    backgroundColor: "#10B981",
                    borderRadius: "4px",
                  }}
                />
              </div>
            </div>

            {/* Google ROAS */}
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <img 
                src="/images/google-ads-icon.webp" 
                alt="Google Ads" 
                style={{ 
                  width: "32px", 
                  height: "32px", 
                  objectFit: "contain",
                  display: "block",
                  flexShrink: 0
                }} loading="lazy" decoding="async" />
              <span style={{ width: "90px", fontSize: "13px", color: "#374151", fontFamily: "Inter, sans-serif", fontWeight: 500 }}>
                Google ROAS
              </span>
              <div style={{ flex: 1, position: "relative", height: "12px", backgroundColor: "#E5E7EB", borderRadius: "4px" }}>
                <div
                  style={{
                    position: "absolute",
                    left: "25%",
                    width: "45%",
                    height: "100%",
                    backgroundColor: "#F59E0B",
                    borderRadius: "4px",
                  }}
                />
              </div>
            </div>

            {/* TikTok ROAS */}
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  backgroundColor: "#000000",
                  borderRadius: "4px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  overflow: "hidden",
                }}
              >
                <img 
                  src="/images/tiktok-icon.png" 
                  alt="TikTok" 
                  style={{ 
                    width: "100%", 
                    height: "100%", 
                    objectFit: "contain",
                    display: "block"
                  }} loading="lazy" decoding="async" />
              </div>
              <span style={{ width: "90px", fontSize: "13px", color: "#374151", fontFamily: "Inter, sans-serif", fontWeight: 500 }}>
                TikTok ROAS
              </span>
              <div style={{ flex: 1, position: "relative", height: "12px", backgroundColor: "#E5E7EB", borderRadius: "4px" }}>
                <div
                  style={{
                    position: "absolute",
                    left: "10%",
                    width: "60%",
                    height: "100%",
                    backgroundColor: "#F59E0B",
                    borderRadius: "4px",
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      </BrowserWindow>

      {/* Annotation: "Narrow Range = Act Now" - RIGHT MARGIN (F4 Fix) */}
        <div
          style={{
            position: "absolute",
            right: "-8px",
          top: "135px",
            display: "flex",
          alignItems: "center",
          zIndex: 20,
          }}
        >
        <div
          style={{
            backgroundColor: "#D1FAE5",
            border: "1px solid #10B981",
            borderRadius: "4px",
            padding: "4px 8px",
              fontSize: "9px",
              fontWeight: 600,
            color: "#10B981",
              fontFamily: "Inter, sans-serif",
              whiteSpace: "nowrap",
            boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
            }}
          >
            Narrow Range = Act Now
          </div>
        </div>

      {/* Annotation: "Wide Range = Need More Data" - RIGHT MARGIN (F4 Fix) */}
        <div
          style={{
            position: "absolute",
          right: "-8px",
          top: "240px",
            display: "flex",
            alignItems: "center",
          zIndex: 20,
          }}
        >
          <div
            style={{
            backgroundColor: "#FEF3C7",
            border: "1px solid #F59E0B",
            borderRadius: "4px",
            padding: "4px 8px",
              fontSize: "9px",
              fontWeight: 600,
            color: "#000000",
              fontFamily: "Inter, sans-serif",
              whiteSpace: "nowrap",
            boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
            }}
          >
            Wide Range = Need More Data
        </div>
      </div>
    </div>
  );
}

// Card 3: 48-Hour Deployment Timeline (F7 Fix - Updated text content)
function DeploymentTimelineVisual() {
  const milestones = [
    {
      hour: "Hour 0-4: Account Setup",
      description: "Connect Stripe, Platforms",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
        </svg>
      ),
    },
    {
      hour: "Hour 4-24: Historical Data Pull",
      description: "90-Day Import",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" />
          <line x1="12" y1="15" x2="12" y2="3" />
        </svg>
      ),
    },
    {
      hour: "Hour 24-48: First Attribution Report",
      description: "Live Dashboard",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="20" x2="18" y2="10" />
          <line x1="12" y1="20" x2="12" y2="4" />
          <line x1="6" y1="20" x2="6" y2="14" />
        </svg>
      ),
    },
  ];

  return (
    <div
      style={{
        position: "relative",
        background: "linear-gradient(180deg, rgba(59,130,246,0.05) 0%, rgba(59,130,246,0.02) 100%)",
        borderRadius: "12px",
        padding: "24px",
        minHeight: "240px",
      }}
    >
      {/* Vertical Dashed Timeline Line */}
      <div
        style={{
          position: "absolute",
          left: "44px",
          top: "48px",
          bottom: "48px",
          width: "2px",
          backgroundImage: "repeating-linear-gradient(to bottom, #3B82F6 0, #3B82F6 8px, transparent 8px, transparent 16px)",
        }}
      />

      {/* Milestones */}
      <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
        {milestones.map((milestone, index) => (
          <div
            key={index}
          style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "16px",
              marginBottom: index < milestones.length - 1 ? "32px" : "0",
          }}
          >
            {/* Icon with Checkmark Badge */}
            <div style={{ position: "relative", flexShrink: 0 }}>
              <div
                style={{
                  width: "40px",
                  height: "40px",
                  borderRadius: "50%",
                  backgroundColor: "#FFFFFF",
                  border: "2px solid #E5E7EB",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
                  zIndex: 2,
                  position: "relative",
                }}
              >
                {milestone.icon}
              </div>
              {/* Green Checkmark Badge */}
              <div
                style={{
                  position: "absolute",
                  top: "-10px",
                  right: "-4px",
                  width: "18px",
                  height: "18px",
                  borderRadius: "50%",
                  backgroundColor: "#10B981",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 1px 2px rgba(0,0,0,0.1)",
                }}
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              </div>

            {/* Text Labels */}
            <div style={{ paddingTop: "4px" }}>
              <div
                style={{
                  fontSize: "14px",
                  fontWeight: 600,
                  color: "#111827",
                  fontFamily: "Inter, sans-serif",
                  marginBottom: "2px",
                }}
              >
                {milestone.hour}
              </div>
              <div
                style={{
                  fontSize: "13px",
                  fontWeight: 400,
                  color: "#6B7280",
                  fontFamily: "Inter, sans-serif",
                }}
              >
                {milestone.description}
              </div>
              </div>
            </div>
          ))}
      </div>
    </div>
  );
}

// Solution Card Component (F1 Fix - Decorative numbers visible)
interface SolutionCardProps {
  number: string;
  visual: React.ReactNode;
  headline: string;
  description: string;
}

function SolutionCard({ number, visual, headline, description }: SolutionCardProps) {
  return (
    <div
      className="solution-card"
      style={{
        backgroundColor: "#FFFFFF",
        borderRadius: "16px",
        padding: "120px 32px 32px 32px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.04)",
        border: "1px solid rgba(0,0,0,0.04)",
        position: "relative",
        overflow: "visible", // F1 FIX: Changed from hidden to visible
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Decorative Number (F1 FIX: Increased opacity, proper z-index) */}
      <span
        style={{
          position: "absolute",
          top: "6.6px",
          right: "12px",
          fontFamily: "Inter, sans-serif",
          fontSize: "120px",
          fontWeight: 700,
          color: "rgba(148, 163, 184, 0.15)", // Increased opacity for better visibility
          lineHeight: 1,
          zIndex: 1, // F1 FIX: Above background (0), below content (10+)
          pointerEvents: "none",
          userSelect: "none",
        }}
      >
        {number}
      </span>

      {/* Visual Content */}
      <div style={{ position: "relative", zIndex: 10, marginBottom: "20px" }}>{visual}</div>

      {/* Headline */}
      <h3
        style={{
          fontFamily: "Inter, sans-serif",
          fontSize: "20px",
          fontWeight: 600,
          lineHeight: 1.3,
          color: "#111827",
          marginBottom: "8px",
          marginTop: 0,
          position: "relative",
          zIndex: 10,
        }}
      >
        {headline}
      </h3>

      {/* Description */}
      <p
        style={{
          fontFamily: "Inter, sans-serif",
          fontSize: "15px",
          fontWeight: 400,
          lineHeight: 1.6,
          color: "#6B7280",
          margin: 0,
          position: "relative",
          zIndex: 10,
        }}
      >
        {description}
      </p>
    </div>
  );
}

// Main Section Export
export function SolutionOverview() {
  const solutions = [
    {
      number: "01",
      visual: <RevenueVerificationVisual />,
      headline: "Revenue Verification",
      description: "Platform-claimed revenue vs. verified Stripe/PayPal webhooks. Expose 16-40% over-reporting.",
    },
    {
      number: "02",
      visual: <ConfidenceRangesVisual />,
      headline: "Confidence Ranges",
      description: "See exactly how certain the model is. Narrow ranges mean act, wide ranges mean wait for more data.",
    },
    {
      number: "03",
      visual: <DeploymentTimelineVisual />,
      headline: "48-Hour Deployment",
      description: "No engineering required. No 6-month implementations. Live insights in 2 days vs. competitors' 3-6 months.",
    },
  ];

  return (
    <section
      className="solution-overview-section"
      style={{
        backgroundColor: "#E9ECEF",
        padding: "80px 0",
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
          background: "linear-gradient(to bottom, rgba(255, 255, 255, 1) 0%, rgba(255, 255, 255, 0.8) 20%, rgba(233, 236, 239, 0.6) 50%, rgba(233, 236, 239, 1) 100%)",
          pointerEvents: "none",
          zIndex: 1,
        }}
      />
      {/* CSS for responsive grid */}
      <style>
        {`
          .solution-overview__inner {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 48px;
          }
          .solution-overview__grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 40px;
          }
          @media (max-width: 1024px) {
            .solution-overview__grid {
              grid-template-columns: repeat(2, 1fr);
              gap: 24px;
            }
            .solution-overview__inner {
              padding: 0 32px;
            }
          }
          @media (max-width: 767px) {
            .solution-overview-section {
              padding: 48px 0 !important;
            }

            .solution-overview__grid {
              grid-template-columns: 1fr !important;
              gap: 32px !important;
            }
            .solution-overview__inner {
              padding: 0 20px !important;
            }

            .solution-overview-title {
              font-size: 32px !important;
              line-height: 1.25 !important;
              margin-bottom: 40px !important;
              padding: 0 16px !important;
            }

            .solution-card {
              padding: 80px 24px 24px 24px !important;
            }

            .solution-card h3 {
              font-size: 18px !important;
              line-height: 1.3 !important;
            }

            .solution-card p {
              font-size: 15px !important;
              line-height: 1.6 !important;
            }

            /* Hide external annotations on mobile (except Revenue Verification annotations) */
            .solution-card [style*="position: absolute"][style*="left: -"]:not(.revenue-verification-annotation) {
              display: none !important;
            }

            .solution-card [style*="position: absolute"][style*="right: -"] {
              display: none !important;
            }

            /* Revenue Verification card: position badges/SVGs on mobile (50px left of previous) */
            .solution-card .revenue-verification-annotation {
              left: -42px !important;
            }

            /* Revenue Comparison: nudge "Platform Claimed" / "Verified Revenue" labels slightly right on mobile */
            .solution-card .revenue-comparison-label {
              margin-left: 8px !important;
            }
            /* "Platform Claimed" label: 0.4x right of Verified Revenue alignment on mobile */
            .solution-card .revenue-comparison-row-platform-claimed .revenue-comparison-label {
              margin-left: 11px !important;
            }
          }
        `}
      </style>

      <div className="solution-overview__inner" style={{ position: "relative", zIndex: 2 }}>
        {/* Section Title (F6 FIX: Correct font, weight, tracking) */}
        <h2
          className="solution-overview-title"
          style={{
            fontFamily: "'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            fontSize: "44px",
            fontWeight: 700,
            lineHeight: 1.2,
            letterSpacing: "-0.025em", // F6 FIX: Tighter tracking
            color: "#111827",
            textAlign: "center",
            marginTop: 0,
            marginBottom: "56px",
          }}
        >
          How Skeldir Solves It
        </h2>

        {/* 3-Column Card Grid */}
        <div className="solution-overview__grid">
          {solutions.map((solution, index) => (
            <SolutionCard
              key={index}
              number={solution.number}
              visual={solution.visual}
              headline={solution.headline}
              description={solution.description}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
