"use client";

import { useState, useCallback, useEffect } from "react";

// ============================================================================
// TESTIMONIAL CAROUSEL SECTION
// Reference: Skeldir Testimonial Carousel Component Specification v1.0
// Pixel-Perfect Implementation per Exact Specifications
// ============================================================================

// =============================================================================
// TESTIMONIAL DATA
// =============================================================================
interface Testimonial {
  id: number;
  quote: string;
  name: string;
  title: string;
  company: string;
  companyLogo: string;
  logoAlt: string;
  outcome: string;
}

const testimonials: Testimonial[] = [
  {
    id: 1,
    quote: "Skeldir automated what used to be our most time-intensive process. Now leadership trusts our numbers, and we're growing ad spend strategically instead of defensively",
    name: "Henry Vaggelatos",
    title: "Marketing Director",
    company: "Adobe",
    companyLogo: "/images/logos/adobe-logo.svg",
    logoAlt: "Adobe logo",
    outcome: "15 hours/week saved"
  },
  {
    id: 2,
    quote: "We discovered significant Meta ads over-reporting that would have stayed hidden. Skeldir's clear confidence ranges gave us the data to reallocate budget to channels that actually convert",
    name: "Dave Cualey",
    title: "VP of Growth",
    company: "Salesforce",
    companyLogo: "/images/logos/salesforce-logo.svg",
    logoAlt: "Salesforce logo",
    outcome: "$180K reallocated"
  },
  {
    id: 3,
    quote: "As an agency managing multiple e-commerce clients, Skeldir's rapid deployment changed everything. We went from lengthy enterprise implementations to live dashboards in days, not months.",
    name: "Elizabeth Smyk",
    title: "Agency Director",
    company: "HubSpot",
    companyLogo: "/images/logos/hubspot-logo.svg",
    logoAlt: "HubSpot logo",
    outcome: "48-hour deployment"
  },
  {
    id: 4,
    quote: "The Bayesian confidence ranges are a game-changer. Instead of defending black-box numbers, I show the probability distributions when requesting budget increases. The data finally speaks for itself.",
    name: "Sharon Gomez",
    title: "CMO",
    company: "Shopify",
    companyLogo: "/images/logos/shopify-logo.svg",
    logoAlt: "Shopify logo",
    outcome: "Board-level trust"
  },
  {
    id: 5,
    quote: "Within the first week, we caught platform over-reporting that our manual process never would have found. The revenue verification alone justifies the Skeldir investment.",
    name: "Naveen Bassani",
    title: "Director of Digital Marketing",
    company: "Stripe",
    companyLogo: "/images/logos/stripe-logo.svg",
    logoAlt: "Stripe logo",
    outcome: "$47K identified"
  }
];

// =============================================================================
// COMPANY LOGO COMPONENTS (Inline SVGs as fallbacks)
// =============================================================================
function AdobeLogo() {
  return (
    <div style={{ backgroundColor: "#FFFFFF", display: "inline-block", lineHeight: 0 }}>
      <img 
        src="/images/vantage.png" 
        alt="Vantage" 
        style={{
          width: "200px",
          height: "auto",
          objectFit: "contain",
          display: "block",
          border: "none",
          outline: "none",
          mixBlendMode: "multiply",
        }} loading="lazy" decoding="async" />
    </div>
  );
}

function SalesforceLogo() {
  return (
    <div style={{ backgroundColor: "#FFFFFF", display: "inline-block", lineHeight: 0 }}>
      <img 
        src="/images/2-catalyst.png" 
        alt="CATALYST" 
        style={{
          width: "200px",
          height: "auto",
          objectFit: "contain",
          display: "block",
          border: "none",
          outline: "none",
          mixBlendMode: "multiply",
        }} loading="lazy" decoding="async" />
    </div>
  );
}

function HubSpotLogo() {
  return (
    <div style={{ backgroundColor: "#FFFFFF", display: "inline-block", lineHeight: 0 }}>
      <img 
        src="/images/apex-analytics.jpg" 
        alt="Apex Analytics" 
        style={{
          width: "200px",
          height: "auto",
          objectFit: "contain",
          display: "block",
          border: "none",
          outline: "none",
          mixBlendMode: "multiply",
        }} loading="lazy" decoding="async" />
    </div>
  );
}

