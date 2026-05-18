"use client";

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";

/** Full phrase — measure + slice use identical string for stable layout physics */
const HERO_HEADLINE_LEAD = "Every ad dollar traced, verified to the source—";
const HERO_TYPEWRITER_PREFIX = "So your AI Agents and teams ";
const HERO_TYPEWRITER_SUFFIX_INITIAL = "never act on a guess.";
const HERO_TYPEWRITER_SUFFIX_FINAL = "execute from confirmed truth.";
const HERO_TYPEWRITER_PHRASE_INITIAL =
  HERO_TYPEWRITER_PREFIX + HERO_TYPEWRITER_SUFFIX_INITIAL;
const HERO_TYPEWRITER_PHRASE_FINAL =
  HERO_TYPEWRITER_PREFIX + HERO_TYPEWRITER_SUFFIX_FINAL;
/** Longest suffix sets invisible reserve width during suffix swap */
const HERO_TYPEWRITER_LAYOUT_SUFFIX =
  HERO_TYPEWRITER_SUFFIX_FINAL.length >= HERO_TYPEWRITER_SUFFIX_INITIAL.length
    ? HERO_TYPEWRITER_SUFFIX_FINAL
    : HERO_TYPEWRITER_SUFFIX_INITIAL;
const HERO_HEADLINE_ARIA_LABEL = `${HERO_HEADLINE_LEAD} ${HERO_TYPEWRITER_PHRASE_FINAL}`;

/** Subheadline — one string per line; order + spacing are layout-stable */
const HERO_SUBHEADLINE_LINES = [
  "Every major ad platform grades its own homework.",
  "Skeldir cross-checks & reconciles ad platform data against Stripe and Shopify revenue in real time, and gives you and your tools data you can actually trust.",
  "Live in 48 hours, not months.",
] as const;
const HERO_TYPEWRITER_MS_PER_CHAR = 58;
const HERO_TYPEWRITER_BACKSPACE_MS_PER_CHAR = 42;
const HERO_TYPEWRITER_START_DELAY_MS = 520;
const HERO_HOLD_AFTER_INITIAL_MS = 2400;
/** Caret geometry + blink — tied to type scale (em), not arbitrary px */
const HERO_CARET_WIDTH_EM = 0.065;
const HERO_CARET_MIN_WIDTH_PX = 2;
const HERO_CARET_HEIGHT_EM = 1.06;
const HERO_CARET_BLINK_DURATION_S = 1.55;

/** Highlight term — indices are stable across initial/final (shared prefix) */
const HERO_AI_AGENTS_TERM = "AI Agents";
const HERO_AI_AGENTS_TERM_START = HERO_TYPEWRITER_PHRASE_INITIAL.indexOf(HERO_AI_AGENTS_TERM);
const HERO_AI_AGENTS_TERM_END =
  HERO_AI_AGENTS_TERM_START + HERO_AI_AGENTS_TERM.length;
/** Ink (typewriter body) ↔ signal (CTA / intelligence accent) — discrete flip, not a gradient bleed */
const HERO_AI_AGENTS_COLOR_INK = "#111827";
const HERO_AI_AGENTS_COLOR_SIGNAL = "#2563EB";
const HERO_AI_AGENTS_FLIP_DURATION_S = 1.9;

/** Desktop — lift text column from grid vertical center (tablet/mobile unchanged) */
const HERO_DESKTOP_TEXT_OFFSET_PX = 28;

/** Single stack for h1 lead + typewriter — must match .hero-headline in scoped CSS */
const HERO_HEADLINE_FONT_FAMILY =
  "var(--font-hero-display), var(--font-dm-sans), ui-sans-serif, system-ui, sans-serif";

const heroTypewriterTextStyle: CSSProperties = {
  color: "#111827",
  fontFamily: HERO_HEADLINE_FONT_FAMILY,
  fontWeight: 700,
  lineHeight: 1.2,
  letterSpacing: "-0.02em",
};

type HeroTypewriterPhase =
  | "type-initial"
  | "hold"
  | "backspace"
  | "type-final"
  | "done";

function heroTypewriterInvisibleReserve(displayText: string): string {
  const prefixLen = HERO_TYPEWRITER_PREFIX.length;
  if (displayText.length < prefixLen) {
    return (
      HERO_TYPEWRITER_PREFIX.slice(displayText.length) + HERO_TYPEWRITER_LAYOUT_SUFFIX
    );
  }
  const suffixVisible = displayText.slice(prefixLen);
  return HERO_TYPEWRITER_LAYOUT_SUFFIX.slice(suffixVisible.length);
}

