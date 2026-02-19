"use client";

import { useRouter } from "next/navigation";
import { Footer } from "@/components/layout/Footer";
import { MarketingDefense } from "@/components/layout/MarketingDefense";
import { ReconciliationNetwork } from "@/components/layout/ReconciliationNetwork";
import { IntegrationsShowcase } from "@/components/layout/IntegrationsShowcase";

export default function ProductPage() {
  const router = useRouter();
  return (
    <main style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <style>{`
        header {
          background-color: rgba(255, 255, 255, 0.95) !important;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1) !important;
        }
        header nav a,
        header nav button {
          color: #1E293B !important;
        }

        /* Product Hero Section - Background at native resolution */
        .product-hero-section {
          position: relative;
          width: 100%;
          min-height: 1080px;
          height: 100vh;
          max-height: 1080px;
          overflow: hidden;
        }

        .product-hero-section::before {
          content: '';
          position: absolute;
          top: 0;
          left: 50%;
          transform: translateX(-50%);
          width: 2208px;
          height: 1080px;
          background-image: url('/images/product-overview-background.png');
          background-size: 2208px 1080px;
          background-repeat: no-repeat;
          background-position: center center;
          z-index: 0;
          pointer-events: none;
        }

        .product-hero-section::after {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          height: 100%;
          background: linear-gradient(to right, 
            #FFFFFF 0%, 
            rgba(255, 255, 255, 0.8) 5%,
            rgba(255, 255, 255, 0.3) 12%,
            transparent 20%, 
            transparent 80%, 
            rgba(255, 255, 255, 0.3) 88%,
            rgba(255, 255, 255, 0.8) 95%,
            #FFFFFF 100%);
          z-index: 0;
          pointer-events: none;
        }

        /* Bottom fade transition to next section */
        .product-hero-content::after {
          content: '';
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
          height: 150px;
          background: linear-gradient(to bottom, 
            transparent 0%,
            rgba(248, 250, 252, 0.2) 20%,
            rgba(248, 250, 252, 0.5) 50%,
            rgba(248, 250, 252, 0.8) 75%,
            rgba(248, 250, 252, 0.95) 90%,
            #F8FAFC 100%);
          z-index: 3;
          pointer-events: none;
        }

        .product-hero-content {
          position: relative;
          z-index: 1;
          max-width: 1920px;
          width: 100%;
          height: 100%;
          margin: 0 auto;
        }

        /* Card positioning - EXACT absolute coordinates aligned to frame box
           Frame in 2208px background: left 1148px, top 162px, width 905px, height 723px
           Centered on 1920px viewport: frame left = 1148 - 144 = 1004px
           Card aspect ratio matches Command Center image (1619×1080 = 1.499:1) */
        .product-hero__mockup-card {
          position: absolute;
          left: 1241px;
          top: 233px;
          width: 700px;
          aspect-ratio: 1619 / 1080;
          background: #FFFFFF;
          border-radius: 16px;
          border: 1px solid rgba(15, 23, 42, 0.08);
          box-shadow:
            0 20px 60px rgba(15, 23, 42, 0.15),
            0 0 0 1px rgba(255, 255, 255, 0.1) inset;
          z-index: 5;
          overflow: hidden;
        }

        /* Mobile: Reset absolute positioning */
        @media (max-width: 1024px) {
          .product-hero__mockup-card {
            position: relative !important;
            left: auto !important;
            top: auto !important;
            width: 100% !important;
            max-width: 680px !important;
            aspect-ratio: 16 / 10 !important;
          }
        }

        /* Additional mobile fix to prevent any clipping */
        @media (max-width: 767px) {
          .product-hero__mockup-card {
            width: calc(100% - 40px) !important;
            max-width: calc(100% - 40px) !important;
            margin: 0 auto !important;
            overflow: hidden !important;
          }
          
          .product-hero__mockup-card img {
            width: 100% !important;
            height: 100% !important;
            object-fit: cover !important;
            object-position: 45% center !important;
          }
        }
        
        .product-hero__mockup-card img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          object-position: center;
          display: block;
          margin: 0;
          image-rendering: -webkit-optimize-contrast;
          image-rendering: crisp-edges;
        }

        /* Text column positioning */
        .product-hero__text-column {
          position: absolute;
          left: 0;
          top: 50%;
          transform: translateY(-50%);
          max-width: 620px;
          padding: 0 0 0 120px;
          z-index: 10;
        }

        /* Responsive Styles - Scaled proportionally from 1920px base
           Base: left 1041px, top 227px, width 831px, height 593px */

        /* 1600px viewport: Scale factor 0.833 (1600/1920) */
        @media (max-width: 1600px) {
          .product-hero-section {
            min-height: 900px;
            max-height: 900px;
          }
          .product-hero-section::before {
            width: 1840px;
            height: 900px;
            background-size: 1840px 900px;
          }
          .product-hero__text-column {
            padding-left: 100px;
            max-width: 500px;
          }
          .product-hero__mockup-card {
            left: 1034px;
            top: 194px;
            width: 583px;
            aspect-ratio: 1619 / 1080;
          }
        }

        /* 1440px viewport: Scale factor 0.75 (1440/1920) */
        @media (max-width: 1440px) {
          .product-hero-section {
            min-height: 810px;
            max-height: 810px;
          }
          .product-hero-section::before {
            width: 1656px;
            height: 810px;
            background-size: 1656px 810px;
          }
          .product-hero__text-column {
            padding-left: 80px;
            max-width: 460px;
          }
          .product-hero__text-column h1 {
            font-size: 44px !important;
          }
          .product-hero__mockup-card {
            left: 930px;
            top: 175px;
            width: 525px;
            aspect-ratio: 1619 / 1080;
          }
        }

        /* 1280px viewport: Scale factor 0.667 (1280/1920) */
        @media (max-width: 1280px) {
          .product-hero-section {
            min-height: 720px;
            max-height: 720px;
          }
          .product-hero-section::before {
            width: 1472px;
            height: 720px;
            background-size: 1472px 720px;
          }
          .product-hero__text-column {
            padding-left: 60px;
            max-width: 420px;
          }
          .product-hero__text-column h1 {
            font-size: 40px !important;
          }
          .product-hero__mockup-card {
            left: 827px;
            top: 155px;
            width: 467px;
            aspect-ratio: 1619 / 1080;
          }
        }

        /* Tablet and below: Hide background, stack layout */
        @media (max-width: 1024px) {
          .product-hero-section::before {
            display: none;
          }
          .product-hero-section {
            background: linear-gradient(135deg, #F8FAFC 0%, #EEF2FF 50%, #F5F3FF 100%);
            height: auto;
            min-height: auto;
            max-height: none;
            padding: 100px 40px;
            margin-top: 80px;
          }
          .product-hero-content {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 48px;
          }
          .product-hero__text-column {
            position: relative;
            left: auto;
            top: auto;
            transform: none;
            padding: 0;
            max-width: 640px;
            text-align: center;
          }
          .product-hero__text-column h1 {
            font-size: 38px !important;
            max-width: 100% !important;
          }
          .product-hero__mockup-card {
            position: relative;
            left: auto;
            top: auto;
            width: 100%;
            max-width: 680px;
            height: auto;
            min-height: 400px;
          }
          .product-hero__ctas {
            justify-content: center !important;
          }
          .product-hero__bullets {
            align-items: center !important;
          }
        }

        /* Mobile - reduced top spacing between nav and hero content */
        @media (max-width: 767px) {
          .product-hero-section {
            padding: 48px 20px 60px 20px !important;
            margin-top: 48px !important;
          }
          .product-hero__text-column {
            padding: 0 !important;
            max-width: 100% !important;
          }
          .product-hero__text-column h1 {
            font-size: 32px !important;
            line-height: 1.25 !important;
            margin-bottom: 20px !important;
          }
          .product-hero__text-column p {
            font-size: 16px !important;
            line-height: 1.5 !important;
            margin-bottom: 20px !important;
          }
          .product-hero__bullets {
            margin-bottom: 24px !important;
          }
          .product-hero__bullets > div {
            margin-bottom: 8px !important;
          }
          .product-hero__ctas {
            flex-direction: column !important;
            gap: 12px !important;
            width: 100% !important;
          }
          .product-hero__ctas button {
            width: 100% !important;
            max-width: 100% !important;
            min-height: 48px !important;
          }
          .product-hero__mockup-card {
            width: 100% !important;
            max-width: 100% !important;
            min-height: 300px !important;
            margin-top: 32px !important;
          }
        }
      `}</style>

      {/* Hero Section with Background */}
      <section className="product-hero-section">
        {/* Hero Foreground Content */}
        <div className="product-hero-content">
          {/* Left Column: Text Content */}
          <div className="product-hero__text-column" style={{ display: "flex", flexDirection: "column" }}>
            {/* Headline */}
            <h1
              style={{
                fontFamily: "'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                fontSize: "52px",
                fontWeight: 800,
                lineHeight: 1.12,
                letterSpacing: "-0.03em",
                color: "#0F172A",
                maxWidth: "760px",
                margin: "0 0 24px 0",
              }}
            >
              Verify Every Dollar of Ad Spend with Automated Attribution
            </h1>

            {/* Body Paragraph */}
            <p
              style={{
                fontSize: "18px",
                fontWeight: 400,
                lineHeight: 1.55,
                color: "#4B5563",
                maxWidth: "640px",
                margin: "0 0 24px 0",
              }}
            >
              Stop guessing where your budget works. Skeldir connects all ad platforms, reconciles claimed revenue vs. verified revenue, and shows exactly which channels drive real growth.
            </p>

            {/* Bullet List */}
            <div
              className="product-hero__bullets"
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "10px",
                margin: "0 0 28px 0",
              }}
            >
              {/* Bullet 1: Revenue Verification */}
              <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
                <svg width="20" height="20" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0, marginTop: "2px" }}>
                  <defs>
                    <linearGradient id="arrowGradient" x1="0%" y1="0%" x2="100%" y2="100%" gradientUnits="userSpaceOnUse">
                      <stop offset="0%" stopColor="#4F46E5" />
                      <stop offset="50%" stopColor="#A855F7" />
                      <stop offset="100%" stopColor="#EC4899" />
                    </linearGradient>
                  </defs>
                  <path d="M4 3L8 6L4 9" stroke="url(#arrowGradient)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                </svg>
                <span style={{ fontSize: "16px", lineHeight: 1.45, color: "#4B5563" }}>
                  <strong style={{ color: "#111827", fontWeight: 600 }}>Revenue Verification</strong> – See platform-claimed vs. verified revenue side-by-side
                </span>
              </div>

              {/* Bullet 2: Confidence Ranges */}
              <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
                <svg width="20" height="20" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0, marginTop: "2px" }}>
                  <defs>
                    <linearGradient id="arrowGradient2" x1="0%" y1="0%" x2="100%" y2="100%" gradientUnits="userSpaceOnUse">
                      <stop offset="0%" stopColor="#4F46E5" />
                      <stop offset="50%" stopColor="#A855F7" />
                      <stop offset="100%" stopColor="#EC4899" />
                    </linearGradient>
                  </defs>
                  <path d="M4 3L8 6L4 9" stroke="url(#arrowGradient2)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                </svg>
                <span style={{ fontSize: "16px", lineHeight: 1.45, color: "#4B5563" }}>
                  <strong style={{ color: "#111827", fontWeight: 600 }}>Confidence Ranges</strong> – Know exactly how certain your attribution model is
                </span>
              </div>

              {/* Bullet 3: 48-Hour Deployment */}
              <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
                <svg width="20" height="20" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0, marginTop: "2px" }}>
                  <defs>
                    <linearGradient id="arrowGradient3" x1="0%" y1="0%" x2="100%" y2="100%" gradientUnits="userSpaceOnUse">
                      <stop offset="0%" stopColor="#4F46E5" />
                      <stop offset="50%" stopColor="#A855F7" />
                      <stop offset="100%" stopColor="#EC4899" />
                    </linearGradient>
                  </defs>
                  <path d="M4 3L8 6L4 9" stroke="url(#arrowGradient3)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                </svg>
                <span style={{ fontSize: "16px", lineHeight: 1.45, color: "#4B5563" }}>
                  <strong style={{ color: "#111827", fontWeight: 600 }}>48-Hour Deployment</strong> – Start analyzing without 6-month integration projects
                </span>
              </div>
            </div>

            {/* CTA Row */}
            <div className="product-hero__ctas" style={{ display: "flex", alignItems: "center", gap: "16px", marginTop: "4px" }}>
              {/* Primary CTA */}
              <button
                onClick={() => router.push('/signup')}
                style={{
                  display: "inline-flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  minWidth: "220px",
                  height: "56px",
                  padding: "0 28px",
                  borderRadius: "999px",
                  border: "none",
                  background: "#2563EB",
                  color: "#FFFFFF",
                  fontSize: "16px",
                  fontWeight: 600,
                  boxShadow: "0 8px 24px rgba(37, 99, 235, 0.35)",
                  cursor: "pointer",
                  transition: "all 200ms ease-out",
                  lineHeight: "1.2",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "#1D4ED8";
                  e.currentTarget.style.boxShadow = "0 10px 30px rgba(37, 99, 235, 0.45)";
                  e.currentTarget.style.transform = "translateY(-1px)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "#2563EB";
                  e.currentTarget.style.boxShadow = "0 8px 24px rgba(37, 99, 235, 0.35)";
                  e.currentTarget.style.transform = "translateY(0)";
                }}
              >
                Get started
                <span style={{ fontSize: "14px", fontWeight: 500 }}>$149/mo</span>
              </button>

              {/* Secondary CTA */}
              <button
                onClick={() => router.push('/pricing')}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  minWidth: "160px",
                  height: "56px",
                  padding: "0 26px",
                  borderRadius: "999px",
                  border: "2px solid #2563EB",
                  color: "#2563EB",
                  background: "transparent",
                  fontSize: "16px",
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 180ms ease-out",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "rgba(37, 99, 235, 0.06)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "transparent";
                }}
              >
                Book Demo
              </button>
            </div>
          </div>

          {/* Right Column: Product Card Mockup - Positioned within frame box */}
          <div className="product-hero__mockup-card">
            <img
              src="/images/4. Command Center .png"
              alt="Skeldir Command Center"
              loading="lazy"
              decoding="async"
            />
          </div>
        </div>
      </section>

      {/* Below Hero Section - Features */}
      <section
        className="product-features-section"
        style={{
          width: "100%",
          backgroundColor: "#F8FAFC",
          padding: "100px 60px",
          position: "relative",
        }}
      >
        {/* Top fade-in transition from hero section */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: "150px",
            background: "linear-gradient(to bottom, rgba(248, 250, 252, 0) 0%, rgba(248, 250, 252, 0.3) 30%, rgba(248, 250, 252, 0.7) 60%, rgba(248, 250, 252, 0.95) 85%, #F8FAFC 100%)",
            pointerEvents: "none",
            zIndex: 1,
          }}
        />
        <div
          className="product-features-container"
          style={{
            maxWidth: "1300px",
            margin: "0 auto",
            display: "grid",
            gridTemplateColumns: "340px 1fr",
            gap: "90px",
            alignItems: "start",
            position: "relative",
            zIndex: 2,
          }}
        >
          {/* Left: Main Heading */}
          <div className="product-features-heading">
            <h2
              className="product-features-title"
              style={{
                fontSize: "2.875rem",
                fontWeight: 400,
                background: "linear-gradient(120deg, #4F46E5 0%, #A855F7 50%, #EC4899 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
                color: "transparent",
                lineHeight: "1.25",
                fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                letterSpacing: "-0.015em",
                display: "inline-block",
              }}
            >
              Smarter insights for faster decisions
            </h2>
          </div>

          {/* Right: 3 Feature Columns */}
          <div
            className="product-features-grid"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: "54px",
            }}
          >
            {/* Feature 1: Everything in one place */}
            <div className="product-feature-card">
              <div
                style={{
                  width: "30px",
                  height: "30px",
                  marginBottom: "18px",
                }}
              >
                <svg
                  width="30"
                  height="30"
                  viewBox="0 0 30 30"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <rect x="3.75" y="3.75" width="9" height="9" rx="1.85" stroke="#7C3AED" strokeWidth="1.1" fill="none" />
                  <rect x="17.25" y="3.75" width="9" height="9" rx="1.85" stroke="#7C3AED" strokeWidth="1.1" fill="none" />
                  <rect x="3.75" y="17.25" width="9" height="9" rx="1.85" stroke="#7C3AED" strokeWidth="1.1" fill="none" />
                  <rect x="17.25" y="17.25" width="9" height="9" rx="1.85" stroke="#7C3AED" strokeWidth="1.1" fill="none" />
                </svg>
              </div>
              <h3
                style={{
                  fontSize: "1.125rem",
                  fontWeight: 500,
                  color: "#000000",
                  marginBottom: "12px",
                  fontFamily: "'SF Pro Display', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                  letterSpacing: "-0.01em",
                }}
              >
                Everything you need to trust your marketing numbers all in one place
              </h3>
              <p
                style={{
                  fontSize: "0.9375rem",
                  color: "#6B7280",
                  lineHeight: "1.65",
                  fontFamily: "'SF Pro Text', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                  fontWeight: 400,
                }}
              >
                Stop bouncing between ad platforms, spreadsheets, and reports. Skeldir brings your channel performance and verified outcomes together, then explains the &quot;why&quot; with statistical transparency.
              </p>
            </div>

            {/* Feature 2: Get the why */}
            <div className="product-feature-card">
              <div
                style={{
                  width: "30px",
                  height: "30px",
                  marginBottom: "18px",
                }}
              >
                <svg
                  width="30"
                  height="30"
                  viewBox="0 0 30 30"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M16.8 2.8L5.6 17.8h9.4l-1.9 9.4 11.3-15H14.1l2.7-9.4z"
                    stroke="#7C3AED"
                    strokeWidth="1.1"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    fill="none"
                  />
                </svg>
              </div>
              <h3
                style={{
                  fontSize: "1.125rem",
                  fontWeight: 500,
                  color: "#000000",
                  marginBottom: "12px",
                  fontFamily: "'SF Pro Display', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                  letterSpacing: "-0.01em",
                }}
              >
                Get the &quot;why,&quot; not just the number
              </h3>
              <p
                style={{
                  fontSize: "0.9375rem",
                  color: "#6B7280",
                  lineHeight: "1.65",
                  fontFamily: "'SF Pro Text', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                  fontWeight: 400,
                }}
              >
                Skeldir turns your messy marketing inputs into a consistent, evidence-backed view—complete with confidence ranges and discrepancy detection—so decisions happen faster and with less second-guessing.
              </p>
            </div>

            {/* Feature 3: Transparent insights */}
            <div className="product-feature-card">
              <div
                style={{
                  width: "36px",
                  height: "30px",
                  marginBottom: "18px",
                }}
              >
                <svg
                  width="36"
                  height="30"
                  viewBox="0 0 36 30"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  {/* Shield outline */}
                  <path
                    d="M15 2.8L5.6 6.5v7.5c0 5.8 4 10.5 9.4 12.3c4.5-1.5 7.8-5 9.2-9.3M24.2 6.5L15 2.8"
                    stroke="#7C3AED"
                    strokeWidth="1.1"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    fill="none"
                  />
                  {/* Lock shackle */}
                  <path
                    d="M22 17.5v-2.4c0-1.1 0.9-2 2-2s2 0.9 2 2v2.4"
                    stroke="#7C3AED"
                    strokeWidth="1.1"
                    strokeLinecap="butt"
                    fill="none"
                  />
                  {/* Lock body */}
                  <rect
                    x="20"
                    y="17.5"
                    width="8"
                    height="8"
                    rx="1"
                    fill="#7C3AED"
                  />
                  {/* Keyhole */}
                  <circle
                    cx="24"
                    cy="21.5"
                    r="0.8"
                    fill="#FFFFFF"
                  />
                </svg>
              </div>
              <h3
                style={{
                  fontSize: "1.125rem",
                  fontWeight: 500,
                  color: "#000000",
                  marginBottom: "12px",
                  fontFamily: "'SF Pro Display', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                  letterSpacing: "-0.01em",
                }}
              >
                Transparent insights, built for trust
              </h3>
              <p
                style={{
                  fontSize: "0.9375rem",
                  color: "#6B7280",
                  lineHeight: "1.65",
                  fontFamily: "'SF Pro Text', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                  fontWeight: 400,
                }}
              >
                Every insight is tied back to underlying sources and assumptions, so teams can trust what they&apos;re seeing and understand where it came from.
              </p>
            </div>
          </div>
        </div>

        <style>{`
          @media (max-width: 1024px) {
            .product-features-section {
              padding: 80px 40px !important;
            }
            
            .product-features-container {
              grid-template-columns: 1fr !important;
              gap: 48px !important;
            }
            
            .product-features-heading {
              text-align: center !important;
            }
            
            .product-features-title {
              font-size: 2.25rem !important;
            }
            
            .product-features-grid {
              grid-template-columns: 1fr !important;
              gap: 40px !important;
            }
          }

          @media (max-width: 767px) {
            .product-features-section {
              padding: 60px 20px !important;
              overflow-x: hidden !important;
            }
            
            .product-features-container {
              display: flex !important;
              flex-direction: column !important;
              gap: 40px !important;
              width: 100% !important;
              max-width: 100% !important;
              padding: 0 !important;
              margin: 0 !important;
            }
            
            .product-features-heading {
              width: 100% !important;
              text-align: center !important;
              padding: 0 !important;
              margin: 0 !important;
            }
            
            .product-features-title {
              font-size: 32px !important;
              line-height: 1.25 !important;
              text-align: center !important;
            }
            
            .product-features-grid {
              display: flex !important;
              flex-direction: column !important;
              gap: 32px !important;
              width: 100% !important;
              max-width: 100% !important;
              padding: 0 !important;
              margin: 0 !important;
            }
            
            .product-feature-card {
              width: 100% !important;
              max-width: 100% !important;
              padding: 0 !important;
              margin: 0 !important;
              position: relative !important;
              left: 0 !important;
              right: 0 !important;
            }
            
            .product-feature-card h3 {
              font-size: 18px !important;
              line-height: 1.4 !important;
              margin-bottom: 12px !important;
            }
            
            .product-feature-card p {
              font-size: 15px !important;
              line-height: 1.6 !important;
            }
          }
        `}</style>
      </section>

      {/* Marketing Defense Section (Replaces How Skeldir Works) */}
      <MarketingDefense />

      {/* Reconciliation Network Section (Section 4) */}
      <ReconciliationNetwork />

      {/* Integrations Showcase Section (Section 5) */}
      <IntegrationsShowcase />

      <Footer />
    </main>
  );
}