function ShopifyLogo() {
  return (
    <div style={{ backgroundColor: "#FFFFFF", display: "inline-block", lineHeight: 0 }}>
      <img 
        src="/images/meridian.png" 
        alt="Meridian" 
        style={{
          width: "200px",
          height: "auto",
          objectFit: "contain",
          display: "block",
          border: "none",
          outline: "none",
          mixBlendMode: "multiply",
        }} loading="lazy" decoding="async" />
    </div>
  );
}

function StripeLogo() {
  return (
    <div style={{ backgroundColor: "#FFFFFF", display: "inline-block", lineHeight: 0 }}>
      <img 
        src="/images/novus.png" 
        alt="Novus" 
        style={{
          width: "200px",
          height: "auto",
          objectFit: "contain",
          display: "block",
          border: "none",
          outline: "none",
          mixBlendMode: "multiply",
        }} loading="lazy" decoding="async" />
    </div>
  );
}

// =============================================================================
// CHEVRON ICONS
// =============================================================================
function ChevronLeftIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M12.5 15L7.5 10L12.5 5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M7.5 15L12.5 10L7.5 5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// =============================================================================
// COMPANY LOGO RENDERER
// =============================================================================
function CompanyLogo({ company }: { company: string }) {
  const logoStyle = {
    height: "28px",
    width: "auto",
    maxWidth: "120px",
  };

  switch (company) {
    case "Adobe":
      return <div style={logoStyle}><AdobeLogo /></div>;
    case "Salesforce":
      return <div style={logoStyle}><SalesforceLogo /></div>;
    case "HubSpot":
      return <div style={logoStyle}><HubSpotLogo /></div>;
    case "Shopify":
      return <div style={logoStyle}><ShopifyLogo /></div>;
    case "Stripe":
      return <div style={logoStyle}><StripeLogo /></div>;
    default:
      return null;
  }
}

// =============================================================================
// TESTIMONIAL CARD COMPONENT
// =============================================================================
interface TestimonialCardProps {
  testimonial: Testimonial;
  isActive: boolean;
  position: "left" | "center" | "right" | "hidden";
}

function TestimonialCard({ testimonial, isActive, position }: TestimonialCardProps) {
  const getCardStyle = (): React.CSSProperties => {
    const baseStyle: React.CSSProperties = {
      width: "500px",
      minHeight: "280px",
      backgroundColor: "#FFFFFF",
      borderRadius: "16px",
      padding: "32px",
      boxShadow: "0 4px 24px rgba(0, 0, 0, 0.12)",
      transition: "opacity 300ms ease, transform 300ms ease",
      display: "flex",
      flexDirection: "column",
      flex: "0 0 500px",
    };

    if (position === "center") {
      return {
        ...baseStyle,
        opacity: 1,
        transform: "scale(1)",
        zIndex: 10,
      };
    }

    if (position === "left" || position === "right") {
      return {
        ...baseStyle,
        opacity: 0.6,
        transform: "scale(0.95)",
        zIndex: 5,
      };
    }

    // hidden
    return {
      ...baseStyle,
      opacity: 0,
      pointerEvents: "none",
      display: "none",
    };
  };

  return (
    <div
      style={getCardStyle()}
      role="group"
      aria-roledescription="slide"
      aria-label={`Testimonial ${testimonial.id} of 5`}
      aria-hidden={position === "hidden"}
    >
      {/* Top Section: Name/Title and Company Logo side by side */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "20px",
        }}
      >
        {/* Name and Title */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "4px",
            flex: 1,
          }}
        >
          <span
            style={{
              fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
              fontSize: "18px",
              fontWeight: 600,
              color: "#1E293B",
              lineHeight: 1.4,
            }}
          >
            {testimonial.name}
          </span>
          <span
            style={{
              fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
              fontSize: "14px",
              fontWeight: 400,
              color: "#6B7280",
              lineHeight: 1.4,
            }}
          >
            {testimonial.title}
          </span>
        </div>

        {/* Company Logo */}
        <div
          style={{
            flexShrink: 0,
          }}
        >
          <CompanyLogo company={testimonial.company} />
        </div>
      </div>

      {/* Quote Text */}
      <p
        style={{
          fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
          fontSize: "16px",
          fontWeight: 400,
          lineHeight: 1.6,
          color: "#374151",
          margin: 0,
          flex: 1,
        }}
      >
        "{testimonial.quote}"
      </p>
    </div>
  );
}

