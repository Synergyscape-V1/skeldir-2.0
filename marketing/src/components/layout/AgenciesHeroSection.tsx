"use client";

import Link from "next/link";
import Image from "next/image";

export function AgenciesHeroSection() {
  return (
    <section
      className="agencies-hero agencies-hero-section agencies-hero-reveal"
      aria-labelledby="agencies-hero-heading"
      style={{
        position: 'relative',
        width: '100%',
        minHeight: '100vh',
        overflow: 'hidden',
        margin: 0,
        paddingTop: '96px',
        paddingBottom: '48px',
      }}
    >
      {/* Responsive hero background (replaces CSS background for instant LCP) */}
      <img
        src="/assets/images/agencies-hero/agencies-hero-800w.jpg"
        srcSet="/assets/images/agencies-hero/agencies-hero-400w.jpg 400w, /assets/images/agencies-hero/agencies-hero-800w.jpg 800w, /assets/images/agencies-hero/agencies-hero-1200w.jpg 1200w"
        sizes="(max-width: 767px) 100vw, (max-width: 1023px) 80vw, 1200px"
        alt="Abstract green and gold gradient wave background"
        width={1200}
        height={661}
        loading="eager"
        fetchPriority="high"
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          objectPosition: 'center',
          display: 'block',
          zIndex: 0,
        }}
      />
      {/* Overlay content — preserved z-index above image */}
      <div
        style={{
          position: 'relative',
          zIndex: 1,
          display: 'flex',
          alignItems: 'center',
          minHeight: '100vh',
        }}
      >
      <div
        className="agencies-hero-container"
        style={{
          width: '100%',
          maxWidth: '1280px',
          margin: '0 auto',
          padding: '0 16px',
        }}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr',
            gap: '48px',
            alignItems: 'center',
          }}
          className="agencies-hero-grid"
        >
          {/* Left Column: Text Content */}
          {/* Left column: no negative margin — negative X pushes content past viewport (x<0) and causes clipping */}
          <div
            className="agencies-hero-text"
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              textAlign: 'center',
              marginTop: '-200px',
              marginLeft: 0,
            }}
          >
          <h1
            id="agencies-hero-heading"
            className="agencies-hero-headline"
            style={{
              fontFamily: "'DM Sans', 'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
              fontSize: '56px',
              fontWeight: 700,
              lineHeight: 1.15,
              letterSpacing: '-0.025em',
              color: '#111827',
              margin: '0 0 32px 0',
            }}
          >
            <span style={{ color: '#FFFFFF' }}>Enterprise Attribution Intelligence Without</span> Enterprise Complexity
          </h1>

          <p
            className="agencies-hero-subheadline"
            style={{
              fontFamily: "'DM Sans', 'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
              fontSize: '20px',
              fontWeight: 400,
              lineHeight: 1.6,
              color: '#FFFFFF',
              margin: '0 auto 32px auto',
              maxWidth: '600px',
            }}
          >
            Skeldir delivers Bayesian confidence ranges for multi-client portfolios—exposing platform over-reporting discrepancies, eliminating manual reconciliation cycles, with deployment measured in days instead of months.
          </p>

          {/* Feature Badges */}
          <div
            className="agencies-hero-badges"
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '12px',
              margin: '0 0 32px 0',
            }}
          >
            {['Multi-tenant Dashboard', 'White-label Branding', 'REST API Access'].map((badge, index) => (
              <span
                key={badge}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 16px',
                  borderRadius: '999px',
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #E5E7EB',
                  fontFamily: "'DM Sans', 'Inter', sans-serif",
                  fontSize: '14px',
                  fontWeight: 500,
                  color: '#374151',
                }}
              >
                <svg width="20" height="20" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0, marginTop: "2px" }}>
                  <defs>
                    <linearGradient id={`arrowGradientBadge${index}`} x1="0%" y1="0%" x2="100%" y2="100%" gradientUnits="userSpaceOnUse">
                      <stop offset="0%" stopColor="#4F46E5" />
                      <stop offset="50%" stopColor="#A855F7" />
                      <stop offset="100%" stopColor="#EC4899" />
                    </linearGradient>
                  </defs>
                  <path d="M4 3L8 6L4 9" stroke={`url(#arrowGradientBadge${index})`} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                </svg>
                {badge}
              </span>
            ))}
          </div>

          {/* Primary CTA */}
          <div
            className="agencies-hero-cta"
            style={{
              display: 'flex',
              flexDirection: 'row',
              alignItems: 'center',
              gap: '16px',
            }}
          >
            <Link
              href="/contact-sales?tier=3&source=agencies-hero"
              className="agencies-hero-cta-button"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '0 32px',
                height: '52px',
                minWidth: '180px',
                backgroundColor: '#2563EB',
                color: '#FFFFFF',
                fontFamily: "'DM Sans', 'Inter', sans-serif",
                fontSize: '16px',
                fontWeight: 600,
                borderRadius: '10px',
                textDecoration: 'none',
                boxShadow: '0 2px 8px rgba(37, 99, 235, 0.25)',
                transition: 'all 200ms ease',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#1D4ED8';
                e.currentTarget.style.boxShadow = '0 4px 16px rgba(37, 99, 235, 0.4)';
                e.currentTarget.style.transform = 'translateY(-1px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#2563EB';
                e.currentTarget.style.boxShadow = '0 2px 8px rgba(37, 99, 235, 0.25)';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              Book Demo
            </Link>
            <Link
              href="/pricing"
              className="agencies-hero-cta-button-secondary"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                minWidth: '160px',
                height: '56px',
                padding: '0 26px',
                borderRadius: '999px',
                border: '2px solid #000000',
                color: '#000000',
                background: 'transparent',
                fontFamily: "'DM Sans', 'Inter', sans-serif",
                fontSize: '16px',
                fontWeight: 600,
                textDecoration: 'none',
                cursor: 'pointer',
                transition: 'all 180ms ease-out',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(0, 0, 0, 0.1)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            >
              View Pricing
            </Link>
          </div>
        </div>

          {/* Right Column: Product Visual */}
          <div className="relative mx-auto w-full max-w-[1600px] agencies-hero-visual" style={{ marginTop: '-250px' }}>
            <div 
              className="relative rounded-2xl overflow-visible agencies-hero-image-glass"
              style={{
                background: 'rgba(255, 255, 255, 0.7)',
                backdropFilter: 'blur(20px) saturate(180%)',
                WebkitBackdropFilter: 'blur(20px) saturate(180%)',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.15), 0 0 0 1px rgba(255, 255, 255, 0.2) inset, 0 20px 60px -15px rgba(0, 0, 0, 0.2)',
                transform: 'scale(1.4)',
              }}
            >
              <div className="overflow-hidden rounded-2xl">
                <Image
                  src="/images/Final Agency Hero Image.png"
                  alt="Agency Command Center Dashboard"
                  width={1600}
                  height={1200}
                  className="w-full h-auto object-contain agencies-hero-dashboard-image"
                  priority
                />
              </div>
            </div>
          </div>
        </div>
      </div>
      </div>

      {/* Bottom gradient overlay for transition feel */}
      <div
        className="agencies-hero-bottom-gradient"
        aria-hidden="true"
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: '260px',
          background:
            'linear-gradient(to bottom, transparent 0%, transparent 40%, rgba(255, 255, 255, 0.4) 65%, rgba(255, 255, 255, 0.85) 85%, rgba(255, 255, 255, 1) 100%)',
          pointerEvents: 'none',
          zIndex: 1,
        }}
      />

      {/* Wave Separator SVG — positioned at bottom for seamless transition */}
      <div
        className="agencies-hero-wave"
        aria-hidden="true"
        style={{
          position: 'absolute',
          bottom: '-120px',
          left: 0,
          right: 0,
          lineHeight: 0,
          overflow: 'hidden',
          zIndex: 2,
        }}
      >
        <svg
          viewBox="0 0 1440 120"
          preserveAspectRatio="none"
          style={{
            display: 'block',
            width: '100%',
            height: '120px',
          }}
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M0,120 C600,-40 840,-40 1440,120 L1440,120 L0,120 Z"
            fill="#FFFFFF"
          />
        </svg>
      </div>

      {/* Responsive Styles */}
      <style>{`
        @keyframes float {
          0%, 100% {
            transform: translateY(0px);
          }
          50% {
            transform: translateY(-12px);
          }
        }
        .agencies-hero-image-glass {
          animation: float 6s ease-in-out infinite;
          position: relative;
        }
        .agencies-hero-image-glass::after {
          content: '';
          position: absolute;
          bottom: -25px;
          left: 5%;
          right: 5%;
          height: 50px;
          background: radial-gradient(ellipse at center, rgba(0, 0, 0, 0.2) 0%, rgba(0, 0, 0, 0.1) 30%, rgba(0, 0, 0, 0.05) 50%, transparent 75%);
          border-radius: 50%;
          z-index: -1;
          filter: blur(16px);
          pointer-events: none;
          transform: scale(1.1);
        }

        @keyframes agencies-hero-reveal {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        .agencies-hero-reveal {
          animation: agencies-hero-reveal 0.55s ease-out 0.1s both;
        }

        /* Desktop: 1024px+ — two columns; text stays in viewport (no negative margin), overlap via image pull only */
        @media (min-width: 1024px) {
          .agencies-hero-container {
            padding: 0 24px !important;
          }
          .agencies-hero-grid {
            grid-template-columns: 1fr 1fr !important;
            gap: 48px !important;
          }
          .agencies-hero-text {
            text-align: left !important;
            padding-right: 32px !important;
            margin-left: 0 !important;
            margin-top: -200px !important;
          }
          .agencies-hero-headline {
            text-align: left !important;
          }
          .agencies-hero-subheadline {
            margin-left: 0 !important;
            margin-right: auto !important;
            text-align: left !important;
          }
          .agencies-hero-badges {
            justify-content: flex-start !important;
          }
          .agencies-hero-cta {
            align-items: flex-start !important;
          }
          .agencies-hero-visual {
            margin-left: 0 !important;
            margin-right: 0 !important;
            margin-top: -250px !important;
            max-width: 1600px !important;
            justify-self: end !important;
            transform: translateX(120px) !important;
          }
          .agencies-hero-image-glass {
            transform: scale(1.4) !important;
          }
        }

        /* Tablet: 768px - 1023px — single column stacked, visual first */
        @media (min-width: 768px) and (max-width: 1023px) {
          .agencies-hero {
            padding-top: 80px !important;
            min-height: auto !important;
            padding-bottom: 56px !important;
          }
          .agencies-hero-container {
            padding: 0 24px !important;
          }
          .agencies-hero-grid {
            grid-template-columns: 1fr !important;
            gap: 48px !important;
          }
          .agencies-hero-text {
            order: 2 !important;
            text-align: center !important;
          }
          .agencies-hero-visual {
            order: 1 !important;
          }
          .agencies-hero-headline {
            font-size: 42px !important;
            margin-bottom: 20px !important;
          }
          .agencies-hero-subheadline {
            font-size: 18px !important;
            max-width: 100% !important;
          }
          .agencies-hero-image-glass {
            transform: scale(1.3) !important;
          }
        }

        /* Mobile: < 768px — Enterprise-grade mobile optimization */
        @media (max-width: 767px) {
          .agencies-hero {
            padding-top: 80px !important;
            min-height: auto !important;
            padding-bottom: 48px !important;
          }
          .agencies-hero-container {
            padding: 0 20px !important;
            max-width: 100% !important;
          }
          .agencies-hero-grid {
            grid-template-columns: 1fr !important;
            gap: 40px !important;
            align-items: flex-start !important;
          }
          .agencies-hero-text {
            order: 1 !important;
            text-align: center !important;
            margin-top: 0 !important;
            margin-left: 0 !important;
            padding: 0 !important;
            width: 100% !important;
            max-width: 100% !important;
          }
          .agencies-hero-visual {
            order: 2 !important;
            margin-top: 0 !important;
            margin-left: 0 !important;
            width: 100% !important;
            max-width: 100% !important;
            padding: 0 !important;
          }
          .agencies-hero-headline {
            font-size: 36px !important;
            line-height: 1.25 !important;
            letter-spacing: -0.03em !important;
            font-weight: 700 !important;
            margin-bottom: 20px !important;
            padding: 0 4px !important;
          }
          .agencies-hero-headline span {
            white-space: normal !important;
            display: inline !important;
          }
          .agencies-hero-subheadline {
            font-size: 16px !important;
            line-height: 1.6 !important;
            max-width: 100% !important;
            margin-bottom: 24px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding: 0 4px !important;
          }
          .agencies-hero-badges {
            gap: 10px !important;
            margin-bottom: 32px !important;
            justify-content: center !important;
            padding: 0 4px !important;
            flex-wrap: wrap !important;
          }
          .agencies-hero-badges span {
            font-size: 13px !important;
            padding: 10px 16px !important;
            min-height: 40px !important;
            display: inline-flex !important;
            align-items: center !important;
          }
          .agencies-hero-cta {
            width: 100% !important;
            flex-direction: column !important;
            align-items: stretch !important;
            padding: 0 4px !important;
            gap: 12px !important;
          }
          .agencies-hero-cta-button,
          .agencies-hero-cta-button-secondary {
            width: 100% !important;
            min-width: unset !important;
            height: 56px !important;
            min-height: 56px !important;
            font-size: 16px !important;
            font-weight: 600 !important;
            padding: 0 24px !important;
            border-radius: 12px !important;
          }
          .agencies-hero-cta-button {
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3) !important;
          }
          .agencies-hero-cta-button-secondary {
            border-radius: 999px !important;
          }
          .agencies-hero-image-glass {
            transform: scale(1) !important;
            width: 100% !important;
            margin: 0 auto !important;
          }
          .agencies-hero-dashboard-image {
            width: 100% !important;
            height: auto !important;
            object-fit: contain !important;
          }
          .agencies-hero-image-glass::after {
            display: none !important;
          }
        }

        /* Very small screens: 320px - 374px — Enhanced readability */
        @media (max-width: 374px) {
          .agencies-hero-container {
            padding: 0 16px !important;
          }
          .agencies-hero-headline {
            font-size: 32px !important;
            line-height: 1.2 !important;
            margin-bottom: 16px !important;
          }
          .agencies-hero-subheadline {
            font-size: 15px !important;
            line-height: 1.5 !important;
            margin-bottom: 20px !important;
          }
          .agencies-hero-badges {
            flex-direction: column !important;
            align-items: stretch !important;
            gap: 8px !important;
          }
          .agencies-hero-badges span {
            width: 100% !important;
            justify-content: center !important;
          }
          .agencies-hero-cta-button {
            font-size: 15px !important;
            padding: 0 20px !important;
          }
        }

        /* Large screens: 1440px+ */
        @media (min-width: 1440px) {
          .agencies-hero-container {
            max-width: 1400px !important;
            padding: 0 64px !important;
          }
        }

        /* Ultra-wide screens: 2560px */
        @media (min-width: 2560px) {
          .agencies-hero-container {
            max-width: 1600px !important;
          }
        }
      `}</style>
    </section>
  );
}