function renderTypewriterWithAiAgentsHighlight(
  displayText: string,
  aiAgentsFlipActive: boolean,
): ReactNode {
  const aiAgentsFullyTyped =
    HERO_AI_AGENTS_TERM_START >= 0 && displayText.length >= HERO_AI_AGENTS_TERM_END;

  if (!aiAgentsFullyTyped || HERO_AI_AGENTS_TERM_START < 0) {
    return displayText;
  }

  return (
    <>
      {displayText.slice(0, HERO_AI_AGENTS_TERM_START)}
      <span
        className={
          aiAgentsFlipActive ? "hero-ai-agents-flip" : "hero-ai-agents-term"
        }
      >
        {HERO_AI_AGENTS_TERM}
      </span>
      {displayText.slice(HERO_AI_AGENTS_TERM_END)}
    </>
  );
}

function HeroTypewriterKnowPhrase() {
  const [displayText, setDisplayText] = useState("");
  const [phase, setPhase] = useState<HeroTypewriterPhase>("type-initial");
  const [aiAgentsFlipActive, setAiAgentsFlipActive] = useState(false);
  const intervalRef = useRef<number | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const aiAgentsFlipFiredRef = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const clearTimers = () => {
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      if (intervalRef.current) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setDisplayText(HERO_TYPEWRITER_PHRASE_FINAL);
      setPhase("done");
      return clearTimers;
    }

    const runTypeForward = (
      target: string,
      startIndex: number,
      onComplete: () => void,
    ) => {
      let index = startIndex;
      intervalRef.current = window.setInterval(() => {
        index += 1;
        setDisplayText(target.slice(0, index));
        if (index >= target.length) {
          clearTimers();
          onComplete();
        }
      }, HERO_TYPEWRITER_MS_PER_CHAR);
    };

    const runBackspace = (fromLength: number, stopLength: number, onComplete: () => void) => {
      let index = fromLength;
      intervalRef.current = window.setInterval(() => {
        index -= 1;
        setDisplayText(HERO_TYPEWRITER_PHRASE_INITIAL.slice(0, index));
        if (index <= stopLength) {
          setDisplayText(HERO_TYPEWRITER_PREFIX);
          clearTimers();
          onComplete();
        }
      }, HERO_TYPEWRITER_BACKSPACE_MS_PER_CHAR);
    };

    const startSequence = () => {
      setPhase("type-initial");
      runTypeForward(HERO_TYPEWRITER_PHRASE_INITIAL, 0, () => {
        setPhase("hold");
        timeoutRef.current = window.setTimeout(() => {
          setPhase("backspace");
          runBackspace(
            HERO_TYPEWRITER_PHRASE_INITIAL.length,
            HERO_TYPEWRITER_PREFIX.length,
            () => {
              setPhase("type-final");
              runTypeForward(
                HERO_TYPEWRITER_PHRASE_FINAL,
                HERO_TYPEWRITER_PREFIX.length,
                () => {
                  setPhase("done");
                },
              );
            },
          );
        }, HERO_HOLD_AFTER_INITIAL_MS);
      });
    };

    timeoutRef.current = window.setTimeout(startSequence, HERO_TYPEWRITER_START_DELAY_MS);

    return clearTimers;
  }, []);

  useEffect(() => {
    if (aiAgentsFlipFiredRef.current) return;
    if (HERO_AI_AGENTS_TERM_START < 0) return;
    if (displayText.length < HERO_AI_AGENTS_TERM_END) return;
    if (typeof window === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    aiAgentsFlipFiredRef.current = true;
    setAiAgentsFlipActive(true);
  }, [displayText]);

  const invisibleReserve = heroTypewriterInvisibleReserve(displayText);
  const showCaret = phase !== "done";

  return (
    <span className="hero-typewriter-wrap" style={heroTypewriterTextStyle} aria-hidden="true">
      <span className="hero-typewriter-typed">
        {renderTypewriterWithAiAgentsHighlight(displayText, aiAgentsFlipActive)}
        {showCaret ? <span className="hero-typewriter-caret" aria-hidden /> : null}
      </span>
      <span className="hero-typewriter-remainder">{invisibleReserve}</span>
    </span>
  );
}