// =============================================================================
// NAVIGATION BUTTON COMPONENT
// =============================================================================
interface NavButtonProps {
  direction: "prev" | "next";
  onClick: () => void;
  ariaLabel: string;
}

function NavButton({ direction, onClick, ariaLabel }: NavButtonProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [isActive, setIsActive] = useState(false);

  const getButtonStyle = (): React.CSSProperties => {
    let transform = "translateY(-50%)";
    let boxShadow = "0 2px 8px rgba(0, 0, 0, 0.06)";
    let backgroundColor = "#FFFFFF";
    let borderColor = "#E2E8F0";

    if (isHovered) {
      backgroundColor = "#F8FAFC";
      borderColor = "#CBD5E1";
      boxShadow = "0 4px 12px rgba(0, 0, 0, 0.1)";
      transform = "translateY(-50%) scale(1.05)";
    }

    if (isActive) {
      transform = "translateY(-50%) scale(0.95)";
      boxShadow = "0 1px 4px rgba(0, 0, 0, 0.1)";
    }

    return {
      width: "48px",
      height: "48px",
      borderRadius: "50%",
      backgroundColor: "#FFFFFF",
      border: "none",
      boxShadow: "0 2px 8px rgba(0, 0, 0, 0.15)",
      position: "absolute",
      top: "50%",
      transform,
      left: direction === "prev" ? "-24px" : "unset",
      right: direction === "next" ? "-24px" : "unset",
      zIndex: 20,
      cursor: "pointer",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      color: isHovered ? "#2563EB" : "#64748B",
      transition: "all 200ms ease",
      outline: "none",
    };
  };

  return (
    <button
      id={direction === "prev" ? "carousel-prev-btn" : "carousel-next-btn"}
      style={getButtonStyle()}
      onClick={onClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        setIsActive(false);
      }}
      onMouseDown={() => setIsActive(true)}
      onMouseUp={() => setIsActive(false)}
      onFocus={(e) => {
        e.currentTarget.style.outline = "3px solid #93C5FD";
        e.currentTarget.style.outlineOffset = "2px";
      }}
      onBlur={(e) => {
        e.currentTarget.style.outline = "none";
      }}
      aria-label={ariaLabel}
      type="button"
    >
      {direction === "prev" ? <ChevronLeftIcon /> : <ChevronRightIcon />}
    </button>
  );
}

// =============================================================================
// PAGINATION DOT COMPONENT
// =============================================================================
interface PaginationDotProps {
  index: number;
  isActive: boolean;
  onClick: () => void;
}

