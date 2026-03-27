"use client";

import { useState, useRef, useCallback } from "react";

// ============================================================================
// INTERACTIVE PRODUCT DEMO COMPONENT
// YouTube embed: plays in-page so users are not sent to youtube.com
// State Machine: READY_TO_PLAY → PLAYING → ERROR
// ============================================================================

const YOUTUBE_VIDEO_ID = "DHEyowvZ_9E";
const YOUTUBE_EMBED_URL = `https://www.youtube.com/embed/${YOUTUBE_VIDEO_ID}`;
const YOUTUBE_THUMBNAIL_URL = `https://img.youtube.com/vi/${YOUTUBE_VIDEO_ID}/maxresdefault.jpg`;
const YOUTUBE_THUMBNAIL_FALLBACK = `https://img.youtube.com/vi/${YOUTUBE_VIDEO_ID}/hqdefault.jpg`;

type DemoState = "READY_TO_PLAY" | "PLAYING" | "ERROR";

// =============================================================================
// PLAY ICON SVG
// =============================================================================
function PlayIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      style={{
        width: "32px",
        height: "32px",
        fill: "#FFFFFF",
        marginLeft: "4px",
      }}
    >
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

// =============================================================================
// TOOLTIP COMPONENT
// =============================================================================
interface TooltipProps {
  number: string;
  title: string;
  subtitle: string;
  badgeTop: number;
  badgeLeft: number;
  calloutTop: number;
  calloutLeft: number;
  lineX1: number;
  lineY1: number;
  lineX2: number;
  lineY2: number;
  isVisible: boolean;
}

function Tooltip({
  number,
  title,
  subtitle,
  badgeTop,
  badgeLeft,
  calloutTop,
  calloutLeft,
  lineX1,
  lineY1,
  lineX2,
  lineY2,
  isVisible,
}: TooltipProps) {
  return (
    <div
      className="demo-tooltip-overlay"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        opacity: isVisible ? 1 : 0,
        transition: "opacity 50ms ease-out",
        display: isVisible ? "block" : "none",
      }}
    >

      {/* Callout Box */}
      <div
        className="tooltip-callout"
        style={{
          position: "absolute",
          top: `${calloutTop}px`,
          left: `${calloutLeft}px`,
          width: "220px",
          padding: "16px 20px",
          backgroundColor: "#FFFFFF",
          border: "2px solid #2563EB",
          borderRadius: "12px",
          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.1)",
          zIndex: 11,
        }}
      >
        <div
          className="tooltip-title"
          style={{
            fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            fontSize: "16px",
            fontWeight: 600,
            color: "#0F172A",
            marginBottom: "4px",
          }}
        >
          {title}
        </div>
        <div
          className="tooltip-subtitle"
          style={{
            fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            fontSize: "14px",
            fontWeight: 400,
            color: "#64748B",
            lineHeight: 1.4,
          }}
        >
          {subtitle}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT EXPORT