export function HeroSection() {
  return (
    <div className="pt-24 pb-16 lg:pt-32 lg:pb-24">
      <div className="container mx-auto px-4 md:px-6">
        <div className="grid gap-12 lg:grid-cols-2 lg:gap-12 items-center min-w-0 hero-home-grid">
          {/* Left: Text Content — above product visual (3D transform creates stacking) */}
          <div className="flex flex-col justify-center space-y-8 text-left lg:pr-8 hero-text-column relative z-[30] min-w-0 max-w-full">
            <h1
              className="font-bold text-white hero-headline max-w-full"
              style={{ color: "white" }}
              aria-label={HERO_HEADLINE_ARIA_LABEL}
            >
              <span className="hero-headline-lead">{HERO_HEADLINE_LEAD}</span>{" "}
              <HeroTypewriterKnowPhrase />
            </h1>

            <p className="max-w-[600px] text-white mx-auto lg:mx-0 hero-subheadline">
              {HERO_SUBHEADLINE_LINES.map((line) => (
                <span key={line} className="hero-subheadline-line">
                  {line}
                </span>
              ))}
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

          {/* Right: Product Visual — 3D perspective hero dashboard */}
          <div className="relative z-0 mx-auto w-full min-w-0 max-w-[950px] lg:max-w-none lg:ml-[20%] hero-image-container home-product-hero">
            <div className="hero-image-float-wrapper">
              <div className="relative overflow-visible hero-image-glass">
                <img
                  src="/homepage-demo-2.png"
                  alt="Skeldir command center — unified attribution and ROAS control panel"
                  className="w-full h-auto object-contain hero-dashboard-image block"
                  loading="eager"
                  decoding="async"
                  fetchPriority="high"
                />
              </div>
            </div>
          </div>
          
          <style>{`
            @keyframes hero-caret-blink {
              0%, 45% { opacity: 1; }
              50%, 95% { opacity: 0; }
              100% { opacity: 1; }
            }
            /* One burst per page load: ink ↔ signal, stepped (no continuous loop) */
            @keyframes hero-ai-agents-color-flip {
              0%, 100% { color: ${HERO_AI_AGENTS_COLOR_INK}; }
              16.67% { color: ${HERO_AI_AGENTS_COLOR_SIGNAL}; }
              33.33% { color: ${HERO_AI_AGENTS_COLOR_INK}; }
              50% { color: ${HERO_AI_AGENTS_COLOR_SIGNAL}; }
              66.67% { color: ${HERO_AI_AGENTS_COLOR_INK}; }
              83.33% { color: ${HERO_AI_AGENTS_COLOR_SIGNAL}; }
            }
            .hero-ai-agents-term {
              color: ${HERO_AI_AGENTS_COLOR_INK};
            }
            .hero-ai-agents-flip {
              animation: hero-ai-agents-color-flip ${HERO_AI_AGENTS_FLIP_DURATION_S}s step-end 1 forwards;
            }
            /* Column-sized type scale — same cqi basis as measure + slice reserve below */
            .hero-text-column {
              container-type: inline-size;
              container-name: hero-text;
            }
            .hero-headline {
              font-family: ${HERO_HEADLINE_FONT_FAMILY};
              font-size: clamp(1.875rem, 0.6rem + 5.2cqi, 2.75rem);
              line-height: 1.2;
              letter-spacing: -0.02em;
              font-weight: 700;
            }
            .hero-headline-lead {
              display: inline;
              white-space: normal;
            }
            .hero-subheadline {
              font-size: 16px;
              line-height: 1.5;
            }
            .hero-subheadline-line {
              display: block;
            }
            .hero-subheadline-line + .hero-subheadline-line {
              margin-top: 2px;
            }
            /* In-flow reserve: invisible suffix keeps width = full phrase; caret sits before remainder from first paint */
            .hero-typewriter-wrap {
              display: inline;
              max-width: 100%;
              white-space: normal;
            }
            .hero-typewriter-remainder {
              visibility: hidden !important;
              user-select: none;
              pointer-events: none;
              white-space: normal;
            }
            .hero-typewriter-typed {
              display: inline;
            }
            .hero-typewriter-caret {
              display: inline-block;
              width: ${HERO_CARET_WIDTH_EM}em;
              min-width: ${HERO_CARET_MIN_WIDTH_PX}px;
              height: ${HERO_CARET_HEIGHT_EM}em;
              margin-left: 0;
              margin-right: 0.05em;
              vertical-align: -0.1em;
              background: #111827;
              animation: hero-caret-blink ${HERO_CARET_BLINK_DURATION_S}s step-end infinite;
            }
            @media (prefers-reduced-motion: reduce) {
              .hero-typewriter-caret {
                animation: none;
                opacity: 1;
              }
              .hero-ai-agents-flip {
                animation: none;
                color: ${HERO_AI_AGENTS_COLOR_INK} !important;
              }
            }
            .hero-home-grid {
              min-width: 0;
            }

            /* ─── 3D Perspective Stage ─── */
            .hero-image-container {
              perspective: 1200px;
              perspective-origin: 60% 50%;
            }

            /* Float animation wrapper — isolated from 3D rotation */
            .hero-image-float-wrapper {
              position: relative;
              transform-style: preserve-3d;
              animation: hero-float 7s ease-in-out infinite;
              will-change: transform;
            }

            @keyframes hero-float {
              0%, 100% { transform: translateY(0px); }
              50% { transform: translateY(-8px); }
            }

            /* Ground contact shadow — on float wrapper so it stays flat */
            .hero-image-float-wrapper::after {
              content: '';
              position: absolute;
              bottom: -22px;
              left: 12%;
              right: 2%;
              height: 50px;
              background: radial-gradient(
                ellipse at 38% 50%,
                rgba(0, 0, 0, 0.20) 0%,
                rgba(0, 0, 0, 0.07) 45%,
                transparent 75%
              );
              border-radius: 50%;
              z-index: -1;
              filter: blur(18px);
              pointer-events: none;
            }

            /* 3D panel — no glass frame (avoids white matting / border around asset) */
            .hero-image-glass {
              position: relative;
              transform-style: preserve-3d;
              transform: translateX(4%) scale(1.25) rotateY(-8deg) rotateX(4deg);
              transform-origin: 65% center;
            }

            /* ─── Responsive ─── */

            @media (max-width: 767px) {
              .hero-text-column {
                align-items: flex-start !important;
              }
              .hero-headline {
                font-size: clamp(1.75rem, 0.5rem + 5.5cqi, 2.25rem) !important;
                line-height: 1.22 !important;
                letter-spacing: -0.02em !important;
                font-weight: 700 !important;
                margin-bottom: 20px !important;
                text-align: left !important;
              }
              .hero-headline-lead,
              .hero-typewriter-wrap {
                white-space: normal !important;
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
                margin-top: 24px !important;
                perspective: 800px;
                perspective-origin: 55% 50%;
              }
              .hero-image-glass {
                transform: translateX(-0.5%) scale(1.08) rotateY(-3deg) rotateX(2deg);
                transform-origin: center center;
                width: 100%;
              }
              .hero-dashboard-image {
                width: 100% !important;
                max-width: 100% !important;
                height: auto !important;
                object-fit: contain !important;
                margin-left: 0 !important;
              }
              .hero-image-float-wrapper::after {
                display: none;
              }
            }

            @media (min-width: 768px) and (max-width: 1023px) {
              .hero-headline {
                font-size: clamp(1.875rem, 0.55rem + 4.8cqi, 2.5rem) !important;
                line-height: 1.22 !important;
              }
              .hero-subheadline {
                font-size: 18px !important;
                line-height: 1.6 !important;
              }
              .hero-image-glass {
                transform: translateX(3%) scale(1.05) rotateY(-6deg) rotateX(3deg);
              }
            }

            @media (min-width: 1024px) {
              .hero-text-column {
                transform: translateY(-${HERO_DESKTOP_TEXT_OFFSET_PX}px);
              }
              .hero-headline {
                font-size: clamp(2rem, 0.65rem + 5cqi, 3rem) !important;
                line-height: 1.18 !important;
              }
              .hero-image-container {
                max-width: 1100px !important;
                margin-left: 0 !important;
                perspective: 1400px;
                perspective-origin: 60% 50%;
              }
              .hero-image-glass {
                transform: translateX(6%) scale(1.3) rotateY(-10deg) rotateX(5deg);
                transform-origin: 60% center;
              }
              .hero-dashboard-image {
                max-height: 640px !important;
                width: 100% !important;
                object-fit: contain !important;
              }
            }
          `}</style>
        </div>
      </div>
    </div>
  );
}
