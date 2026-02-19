"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

export function HeroSection() {
  return (
    <div className="pt-24 pb-16 lg:pt-32 lg:pb-24">
      <div className="container mx-auto px-4 md:px-6">
        <div className="grid gap-12 lg:grid-cols-2 lg:gap-12 items-center">
          {/* Left: Text Content */}
          <div className="flex flex-col justify-center space-y-8 text-left lg:pr-8 lg:-ml-[20%] hero-text-column">
            <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl md:text-6xl leading-tight hero-headline" style={{ color: 'white' }}>
              <span>Stop guessing where</span> <span>your ad budget works—</span><span style={{ 
                color: '#111827', 
                fontFamily: "'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                fontWeight: 700,
                lineHeight: 1.2,
                letterSpacing: '-0.025em'
              }}>know with statistical confidence</span>
            </h1>

            <p className="max-w-[600px] text-white mx-auto lg:mx-0 hero-subheadline" style={{ fontSize: '16px', lineHeight: 1.5 }}>
              Skeldir compares Facebook/Google/TikTok claims against your actual Stripe/Shopify revenue<br />
              <span style={{ display: 'inline-block', marginTop: '2px' }}>See platform over-reporting—then act on statistical confidence ranges, not black-box numbers.</span><br />
              <span style={{ display: 'inline-block', marginTop: '2px' }}>Live in 48 hours, not months.</span>
            </p>

            <div className="flex flex-col items-center lg:items-start gap-4 hero-cta-container">
              <div className="flex flex-col sm:flex-row items-center gap-4 hero-buttons">
              <Link href="/book-demo" className="hero-cta-link-primary">
                <Button
                    className="transition-all hero-cta-button hero-cta-button-primary"
                    style={{
                      backgroundColor: '#2563EB',
                      color: '#FFFFFF',
                      fontFamily: 'Inter, sans-serif',
                      fontSize: '16px',
                      fontWeight: 700,
                      minWidth: '260px',
                      height: '48px',
                      paddingLeft: '20px',
                      paddingRight: '20px',
                      borderRadius: '8px',
                      boxShadow: '0 2px 8px rgba(37, 99, 235, 0.2)',
                      cursor: 'pointer',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = '#1E40AF';
                      e.currentTarget.style.boxShadow = '0 4px 12px rgba(37, 99, 235, 0.4)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = '#2563EB';
                      e.currentTarget.style.boxShadow = '0 2px 8px rgba(37, 99, 235, 0.2)';
                    }}
                >
                  See your revenue discrepancies
                </Button>
              </Link>
              <Link href="/signup" className="hero-cta-link-secondary">
                <Button
                  className="transition-all hero-cta-button hero-cta-button-secondary"
                  style={{
                    backgroundColor: 'transparent',
                    border: '2px solid #000000',
                    color: '#000000',
                    fontFamily: 'Inter, sans-serif',
                    fontSize: '16px',
                    fontWeight: 600,
                    minWidth: '260px',
                    height: '48px',
                    paddingLeft: '20px',
                    paddingRight: '20px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(0, 0, 0, 0.1)';
                    e.currentTarget.style.borderColor = '#000000';
                    e.currentTarget.style.color = '#000000';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                    e.currentTarget.style.borderColor = '#000000';
                    e.currentTarget.style.color = '#000000';
                  }}
                >
                  Start your 48-Hour Deployment
                </Button>
              </Link>
              </div>

              <p className="text-sm text-black font-medium hero-tagline">
                Deploy Today ·  48 Hours to Attribution Clarity
              </p>
            </div>
          </div>

          {/* Right: Product Visual - responsive home product hero screenshot */}
          <div className="relative mx-auto w-full max-w-[950px] lg:max-w-none lg:ml-[20%] hero-image-container home-product-hero">
            <div 
              className="relative rounded-2xl overflow-visible hero-image-glass"
              style={{
                background: 'rgba(255, 255, 255, 0.7)',
                backdropFilter: 'blur(20px) saturate(180%)',
                WebkitBackdropFilter: 'blur(20px) saturate(180%)',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.15), 0 0 0 1px rgba(255, 255, 255, 0.2) inset, 0 20px 60px -15px rgba(0, 0, 0, 0.2)',
                transform: 'scale(1.1)',
              }}
            >
              <div className="overflow-hidden rounded-2xl">
                <img
                  src="/assets/images/home-product-hero/home-product-hero-800w.jpg"
                  srcSet="/assets/images/home-product-hero/home-product-hero-400w.jpg 400w, /assets/images/home-product-hero/home-product-hero-800w.jpg 800w, /assets/images/home-product-hero/home-product-hero-1200w.jpg 1200w"
                  sizes="(max-width: 600px) 100vw, (max-width: 960px) 80vw, 950px"
                  alt="Channel Comparison Dashboard — Skeldir ad channel ROAS and budget shift recommendations"
                  className="w-full h-auto object-contain hero-dashboard-image"
                  loading="eager"
                  decoding="async"
                  fetchPriority="high"
                />
              </div>
            </div>
          </div>
          
          <style>{`
            @keyframes float {
              0%, 100% {
                transform: translateY(0px);
              }
              50% {
                transform: translateY(-12px);
              }
            }
            .hero-image-glass {
              animation: float 6s ease-in-out infinite;
              position: relative;
            }
            .hero-image-glass::after {
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

            /* Mobile: same structure as desktop (left-aligned, same hierarchy) */
            @media (max-width: 767px) {
              .hero-text-column {
                align-items: flex-start !important;
              }
              .hero-headline {
                font-size: 32px !important;
                line-height: 1.25 !important;
                letter-spacing: -0.03em !important;
                font-weight: 800 !important;
                margin-bottom: 20px !important;
                text-align: left !important;
              }
              
              .hero-headline span {
                white-space: normal !important;
                display: inline !important;
              }

              .hero-subheadline {
                font-size: 14px !important;
                line-height: 1.45 !important;
                padding: 0 !important;
                margin-bottom: 20px !important;
                text-align: left !important;
              }

              .hero-cta-container {
                width: 100% !important;
                max-width: 100% !important;
                padding: 0 !important;
                box-sizing: border-box !important;
                overflow-x: hidden !important;
                align-items: flex-start !important;
              }

              .hero-buttons {
                display: flex !important;
                flex-direction: row !important;
                align-items: center !important;
                justify-content: flex-start !important;
                gap: 12px !important;
                flex-wrap: wrap !important;
                padding: 0 !important;
                margin: 0 !important;
              }

              .hero-cta-link-primary,
              .hero-cta-link-secondary {
                display: inline-flex !important;
              }

              .hero-cta-button-primary {
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                min-width: 260px !important;
                width: auto !important;
                height: 48px !important;
                min-height: 48px !important;
                padding: 0 20px !important;
                border-radius: 8px !important;
                background: #2563EB !important;
                color: #FFFFFF !important;
                font-size: 16px !important;
                font-weight: 700 !important;
                box-shadow: 0 2px 8px rgba(37, 99, 235, 0.2) !important;
                transition: all 200ms ease-out !important;
                line-height: 1.2 !important;
                border: none !important;
                white-space: nowrap !important;
              }

              .hero-cta-button-primary:hover {
                background: #1E40AF !important;
                box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4) !important;
              }

              .hero-cta-button-secondary {
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                min-width: 260px !important;
                width: auto !important;
                height: 48px !important;
                min-height: 48px !important;
                padding: 0 20px !important;
                border-radius: 8px !important;
                border: 2px solid #000000 !important;
                color: #000000 !important;
                background: transparent !important;
                font-size: 16px !important;
                font-weight: 600 !important;
                transition: all 180ms ease-out !important;
                white-space: nowrap !important;
              }

              .hero-cta-button-secondary:hover {
                background: rgba(0, 0, 0, 0.1) !important;
                border-color: #000000 !important;
                color: #000000 !important;
              }

              @media (max-width: 360px) {
                .hero-buttons {
                  gap: 8px !important;
                }
                .hero-cta-button-primary,
                .hero-cta-button-secondary {
                  min-width: 220px !important;
                  font-size: 14px !important;
                }
              }

              .hero-tagline {
                font-size: 14px !important;
                text-align: left !important;
                padding: 0 !important;
              }

              .hero-image-container {
                width: 100% !important;
                max-width: 100% !important;
                padding: 0 !important;
                margin-top: 32px !important;
              }

              .hero-image-glass {
                transform: scale(1) !important;
                width: 100% !important;
              }

              .hero-dashboard-image {
                width: 100% !important;
                height: auto !important;
                object-fit: contain !important;
              }

              .hero-image-glass::after {
                display: none !important;
              }
            }

            @media (min-width: 768px) and (max-width: 1023px) {
              .hero-headline {
                font-size: 36px !important;
                line-height: 1.25 !important;
              }

              .hero-subheadline {
                font-size: 18px !important;
                line-height: 1.6 !important;
              }

              .hero-image-glass {
                transform: scale(1.05) !important;
              }
            }
          `}</style>
        </div>
      </div>
    </div>
  );
}