// =============================================================================
export function InteractiveDemo() {
  const [state, setState] = useState<DemoState>("READY_TO_PLAY");
  const containerRef = useRef<HTMLDivElement>(null);

  // Tooltip visibility based on state
  const tooltipsVisible = state === "READY_TO_PLAY";

  // Handle play click: show YouTube embed (plays in-page, no redirect)
  const handlePlayClick = useCallback(() => {
    if (state !== "READY_TO_PLAY") return;
    setState("PLAYING");
  }, [state]);

  // No-op for container click when playing (YouTube iframe has its own controls)
  const handleVideoClick = useCallback(() => {}, []);

  // Transition to error state (e.g. if embed fails to load)
  const transitionToErrorState = useCallback((error: Error) => {
    console.warn("[Skeldir Demo] Error state:", error);
    setState("ERROR");
  }, []);

  // Reset to ready state (from error)
  const resetToReadyState = useCallback(() => {
    setState("READY_TO_PLAY");
  }, []);

  return (
    <section
      id="product-demo-section"
      role="region"
      aria-labelledby="demo-section-title"
      style={{
        width: "100%",
        padding: "80px 48px",
        backgroundColor: "#FFFFFF",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        overflow: "visible",
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
          background: "linear-gradient(to bottom, rgba(255, 255, 255, 1) 0%, rgba(255, 255, 255, 1) 100%)",
          pointerEvents: "none",
          zIndex: 1,
        }}
      />
      <div
        style={{
          width: "100%",
          maxWidth: "1440px",
          margin: "0 auto",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          position: "relative",
          zIndex: 2,
      }}
    >
      {/* Section Title */}
      <h2
        id="demo-section-title"
        style={{
          fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
          fontSize: "48px",
          fontWeight: 700,
          lineHeight: 1.2,
          letterSpacing: "-0.02em",
          color: "#0F172A",
          textAlign: "center",
          margin: "0 0 16px 0",
        }}
      >
        See Skeldir in Action
      </h2>

      {/* Section Subtitle */}
      <p
        id="demo-section-subtitle"
        style={{
          fontFamily: "Inter, -apple-system, sans-serif",
          fontSize: "18px",
          fontWeight: 400,
          lineHeight: 1.6,
          color: "#64748B",
          textAlign: "center",
          margin: "0 0 48px 0",
        }}
      >
          Explore a live dashboard
      </p>

      {/* Media Container */}
      <div
        id="demo-media-container"
        ref={containerRef}
        onClick={handleVideoClick}
        style={{
          position: "relative",
          width: "800px",
          height: "450px",
          borderRadius: "16px",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
          overflow: "visible",
          backgroundColor: "#E2E8F0",
          marginBottom: "40px",
          cursor: state === "PLAYING" ? "pointer" : "default",
        }}
      >
        {/* Thumbnail: YouTube official image so it always matches the video */}
        <img
          id="demo-thumbnail-img"
          src={YOUTUBE_THUMBNAIL_URL}
          alt="Skeldir Channel Comparison dashboard preview — click to play"
          loading="eager"
          draggable={false}
          onClick={handlePlayClick}
          onError={(e) => {
            const target = e.currentTarget;
            if (target.src !== YOUTUBE_THUMBNAIL_FALLBACK) {
              target.src = YOUTUBE_THUMBNAIL_FALLBACK;
            }
          }}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: "center top",
            borderRadius: "16px",
            cursor: "pointer",
            userSelect: "none",
            display: state === "READY_TO_PLAY" ? "block" : "none",
          }}
        />

        {/* YouTube embed: plays in-page so users are not sent to youtube.com */}
        {state === "PLAYING" && (
          <iframe
            id="demo-youtube-embed"
            src={`${YOUTUBE_EMBED_URL}?autoplay=1`}
            title="Skeldir demo video"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              border: "none",
              borderRadius: "16px",
              zIndex: 5,
            }}
          />
        )}

        {/* Play Button Overlay */}
        <button
          id="demo-play-overlay"
          type="button"
          aria-label="Play Skeldir demo video"
          onClick={handlePlayClick}
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: "80px",
            height: "80px",
            borderRadius: "50%",
            background: "rgba(37, 99, 235, 0.95)",
            border: "none",
            cursor: "pointer",
            display: state === "READY_TO_PLAY" ? "flex" : "none",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 8px 24px rgba(37, 99, 235, 0.4)",
            transition: "transform 150ms ease, box-shadow 150ms ease",
            zIndex: 5,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = "translate(-50%, -50%) scale(1.1)";
            e.currentTarget.style.boxShadow =
              "0 12px 32px rgba(37, 99, 235, 0.5)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "translate(-50%, -50%)";
            e.currentTarget.style.boxShadow =
              "0 8px 24px rgba(37, 99, 235, 0.4)";
          }}
        >
          <PlayIcon />
        </button>

        {/* Tooltip 1: Revenue Verification */}
        <Tooltip
          number="1"
          title="Revenue Verification"
          subtitle="Platform-claimed vs. verified revenue"
          badgeTop={185}
          badgeLeft={310}
          calloutTop={115}
          calloutLeft={820}
          lineX1={342}
          lineY1={201}
          lineX2={820}
          lineY2={155}
          isVisible={tooltipsVisible}
        />

        {/* Tooltip 2: Confidence Ranges */}
        <Tooltip
          number="2"
          title="Confidence Ranges"
          subtitle="See exactly how certain the model is"
          badgeTop={265}
          badgeLeft={520}
          calloutTop={295}
          calloutLeft={820}
          lineX1={552}
          lineY1={281}
          lineX2={820}
          lineY2={335}
          isVisible={tooltipsVisible}
        />

        {/* Tooltip 3: Budget Recommendations */}
        <Tooltip
          number="3"
          title="Budget Recommendations"
          subtitle="Approve changes with one click"
          badgeTop={355}
          badgeLeft={280}
          calloutTop={340}
          calloutLeft={-240}
          lineX1={280}
          lineY1={371}
          lineX2={-20}
          lineY2={380}
          isVisible={tooltipsVisible}
        />

        {/* Error Overlay */}
        {state === "ERROR" && (
          <div
            id="demo-error-overlay"
            onClick={resetToReadyState}
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              background: "#FEE2E2",
              border: "1px solid #F87171",
              padding: "24px 32px",
              borderRadius: "12px",
              textAlign: "center",
              zIndex: 20,
              cursor: "pointer",
            }}
          >
            <p
              style={{
                margin: "0 0 8px",
                fontWeight: 600,
                color: "#991B1B",
                fontFamily: "Inter, -apple-system, sans-serif",
              }}
            >
              Video unavailable
            </p>
            <p
              style={{
                margin: 0,
                fontSize: "14px",
                color: "#B91C1C",
                fontFamily: "Inter, -apple-system, sans-serif",
              }}
            >
              Click to try again
            </p>
          </div>
        )}
      </div>

      {/* CTA Button Row */}
      <div
        id="demo-cta-row"
        style={{
          display: "flex",
          flexDirection: "row",
          justifyContent: "center",
          alignItems: "center",
          gap: "24px",
        }}
      >
        {/* Primary CTA: Watch 90-Sec Overview */}
        <button
          id="try-demo-btn"
          type="button"
          onClick={handlePlayClick}
          style={{
            width: "240px",
            height: "52px",
            padding: "14px 32px",
            backgroundColor: "#2563EB",
            color: "#FFFFFF",
            fontFamily: "Inter, -apple-system, sans-serif",
            fontSize: "16px",
            fontWeight: 600,
            border: "none",
            borderRadius: "12px",
            cursor: "pointer",
            boxShadow: "0 4px 14px rgba(37, 99, 235, 0.35)",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            transition:
              "background 150ms ease, transform 150ms ease, box-shadow 150ms ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = "#1D4ED8";
            e.currentTarget.style.transform = "translateY(-2px)";
            e.currentTarget.style.boxShadow =
              "0 8px 20px rgba(37, 99, 235, 0.45)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = "#2563EB";
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow =
              "0 4px 14px rgba(37, 99, 235, 0.35)";
          }}
        >
          Watch 90-Sec Overview
        </button>
      </div>
      </div>

      {/* Responsive styles */}
      <style>{`
        @media (max-width: 767px) {
          #product-demo-section {
            padding: 48px 20px !important;
          }

          #demo-section-title {
            font-size: 32px !important;
            line-height: 1.25 !important;
            margin-bottom: 12px !important;
            padding: 0 16px !important;
          }

          #demo-section-subtitle {
            font-size: 16px !important;
            line-height: 1.5 !important;
            margin-bottom: 32px !important;
            padding: 0 16px !important;
          }

          #demo-media-container {
            width: 100% !important;
            max-width: 100% !important;
            height: auto !important;
            aspect-ratio: 16 / 9 !important;
            margin-bottom: 32px !important;
          }

          .demo-tooltip-overlay {
            display: none !important;
          }

          #demo-cta-row {
            flex-direction: column !important;
            gap: 12px !important;
            width: 100% !important;
            padding: 0 16px !important;
          }

          #try-demo-btn,
          #watch-overview-btn {
            width: 100% !important;
            max-width: 100% !important;
            min-height: 48px !important;
            height: 48px !important;
            font-size: 16px !important;
          }

          #demo-play-overlay {
            width: 64px !important;
            height: 64px !important;
          }
        }

        @media (min-width: 768px) and (max-width: 900px) {
          #demo-media-container {
            width: 100% !important;
            max-width: 600px !important;
            height: auto !important;
            aspect-ratio: 16 / 9 !important;
          }

          .demo-tooltip-overlay {
            display: none !important;
          }

          #demo-cta-row {
            flex-direction: column !important;
            gap: 16px !important;
          }

          #try-demo-btn,
          #watch-overview-btn {
            width: 100% !important;
            max-width: 280px !important;
          }
        }

        #demo-play-overlay:focus-visible {
          outline: 3px solid #93C5FD;
          outline-offset: 4px;
        }

        #try-demo-btn:focus-visible,
        #watch-overview-btn:focus-visible {
          outline: 3px solid #93C5FD;
          outline-offset: 3px;
        }
      `}</style>
    </section>
  );
}