function PaginationDot({ index, isActive, onClick }: PaginationDotProps) {
  const [isHovered, setIsHovered] = useState(false);

  const getDotStyle = (): React.CSSProperties => {
    let backgroundColor = isActive ? "#2563EB" : "#D1D5DB";
    let size = isActive ? 12 : 10;
    let transform = "scale(1)";

    if (isHovered && !isActive) {
      backgroundColor = "#9CA3AF";
      transform = "scale(1.2)";
    }

    if (isHovered && isActive) {
      backgroundColor = "#1D4ED8";
    }

    return {
      width: `${size}px`,
      height: `${size}px`,
      borderRadius: "50%",
      backgroundColor,
      border: "none",
      cursor: "pointer",
      transition: "all 200ms ease",
      transform,
      outline: "none",
      padding: 0,
    };
  };

  return (
    <button
      style={getDotStyle()}
      onClick={onClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onFocus={(e) => {
        e.currentTarget.style.outline = "2px solid #93C5FD";
        e.currentTarget.style.outlineOffset = "2px";
      }}
      onBlur={(e) => {
        e.currentTarget.style.outline = "none";
      }}
      role="tab"
      aria-label={`Show testimonial ${index + 1}`}
      aria-selected={isActive}
      type="button"
    />
  );
}

// =============================================================================
// MAIN TESTIMONIAL CAROUSEL COMPONENT
// =============================================================================
export function TestimonialCarousel() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  const totalTestimonials = 5;
  const animationDuration = 300;

  const handleNext = useCallback(() => {
    if (isAnimating) return;
    setIsAnimating(true);
    setCurrentIndex((prev) => (prev + 1) % totalTestimonials);
    setTimeout(() => setIsAnimating(false), animationDuration);
  }, [isAnimating]);

  const handlePrev = useCallback(() => {
    if (isAnimating) return;
    setIsAnimating(true);
    setCurrentIndex((prev) => (prev - 1 + totalTestimonials) % totalTestimonials);
    setTimeout(() => setIsAnimating(false), animationDuration);
  }, [isAnimating]);

  // Auto-rotate carousel continuously
  useEffect(() => {
    const interval = setInterval(() => {
      if (!isAnimating) {
        setIsAnimating(true);
        setCurrentIndex((prev) => (prev + 1) % totalTestimonials);
        setTimeout(() => setIsAnimating(false), animationDuration);
      }
    }, 4000); // Rotate every 4 seconds

    return () => clearInterval(interval);
  }, [isAnimating, totalTestimonials, animationDuration]);

  // Calculate card positions - show 3 cards at once
  const getCardPosition = (index: number): "left" | "center" | "right" | "hidden" => {
    const prevIndex = (currentIndex - 1 + totalTestimonials) % totalTestimonials;
    const nextIndex = (currentIndex + 1) % totalTestimonials;
    
    if (index === currentIndex) return "center";
    if (index === prevIndex) return "left";
    if (index === nextIndex) return "right";
    return "hidden";
  };

  // Get the active testimonial's company
  const activeCompany = testimonials[currentIndex]?.company || "";
  
  // Map testimonial companies to header company names
  const companyNameMap: Record<string, string> = {
    "Adobe": "Vantage",
    "Salesforce": "CATALYST",
    "HubSpot": "Apex Analytics",
    "Shopify": "Meridian",
    "Stripe": "Novus"
  };

  // Get the header company name for the active testimonial
  const activeHeaderCompany = companyNameMap[activeCompany] || "";

  return (
    <section
      id="testimonials"
      className="testimonials-section"
      style={{
        backgroundColor: "#FFFFFF",
        paddingTop: "100px",
        paddingBottom: "100px",
        width: "100%",
        position: "relative",
        overflow: "hidden",
      }}
      role="region"
      aria-label="Customer testimonials"
      aria-roledescription="carousel"
    >
      {/* Inner Container */}
      <div
        className="testimonials-inner"
        style={{
          maxWidth: "1400px",
          margin: "0 auto",
          paddingLeft: "80px",
          paddingRight: "80px",
          position: "relative",
        }}
      >
        {/* Header Section with Title and Company Logos */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "120px",
            marginBottom: "80px",
          }}
        >
          {/* Title Section */}
          <div className="testimonials-title-wrapper" style={{ flexShrink: 0 }}>
            <h2
              className="testimonials-title"
              style={{
                fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
                fontSize: "56px",
                fontWeight: 600,
                lineHeight: 1.1,
                color: "#1E293B",
                letterSpacing: "-0.03em",
                margin: 0,
                whiteSpace: "nowrap",
              }}
            >
              See what our{" "}
              <span
                style={{
                  color: "#2563EB",
                }}
              >
                customers
              </span>{" "}
              say
            </h2>
          </div>

          {/* Company Logos Section */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "32px",
              color: "#1E293B",
              fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
              fontSize: "16px",
              fontWeight: 500,
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            <span style={{ color: activeHeaderCompany === "Vantage" ? "#2563EB" : "#1E293B" }}>
              Vantage
            </span>
            <span style={{ color: activeHeaderCompany === "CATALYST" ? "#2563EB" : "#1E293B" }}>
              CATALYST
            </span>
            <span style={{ color: activeHeaderCompany === "Apex Analytics" ? "#2563EB" : "#1E293B" }}>
              Apex Analytics
            </span>
            <span style={{ color: activeHeaderCompany === "Meridian" ? "#2563EB" : "#1E293B" }}>
              Meridian
            </span>
            <span style={{ color: activeHeaderCompany === "Novus" ? "#2563EB" : "#1E293B" }}>
              Novus
            </span>
          </div>
        </div>

        {/* Carousel Viewport */}
        <div
          className="testimonials-carousel-viewport"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
            width: "100%",
            margin: "0 auto",
            minHeight: "320px",
            overflow: "hidden",
          }}
        >
          {/* Card Container - Show 3 cards side by side */}
          <div
            className="testimonials-card-container"
            style={{
              position: "relative",
              display: "flex",
              alignItems: "stretch",
              justifyContent: "center",
              gap: "24px",
              width: "100%",
              maxWidth: "1600px",
              minHeight: "320px",
            }}
          >
            {testimonials.map((testimonial, index) => (
              <TestimonialCard
                key={testimonial.id}
                testimonial={testimonial}
                isActive={index === currentIndex}
                position={getCardPosition(index)}
              />
            ))}
          </div>
        </div>

        {/* Live Region for Screen Readers */}
        <div
          aria-live="polite"
          aria-atomic="true"
          style={{
            position: "absolute",
            width: "1px",
            height: "1px",
            padding: 0,
            margin: "-1px",
            overflow: "hidden",
            clip: "rect(0, 0, 0, 0)",
            whiteSpace: "nowrap",
            border: 0,
          }}
        >
          Showing testimonial {currentIndex + 1} of 5: {testimonials[currentIndex].name}, {testimonials[currentIndex].title} at {testimonials[currentIndex].company}
        </div>
      </div>

      {/* Responsive Styles */}
      <style>{`
        @media (max-width: 1023px) {
          .testimonials-inner {
            padding-left: 40px !important;
            padding-right: 40px !important;
          }
          
          .testimonials-card-container {
            gap: 16px !important;
          }
        }

        @media (max-width: 767px) {
          .testimonials-section {
            padding-top: 48px !important;
            padding-bottom: 48px !important;
            width: 100% !important;
            overflow-x: hidden !important;
          }

          .testimonials-inner {
            padding-left: 20px !important;
            padding-right: 20px !important;
            max-width: 100% !important;
          }

          .testimonials-inner > div:first-of-type {
            flex-direction: column !important;
            gap: 24px !important;
            align-items: flex-start !important;
            margin-bottom: 40px !important;
          }

          .testimonials-title {
            font-size: 28px !important;
            line-height: 1.25 !important;
            white-space: normal !important;
          }

          .testimonials-inner > div:first-of-type > div:last-child {
            flex-wrap: wrap !important;
            gap: 12px !important;
            font-size: 14px !important;
            width: 100% !important;
          }

          .testimonials-carousel-viewport {
            padding-left: 0 !important;
            padding-right: 0 !important;
            overflow: visible !important;
          }

          .testimonials-card-container {
            flex-direction: column !important;
            gap: 20px !important;
            align-items: center !important;
            width: 100% !important;
            max-width: 100% !important;
          }

          .testimonials-card-container > div {
            width: 100% !important;
            max-width: 100% !important;
            min-width: 0 !important;
            flex: 0 0 auto !important;
          }

          #testimonials .testimonial-card {
            width: 100% !important;
            max-width: 100% !important;
            min-width: 0 !important;
            padding: 24px 20px !important;
          }

          #testimonials .testimonial-quote {
            font-size: 16px !important;
            line-height: 1.6 !important;
          }

          #carousel-prev-btn,
          #carousel-next-btn {
            width: 44px !important;
            height: 44px !important;
            min-width: 44px !important;
            min-height: 44px !important;
            position: relative !important;
            left: auto !important;
            right: auto !important;
            top: auto !important;
            transform: none !important;
            margin: 8px !important;
          }

          /* Hide side cards on mobile, show only center */
          .testimonials-card-container > div[style*="opacity: 0.6"] {
            display: none !important;
          }

          /* Force all cards to full width on mobile */
          .testimonials-card-container > div {
            width: 100% !important;
            max-width: 100% !important;
            min-width: 0 !important;
            flex: 0 0 auto !important;
          }

          /* Show only center card on mobile */
          .testimonials-card-container > div[style*="opacity: 1"][style*="z-index: 10"] {
            display: flex !important;
            width: 100% !important;
          }

          .testimonials-card-container > div[style*="opacity: 0"] {
            display: none !important;
          }
        }
      `}</style>
    </section>
  );
}
