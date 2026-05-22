"use client";

import { Footer } from "@/components/layout/Footer";
import { useSearchParams, useRouter } from "next/navigation";
import Script from "next/script";
import { Suspense, useRef, useState, useCallback, useEffect } from "react";
import { CheckCircle2 } from "lucide-react";

declare global {
  interface Window {
    Cal?: (method: string, namespace: string, ...args: unknown[]) => void;
  }
}

// Partner logos for book-demo carousel — inherently small logos get larger height so they're legible
const bookDemoPartnerLogos = [
  { name: "Callaway", src: "/images/Callaway_1_transparent.png", height: "2rem" },
  { name: "Fresh Clean Threads", src: "/images/FreshCleanThreads_transparent.png", height: "4.25rem" },
  { name: "NordicTrack", src: "/images/Nordictrack_transparent.png", height: "4.25rem" },
  { name: "bareMinerals", src: "/images/Baremin_transparent.png", height: "4.25rem" },
  { name: "TUMI", src: "/images/TUMI_transparent.png", height: "1.5rem" },
  { name: "Pacsun", src: "/images/Pacsun_transparent.png", height: "2rem" },
];

function BookDemoContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const calTriggerRef = useRef<HTMLButtonElement>(null);
  const isSuccess = searchParams.get("success") === "true";

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [showCalConfirmation, setShowCalConfirmation] = useState(false);
  const [calReady, setCalReady] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const check = () => setIsMobile(typeof window !== "undefined" && window.innerWidth <= 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const initCal = useCallback(() => {
    if (typeof window !== "undefined" && window.Cal) {
      try {
        window.Cal("init", "skeldir-demo", { origin: "https://app.cal.com" });
        (window.Cal as { ns?: Record<string, (a: string, o: object) => void> }).ns?.["skeldir-demo"]?.("ui", {
          hideEventTypeDetails: false,
          layout: "month_view",
        });
        setCalReady(true);
      } catch {
        setCalReady(true);
      }
    }
  }, []);

  useEffect(() => {
    if (!calReady || typeof window === "undefined") return;
    const calNs = (window.Cal as { ns?: Record<string, (a: string, o: object) => void> } | undefined)?.ns?.["skeldir-demo"];
    if (!calNs) return;
    try {
      calNs("on", {
        action: "bookingSuccessful",
        callback: () => {
          setShowCalConfirmation(true);
          setTimeout(() => router.push("/"), 3000);
        },
      });
    } catch {
      // Event API may vary; user can still use Cal and we redirect from modal
    }
  }, [calReady, router]);

  const CAL_BASE = "https://cal.com/skeldir/skeldir-demo";
  const THANK_YOU_PATH = "/book-demo/thank-you";
  const getCalUrlMobile = useCallback(() => {
    if (typeof window === "undefined") return CAL_BASE;
    const origin = window.location.origin;
    const redirectUrl = encodeURIComponent(`${origin}${THANK_YOU_PATH}`);
    return `${CAL_BASE}?returnTo=${redirectUrl}&redirectUrl=${redirectUrl}`;
  }, []);

  const openCalPopup = useCallback(() => {
    if (isMobile) {
      window.location.href = getCalUrlMobile();
      return;
    }
    const trigger = calTriggerRef.current;
    if (trigger && calReady) {
      trigger.click();
    } else {
      window.open(`${CAL_BASE}?overlayCalendar=true`, "cal-com-booking", "width=600,height=700,scrollbars=yes,resizable=yes");
    }
  }, [calReady, isMobile, getCalUrlMobile]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      const form = formRef.current;
      if (!form) return;
      setSubmitError(null);
      if (!form.reportValidity()) return;
      setSubmitting(true);
      const formData = new FormData(form);
      const body = new URLSearchParams(
        Array.from(formData.entries()) as [string, string][]
      ).toString();
      openCalPopup();
      try {
        await fetch("/book-demo", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body,
        });
      } catch {
        setSubmitError("Form could not be saved; your booking will still work.");
      } finally {
        setSubmitting(false);
      }
    },
    [openCalPopup]
  );

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <Script
        src="https://app.cal.com/embed/embed.js"
        strategy="afterInteractive"
        onLoad={initCal}
      />
      {/* Cal.com trigger — opened when user submits form; off-screen but clickable for programmatic open */}
      <button
        ref={calTriggerRef}
        type="button"
        data-cal-link="skeldir/skeldir-demo"
        data-cal-namespace="skeldir-demo"
        data-cal-config='{"layout":"month_view","useSlotsViewOnSmallScreen":"true"}'
        aria-hidden
        tabIndex={-1}
        style={{
          position: "absolute",
          left: -9999,
          width: 1,
          height: 1,
          opacity: 0,
          overflow: "hidden",
          clip: "rect(0,0,0,0)",
        }}
      />

      <main className="flex-grow pt-8">
        {/* Hero Section with Split Layout */}
        <section
          className="book-demo-hero-section"
          style={{
            minHeight: "calc(100vh - 80px)",
            display: "flex",
            alignItems: "flex-start",
            paddingTop: "40px",
            background: "linear-gradient(135deg, #F8FAFC 0%, #FFFFFF 50%, #F1F5F9 100%)",
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* Subtle background pattern */}
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundImage: `radial-gradient(circle at 1px 1px, rgba(0,0,0,0.03) 1px, transparent 0)`,
              backgroundSize: "40px 40px",
              pointerEvents: "none",
            }}
          />

          <div
            className="book-demo-container container mx-auto px-4 md:px-6 lg:px-8"
            style={{
              maxWidth: "1280px",
              position: "relative",
              zIndex: 1,
            }}
          >
            <div
              className="book-demo-grid"
              style={{
                display: "grid",
                gridTemplateColumns: "1fr",
                gap: "48px",
                alignItems: "center",
                padding: "20px 0 80px",
              }}
            >
              {/* Left Column - Value Proposition */}
              <div
                className="value-prop-column"
                style={{
                  maxWidth: "560px",
                }}
              >
                {/* Badge — button style, transparent except border and text */}
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "52px",
                    padding: "0 24px",
                    backgroundColor: "transparent",
                    border: "1px solid #2563EB",
                    borderRadius: "10px",
                    marginBottom: "24px",
                    marginLeft: "-10vw",
                  }}
                >
                  <span
                    style={{
                      fontSize: "16px",
                      fontWeight: 700,
                      color: "#2563EB",
                      fontFamily: "Inter, sans-serif",
                    }}
                  >
                    DEMO SKELDIR TODAY
                  </span>
                </div>

                {/* Main Headline — exactly 2 lines, no wrapping within either line */}
                <h1
                  style={{
                    fontSize: "clamp(36px, 6.5vw, 56px)",
                    fontWeight: 800,
                    color: "#0F172A",
                    lineHeight: 1.12,
                    marginBottom: "24px",
                    marginLeft: "-10vw",
                    fontFamily: "'DM Sans', sans-serif",
                    letterSpacing: "-0.03em",
                    textAlign: "left",
                  }}
                >
                  <span style={{ display: "block", whiteSpace: "nowrap" }}>Grow faster with intelligence that</span>
                  <span style={{ display: "block", whiteSpace: "nowrap" }}>exposes the truth in your ad data.</span>
                </h1>

                {/* Content below headline — aligned vertically with headline */}
                <div style={{ marginLeft: "-10vw" }}>
                  {/* Subheadline */}
                  <p
                    style={{
                      fontSize: "18px",
                      fontWeight: 400,
                      color: "#64748B",
                      lineHeight: 1.6,
                      marginBottom: "40px",
                      fontFamily: "Inter, sans-serif",
                    }}
                  >
                    Skeldir replaces manual platform exports, spreadsheet reconciliation, and conflicting revenue reports by verifying ad platform claims against actual revenue — giving you statistical confidence ranges that turn guesswork into defensible budget decisions all in one unified dashboard
                  </p>

                  {/* Bullet list (product-hero style) */}
                  <div
                    className="book-demo-bullets"
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                      margin: "0 0 48px 0",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
                      <svg width="20" height="20" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0, marginTop: "2px" }}>
                        <defs>
                          <linearGradient id="book-demo-arrow-1" x1="0%" y1="0%" x2="100%" y2="100%" gradientUnits="userSpaceOnUse">
                            <stop offset="0%" stopColor="#4F46E5" />
                            <stop offset="50%" stopColor="#A855F7" />
                            <stop offset="100%" stopColor="#EC4899" />
                          </linearGradient>
                        </defs>
                        <path d="M4 3L8 6L4 9" stroke="url(#book-demo-arrow-1)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                      </svg>
                      <span style={{ fontSize: "18px", lineHeight: 1.45, color: "#4B5563", fontFamily: "Inter, sans-serif" }}>
                        Know which ads actually drive revenue, not just clicks
                      </span>
                    </div>
                    <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
                      <svg width="20" height="20" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0, marginTop: "2px" }}>
                        <defs>
                          <linearGradient id="book-demo-arrow-2" x1="0%" y1="0%" x2="100%" y2="100%" gradientUnits="userSpaceOnUse">
                            <stop offset="0%" stopColor="#4F46E5" />
                            <stop offset="50%" stopColor="#A855F7" />
                            <stop offset="100%" stopColor="#EC4899" />
                          </linearGradient>
                        </defs>
                        <path d="M4 3L8 6L4 9" stroke="url(#book-demo-arrow-2)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                      </svg>
                      <span style={{ fontSize: "18px", lineHeight: 1.45, color: "#4B5563", fontFamily: "Inter, sans-serif" }}>
                        One dashboard to manage all your clients without technical expertise
                      </span>
                    </div>
                    <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
                      <svg width="20" height="20" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0, marginTop: "2px" }}>
                        <defs>
                          <linearGradient id="book-demo-arrow-3" x1="0%" y1="0%" x2="100%" y2="100%" gradientUnits="userSpaceOnUse">
                            <stop offset="0%" stopColor="#4F46E5" />
                            <stop offset="50%" stopColor="#A855F7" />
                            <stop offset="100%" stopColor="#EC4899" />
                          </linearGradient>
                        </defs>
                        <path d="M4 3L8 6L4 9" stroke="url(#book-demo-arrow-3)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                      </svg>
                      <span style={{ fontSize: "18px", lineHeight: 1.45, color: "#4B5563", fontFamily: "Inter, sans-serif" }}>
                        Reliable numbers backed by your actual sales data
                      </span>
                    </div>
                    <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
                      <svg width="20" height="20" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0, marginTop: "2px" }}>
                        <defs>
                          <linearGradient id="book-demo-arrow-4" x1="0%" y1="0%" x2="100%" y2="100%" gradientUnits="userSpaceOnUse">
                            <stop offset="0%" stopColor="#4F46E5" />
                            <stop offset="50%" stopColor="#A855F7" />
                            <stop offset="100%" stopColor="#EC4899" />
                          </linearGradient>
                        </defs>
                        <path d="M4 3L8 6L4 9" stroke="url(#book-demo-arrow-4)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                      </svg>
                      <span style={{ fontSize: "18px", lineHeight: 1.45, color: "#4B5563", fontFamily: "Inter, sans-serif" }}>
                        Deploy for new clients faster than your competitors can send a proposal
                      </span>
                    </div>
                  </div>

                  {/* Trust Indicators — smaller partner logo carousel */}
                  <div>
                    <div
                      className="trust-logos book-demo-partner-logos-container"
                      style={{
                        width: "100%",
                        overflow: "hidden",
                        position: "relative",
                      }}
                    >
                      <div className="book-demo-logo-carousel-track">
                        {[...bookDemoPartnerLogos, ...bookDemoPartnerLogos].map((logo, index) => (
                          <img
                            key={`${logo.name}-${index}`}
                            src={logo.src}
                            alt={logo.name}
                            loading="lazy"
                            decoding="async"
                            style={{
                              height: logo.height,
                              width: "auto",
                              maxWidth: "140px",
                              objectFit: "contain",
                              filter: "grayscale(100%)",
                              opacity: 0.7,
                              flexShrink: 0,
                            }}
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Column - Form Card */}
              <div
                className="form-column"
                style={{
                  width: "100%",
                  maxWidth: "480px",
                  justifySelf: "end",
                }}
              >
                <div
                  style={{
                    backgroundColor: "rgba(255, 255, 255, 0.35)",
                    borderRadius: "20px",
                    padding: "40px",
                    boxShadow: "0 2px 12px rgba(0, 0, 0, 0.03)",
                    border: "1px solid rgba(0, 0, 0, 0.06)",
                    backdropFilter: "blur(8px)",
                  }}
                >
                  {isSuccess ? (
                    /* Success State */
                    <div
                      style={{
                        textAlign: "center",
                        padding: "40px 20px",
                      }}
                    >
                      <div
                        style={{
                          width: "72px",
                          height: "72px",
                          backgroundColor: "rgba(34, 197, 94, 0.1)",
                          borderRadius: "50%",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          margin: "0 auto 24px",
                        }}
                      >
                        <CheckCircle2 size={36} color="#22C55E" />
                      </div>
                      <h2
                        style={{
                          fontSize: "24px",
                          fontWeight: 700,
                          color: "#0F172A",
                          marginBottom: "12px",
                          fontFamily: "'DM Sans', sans-serif",
                        }}
                      >
                        Request Received
                      </h2>
                      <p
                        style={{
                          fontSize: "16px",
                          color: "#64748B",
                          lineHeight: 1.6,
                          marginBottom: "32px",
                          fontFamily: "Inter, sans-serif",
                        }}
                      >
                        We'll contact you within 24 hours to schedule your personalized
                        strategy session.
                      </p>
                      <div
                        style={{
                          padding: "16px 20px",
                          backgroundColor: "#F8FAFC",
                          borderRadius: "12px",
                          border: "1px solid #E2E8F0",
                        }}
                      >
                        <p
                          style={{
                            fontSize: "14px",
                            color: "#64748B",
                            fontFamily: "Inter, sans-serif",
                          }}
                        >
                          Questions in the meantime?
                        </p>
                        <a
                          href="mailto:info@synergyscape.io"
                          style={{
                            fontSize: "15px",
                            fontWeight: 600,
                            color: "#2563EB",
                            textDecoration: "none",
                            fontFamily: "Inter, sans-serif",
                          }}
                        >
                          info@synergyscape.io
                        </a>
                      </div>
                    </div>
                  ) : (
                    /* Form State */
                    <>
                      {/* Form Header */}
                      <div style={{ marginBottom: "32px" }}>
                        <h2
                          style={{
                            fontSize: "24px",
                            fontWeight: 700,
                            color: "#0F172A",
                            marginBottom: "8px",
                            fontFamily: "'DM Sans', sans-serif",
                          }}
                        >
                          Tell us about your business
                        </h2>
                        <p
                          style={{
                            fontSize: "15px",
                            color: "#64748B",
                            fontFamily: "Inter, sans-serif",
                          }}
                        >
                          Get a personalized demo of our attribution platform.
                        </p>
                      </div>

                      {/* Form: AJAX submit, then open Cal.com popup on success */}
                      <form
                        ref={formRef}
                        name="skeldir-demo-request"
                        data-netlify="true"
                        data-netlify-honeypot="bot-field"
                        onSubmit={handleSubmit}
                      >
                        {/* Hidden field for Netlify form detection */}
                        <input type="hidden" name="form-name" value="skeldir-demo-request" />

                        {/* Honeypot field for spam prevention */}
                        <p style={{ display: "none" }}>
                          <label>
                            Don't fill this out if you're human:
                            <input name="bot-field" />
                          </label>
                        </p>

                        {/* Name Row */}
                        <div
                          style={{
                            display: "grid",
                            gridTemplateColumns: "1fr 1fr",
                            gap: "16px",
                            marginBottom: "16px",
                          }}
                        >
                          {/* First Name */}
                          <div>
                            <label
                              htmlFor="first-name"
                              style={{
                                display: "block",
                                fontSize: "14px",
                                fontWeight: 500,
                                color: "#374151",
                                marginBottom: "6px",
                                fontFamily: "Inter, sans-serif",
                              }}
                            >
                              First Name
                            </label>
                            <input
                              type="text"
                              id="first-name"
                              name="first-name"
                              required
                              placeholder="Jane"
                              style={{
                                width: "100%",
                                height: "46px",
                                padding: "0 14px",
                                fontSize: "15px",
                                fontFamily: "Inter, sans-serif",
                                border: "1px solid #D1D5DB",
                                borderRadius: "8px",
                                backgroundColor: "#FFFFFF",
                                color: "#0F172A",
                                outline: "none",
                                transition: "border-color 150ms ease, box-shadow 150ms ease",
                              }}
                              onFocus={(e) => {
                                e.currentTarget.style.borderColor = "#2563EB";
                                e.currentTarget.style.boxShadow = "0 0 0 3px rgba(37, 99, 235, 0.15)";
                              }}
                              onBlur={(e) => {
                                e.currentTarget.style.borderColor = "#D1D5DB";
                                e.currentTarget.style.boxShadow = "none";
                              }}
                            />
                          </div>

                          {/* Last Name */}
                          <div>
                            <label
                              htmlFor="last-name"
                              style={{
                                display: "block",
                                fontSize: "14px",
                                fontWeight: 500,
                                color: "#374151",
                                marginBottom: "6px",
                                fontFamily: "Inter, sans-serif",
                              }}
                            >
                              Last Name
                            </label>
                            <input
                              type="text"
                              id="last-name"
                              name="last-name"
                              required
                              placeholder="Smith"
                              style={{
                                width: "100%",
                                height: "46px",
                                padding: "0 14px",
                                fontSize: "15px",
                                fontFamily: "Inter, sans-serif",
                                border: "1px solid #D1D5DB",
                                borderRadius: "8px",
                                backgroundColor: "#FFFFFF",
                                color: "#0F172A",
                                outline: "none",
                                transition: "border-color 150ms ease, box-shadow 150ms ease",
                              }}
                              onFocus={(e) => {
                                e.currentTarget.style.borderColor = "#2563EB";
                                e.currentTarget.style.boxShadow = "0 0 0 3px rgba(37, 99, 235, 0.15)";
                              }}
                              onBlur={(e) => {
                                e.currentTarget.style.borderColor = "#D1D5DB";
                                e.currentTarget.style.boxShadow = "none";
                              }}
                            />
                          </div>
                        </div>

                        {/* Work Email */}
                        <div style={{ marginBottom: "16px" }}>
                          <label
                            htmlFor="work-email"
                            style={{
                              display: "block",
                              fontSize: "14px",
                              fontWeight: 500,
                              color: "#374151",
                              marginBottom: "6px",
                              fontFamily: "Inter, sans-serif",
                            }}
                          >
                            Work Email
                          </label>
                          <input
                            type="email"
                            id="work-email"
                            name="work-email"
                            required
                            placeholder="jane@company.com"
                            style={{
                              width: "100%",
                              height: "46px",
                              padding: "0 14px",
                              fontSize: "15px",
                              fontFamily: "Inter, sans-serif",
                              border: "1px solid #D1D5DB",
                              borderRadius: "8px",
                              backgroundColor: "#FFFFFF",
                              color: "#0F172A",
                              outline: "none",
                              transition: "border-color 150ms ease, box-shadow 150ms ease",
                            }}
                            onFocus={(e) => {
                              e.currentTarget.style.borderColor = "#2563EB";
                              e.currentTarget.style.boxShadow = "0 0 0 3px rgba(37, 99, 235, 0.15)";
                            }}
                            onBlur={(e) => {
                              e.currentTarget.style.borderColor = "#D1D5DB";
                              e.currentTarget.style.boxShadow = "none";
                            }}
                          />
                        </div>

                        {/* Company Name */}
                        <div style={{ marginBottom: "16px" }}>
                          <label
                            htmlFor="company-name"
                            style={{
                              display: "block",
                              fontSize: "14px",
                              fontWeight: 500,
                              color: "#374151",
                              marginBottom: "6px",
                              fontFamily: "Inter, sans-serif",
                            }}
                          >
                            Company Name
                          </label>
                          <input
                            type="text"
                            id="company-name"
                            name="company-name"
                            required
                            placeholder="Acme Inc."
                            style={{
                              width: "100%",
                              height: "46px",
                              padding: "0 14px",
                              fontSize: "15px",
                              fontFamily: "Inter, sans-serif",
                              border: "1px solid #D1D5DB",
                              borderRadius: "8px",
                              backgroundColor: "#FFFFFF",
                              color: "#0F172A",
                              outline: "none",
                              transition: "border-color 150ms ease, box-shadow 150ms ease",
                            }}
                            onFocus={(e) => {
                              e.currentTarget.style.borderColor = "#2563EB";
                              e.currentTarget.style.boxShadow = "0 0 0 3px rgba(37, 99, 235, 0.15)";
                            }}
                            onBlur={(e) => {
                              e.currentTarget.style.borderColor = "#D1D5DB";
                              e.currentTarget.style.boxShadow = "none";
                            }}
                          />
                        </div>

                        {/* Monthly Ad Spend */}
                        <div style={{ marginBottom: "16px" }}>
                          <label
                            htmlFor="monthly-ad-spend"
                            style={{
                              display: "block",
                              fontSize: "14px",
                              fontWeight: 500,
                              color: "#374151",
                              marginBottom: "6px",
                              fontFamily: "Inter, sans-serif",
                            }}
                          >
                            Monthly Ad Spend
                          </label>
                          <select
                            id="monthly-ad-spend"
                            name="monthly-ad-spend"
                            required
                            defaultValue=""
                            style={{
                              width: "100%",
                              height: "46px",
                              padding: "0 14px",
                              fontSize: "15px",
                              fontFamily: "Inter, sans-serif",
                              border: "1px solid #D1D5DB",
                              borderRadius: "8px",
                              backgroundColor: "#FFFFFF",
                              color: "#0F172A",
                              outline: "none",
                              cursor: "pointer",
                              appearance: "none",
                              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2364748B' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E")`,
                              backgroundRepeat: "no-repeat",
                              backgroundPosition: "right 14px center",
                              paddingRight: "40px",
                              transition: "border-color 150ms ease, box-shadow 150ms ease",
                            }}
                            onFocus={(e) => {
                              e.currentTarget.style.borderColor = "#2563EB";
                              e.currentTarget.style.boxShadow = "0 0 0 3px rgba(37, 99, 235, 0.15)";
                            }}
                            onBlur={(e) => {
                              e.currentTarget.style.borderColor = "#D1D5DB";
                              e.currentTarget.style.boxShadow = "none";
                            }}
                          >
                            <option value="" disabled>
                              Select your monthly spend
                            </option>
                            <option value="<$50K">&lt;$50K</option>
                            <option value="$50K-$150K">$50K-$150K</option>
                            <option value="$150K-$500K">$150K-$500K</option>
                            <option value="$500K+">$500K+</option>
                          </select>
                        </div>

                        {/* Attribution Challenge */}
                        <div style={{ marginBottom: "16px" }}>
                          <label
                            htmlFor="attribution-challenge"
                            style={{
                              display: "block",
                              fontSize: "14px",
                              fontWeight: 500,
                              color: "#374151",
                              marginBottom: "6px",
                              fontFamily: "Inter, sans-serif",
                            }}
                          >
                            Primary Attribution Challenge
                          </label>
                          <select
                            id="attribution-challenge"
                            name="attribution-challenge"
                            required
                            defaultValue=""
                            style={{
                              width: "100%",
                              height: "46px",
                              padding: "0 14px",
                              fontSize: "15px",
                              fontFamily: "Inter, sans-serif",
                              border: "1px solid #D1D5DB",
                              borderRadius: "8px",
                              backgroundColor: "#FFFFFF",
                              color: "#0F172A",
                              outline: "none",
                              cursor: "pointer",
                              appearance: "none",
                              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2364748B' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E")`,
                              backgroundRepeat: "no-repeat",
                              backgroundPosition: "right 14px center",
                              paddingRight: "40px",
                              transition: "border-color 150ms ease, box-shadow 150ms ease",
                            }}
                            onFocus={(e) => {
                              e.currentTarget.style.borderColor = "#2563EB";
                              e.currentTarget.style.boxShadow = "0 0 0 3px rgba(37, 99, 235, 0.15)";
                            }}
                            onBlur={(e) => {
                              e.currentTarget.style.borderColor = "#D1D5DB";
                              e.currentTarget.style.boxShadow = "none";
                            }}
                          >
                            <option value="" disabled>
                              Select your biggest challenge
                            </option>
                            <option value="Conflicting platform data">Conflicting platform data</option>
                            <option value="Manual reconciliation taking too long">Manual reconciliation taking too long</option>
                            <option value="Don't trust current numbers">Don't trust current numbers</option>
                            <option value="CFO demanding ROI proof">CFO demanding ROI proof</option>
                          </select>
                        </div>

                        {/* Referral Source */}
                        <div style={{ marginBottom: "28px" }}>
                          <label
                            htmlFor="referral-source"
                            style={{
                              display: "block",
                              fontSize: "14px",
                              fontWeight: 500,
                              color: "#374151",
                              marginBottom: "6px",
                              fontFamily: "Inter, sans-serif",
                            }}
                          >
                            How did you hear about us?{" "}
                            <span style={{ color: "#94A3B8", fontWeight: 400 }}>(optional)</span>
                          </label>
                          <select
                            id="referral-source"
                            name="referral-source"
                            defaultValue=""
                            style={{
                              width: "100%",
                              height: "46px",
                              padding: "0 14px",
                              fontSize: "15px",
                              fontFamily: "Inter, sans-serif",
                              border: "1px solid #D1D5DB",
                              borderRadius: "8px",
                              backgroundColor: "#FFFFFF",
                              color: "#0F172A",
                              outline: "none",
                              cursor: "pointer",
                              appearance: "none",
                              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2364748B' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E")`,
                              backgroundRepeat: "no-repeat",
                              backgroundPosition: "right 14px center",
                              paddingRight: "40px",
                              transition: "border-color 150ms ease, box-shadow 150ms ease",
                            }}
                            onFocus={(e) => {
                              e.currentTarget.style.borderColor = "#2563EB";
                              e.currentTarget.style.boxShadow = "0 0 0 3px rgba(37, 99, 235, 0.15)";
                            }}
                            onBlur={(e) => {
                              e.currentTarget.style.borderColor = "#D1D5DB";
                              e.currentTarget.style.boxShadow = "none";
                            }}
                          >
                            <option value="">Select an option</option>
                            <option value="Search">Search</option>
                            <option value="LinkedIn">LinkedIn</option>
                            <option value="Referral">Referral</option>
                            <option value="Agency partner">Agency partner</option>
                            <option value="Other">Other</option>
                          </select>
                        </div>

                        {submitError && (
                          <p
                            style={{
                              fontSize: "14px",
                              color: "#DC2626",
                              marginBottom: "12px",
                              fontFamily: "Inter, sans-serif",
                            }}
                          >
                            {submitError}
                          </p>
                        )}
                        {/* Submit Button — AJAX submit, then Cal.com opens on success */}
                        <button
                          type="submit"
                          disabled={submitting}
                          style={{
                            width: "100%",
                            height: "52px",
                            backgroundColor: submitting ? "#93C5FD" : "#2563EB",
                            color: "#FFFFFF",
                            fontSize: "16px",
                            fontWeight: 700,
                            fontFamily: "Inter, sans-serif",
                            border: "none",
                            borderRadius: "10px",
                            cursor: submitting ? "wait" : "pointer",
                            boxShadow: "0 4px 14px rgba(37, 99, 235, 0.35)",
                            transition: "all 200ms ease",
                          }}
                          onMouseEnter={(e) => {
                            if (submitting) return;
                            e.currentTarget.style.backgroundColor = "#1D4ED8";
                            e.currentTarget.style.boxShadow = "0 6px 20px rgba(37, 99, 235, 0.45)";
                            e.currentTarget.style.transform = "translateY(-1px)";
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = submitting ? "#93C5FD" : "#2563EB";
                            e.currentTarget.style.boxShadow = "0 4px 14px rgba(37, 99, 235, 0.35)";
                            e.currentTarget.style.transform = "translateY(0)";
                          }}
                          onMouseDown={(e) => {
                            e.currentTarget.style.transform = "translateY(0)";
                          }}
                        >
                          {submitting ? "Submitting…" : "Book Your Demo"}
                        </button>

                        {/* Privacy Note */}
                        <p
                          style={{
                            fontSize: "12px",
                            color: "#94A3B8",
                            textAlign: "center",
                            marginTop: "16px",
                            fontFamily: "Inter, sans-serif",
                            lineHeight: 1.5,
                          }}
                        >
                          By submitting, you agree to our{" "}
                          <a
                            href="/privacy"
                            style={{ color: "#64748B", textDecoration: "underline" }}
                          >
                            Privacy Policy
                          </a>
                          . We'll never share your information.
                        </p>
                      </form>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Confirmation modal after Cal.com booking — "You will receive a confirmation email shortly", then redirect home */}
      {showCalConfirmation && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="cal-confirmation-title"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "rgba(15, 23, 42, 0.6)",
            padding: "24px",
          }}
          onClick={() => router.push("/")}
        >
          <div
            style={{
              backgroundColor: "#FFFFFF",
              borderRadius: "16px",
              padding: "32px",
              maxWidth: "400px",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
              textAlign: "center",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                width: "56px",
                height: "56px",
                backgroundColor: "rgba(34, 197, 94, 0.1)",
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 20px",
              }}
            >
              <CheckCircle2 size={28} color="#22C55E" />
            </div>
            <h2
              id="cal-confirmation-title"
              style={{
                fontSize: "20px",
                fontWeight: 700,
                color: "#0F172A",
                marginBottom: "12px",
                fontFamily: "'DM Sans', sans-serif",
              }}
            >
              You're all set
            </h2>
            <p
              style={{
                fontSize: "16px",
                color: "#64748B",
                lineHeight: 1.6,
                marginBottom: "24px",
                fontFamily: "Inter, sans-serif",
              }}
            >
              You will receive a confirmation email shortly.
            </p>
            <button
              type="button"
              onClick={() => router.push("/")}
              style={{
                width: "100%",
                height: "48px",
                backgroundColor: "#2563EB",
                color: "#FFFFFF",
                fontSize: "16px",
                fontWeight: 600,
                fontFamily: "Inter, sans-serif",
                border: "none",
                borderRadius: "10px",
                cursor: "pointer",
              }}
            >
              Return to home
            </button>
          </div>
        </div>
      )}

      <Footer />

      {/* Responsive Styles */}
      <style>{`
        /* Book-demo partner logo carousel (smaller iteration of PartnerLogos) */
        @keyframes book-demo-scroll-logos {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .book-demo-partner-logos-container {
          margin-top: 0;
        }
        .book-demo-logo-carousel-track {
          display: flex;
          align-items: center;
          gap: 2rem;
          animation: book-demo-scroll-logos 35s linear infinite;
          width: max-content;
        }
        .book-demo-logo-carousel-track img {
          flex-shrink: 0;
        }

        /* Desktop Layout (≥1024px) */
        @media (min-width: 1024px) {
          .book-demo-grid {
            grid-template-columns: 55% 45% !important;
            gap: 64px !important;
            padding: 20px 0 100px !important;
          }

          .value-prop-column {
            max-width: 560px !important;
          }

          .form-column {
            max-width: 480px !important;
            justify-self: end !important;
          }
        }

        /* Large Desktop (≥1280px) */
        @media (min-width: 1280px) {
          .book-demo-grid {
            gap: 80px !important;
          }
        }

        /* Tablet (768px - 1023px) */
        @media (min-width: 768px) and (max-width: 1023px) {
          .book-demo-grid {
            grid-template-columns: 1fr !important;
            gap: 48px !important;
            padding: 20px 0 80px !important;
          }

          .value-prop-column {
            max-width: 100% !important;
            text-align: center !important;
          }

          .value-prop-column > div:first-child {
            display: flex !important;
            justify-content: center !important;
          }

          .book-demo-bullets {
            max-width: 500px !important;
            margin-left: auto !important;
            margin-right: auto !important;
          }

          .trust-logos {
            justify-content: center !important;
          }

          .form-column {
            max-width: 520px !important;
            margin: 0 auto !important;
            justify-self: center !important;
          }
        }

        /* Mobile (≤767px) — aligned with rest of site */
        @media (max-width: 767px) {
          .book-demo-hero-section {
            padding-top: 48px !important;
            min-height: auto !important;
            align-items: flex-start !important;
          }

          .book-demo-container {
            padding-left: 16px !important;
            padding-right: 16px !important;
          }

          .book-demo-grid {
            grid-template-columns: 1fr !important;
            gap: 32px !important;
            padding: 24px 0 48px !important;
          }

          .value-prop-column {
            max-width: 100% !important;
            text-align: center !important;
          }

          .value-prop-column > div:first-child {
            display: flex !important;
            justify-content: center !important;
            margin-left: 0 !important;
          }

          .value-prop-column h1 {
            margin-left: 0 !important;
            text-align: center !important;
          }

          .value-prop-column h1 span {
            white-space: normal !important;
          }

          .value-prop-column h1 + div {
            margin-left: 0 !important;
            text-align: center !important;
          }

          .value-prop-column div:has(.trust-logos) {
            display: none !important;
          }

          .form-column {
            max-width: 100% !important;
            justify-self: center !important;
          }

          .form-column > div {
            padding: 24px 16px !important;
            border-radius: 16px !important;
          }

          /* Stack name fields on mobile */
          .form-column form > div:first-of-type {
            grid-template-columns: 1fr !important;
          }
        }

        /* Focus visible for accessibility */
        input:focus-visible,
        select:focus-visible,
        button:focus-visible {
          outline: 2px solid #2563EB !important;
          outline-offset: 2px !important;
        }

        /* Placeholder styling */
        input::placeholder {
          color: #9CA3AF;
        }

        /* Select disabled option styling */
        select option[value=""][disabled] {
          color: #9CA3AF;
        }
      `}</style>
    </div>
  );
}

export default function BookDemoPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-white">
          <div
            style={{
              width: "40px",
              height: "40px",
              border: "3px solid #E5E7EB",
              borderTopColor: "#2563EB",
              borderRadius: "50%",
              animation: "spin 0.8s linear infinite",
            }}
          />
          <style>{`
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      }
    >
      <BookDemoContent />
    </Suspense>
  );
}
