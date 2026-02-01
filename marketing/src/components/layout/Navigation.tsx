"use client";

import Link from "next/link";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { Menu, X } from "lucide-react";
import { useState, useEffect, useRef } from "react";

const navLinks = [
  { href: "/product", label: "Product" },
  { href: "/pricing", label: "Pricing" },
  { href: "/agencies", label: "Agencies" },
  { href: "/resources", label: "Resources" },
];

export function Navigation({ forceVisible = false }: { forceVisible?: boolean }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [isClient, setIsClient] = useState(false);
  const toggleHandledByPointer = useRef(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  useEffect(() => {
    const handleScroll = () => {
      const isScrolled = window.scrollY > 100;
      setScrolled(isScrolled);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // H01/H02: When mobile nav is open, prevent scroll on the page behind (overflow only — no position:fixed so the menu open tap is not blocked on mobile).
  useEffect(() => {
    if (!mobileMenuOpen) return;
    const prevBody = document.body.style.overflow;
    const prevHtml = document.documentElement.style.overflow;
    document.body.style.overflow = 'hidden';
    document.documentElement.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prevBody;
      document.documentElement.style.overflow = prevHtml;
    };
  }, [mobileMenuOpen]);

  const isVisible = forceVisible || scrolled;

  return (
    <header
      className="fixed top-0 z-[9999] w-full pb-2 transition-all duration-300"
      style={{
        // Visible state (scrolled or forceVisible): solid + blur + subtle border
        backgroundColor: isVisible ? "rgba(255, 255, 255, 0.95)" : "transparent",
        boxShadow: isVisible ? "0 4px 20px rgba(0, 0, 0, 0.1)" : "none",
        borderBottom: isVisible ? "1px solid rgba(229, 231, 235, 0.4)" : "none",
        backdropFilter: isVisible ? "blur(12px)" : "none",
      }}
    >
      <nav className="container mx-auto flex h-16 items-center justify-between px-4 md:px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2" style={{ transform: 'translateY(2px)' }}>
          <picture>
            <source srcSet="/images/logos/skeldir-logo.webp" type="image/webp" />
            <img
              src="/images/logos/skeldir-logo.png"
              alt="Skeldir"
              width={140}
              height={32}
              className="h-[4.2rem] w-auto"
              loading="eager"
              fetchPriority="high"
              decoding="async"
            />
          </picture>
        </Link>

        {/* Desktop Navigation Links */}
        <div className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-[15px] font-semibold transition-all px-3 py-2 rounded-lg"
              style={{
                color: isVisible ? '#1E293B' : '#FFFFFF',
                backgroundColor: 'transparent',
                transform: 'translateY(0px)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = isVisible ? '#2563EB' : '#93C5FD';
                e.currentTarget.style.backgroundColor = isVisible
                  ? 'rgba(37, 99, 235, 0.08)'
                  : 'rgba(255, 255, 255, 0.12)';
                e.currentTarget.style.transform = 'translateY(-1px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = isVisible ? '#1E293B' : '#FFFFFF';
                e.currentTarget.style.backgroundColor = 'transparent';
                e.currentTarget.style.transform = 'translateY(0px)';
              }}
            >
              {link.label}
            </Link>
          ))}
        </div>

        {/* Desktop Actions */}
        <div className="hidden md:flex items-center gap-4">
          <Link
            href="/Login"
            className="text-[15px] font-semibold transition-all px-3 py-2 rounded-lg"
            style={{
              color: isVisible ? '#1E293B' : '#FFFFFF',
              backgroundColor: 'transparent',
              transform: 'translateY(0px)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = isVisible ? '#2563EB' : '#93C5FD';
              e.currentTarget.style.backgroundColor = isVisible
                ? 'rgba(37, 99, 235, 0.08)'
                : 'rgba(255, 255, 255, 0.12)';
              e.currentTarget.style.transform = 'translateY(-1px)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = isVisible ? '#1E293B' : '#FFFFFF';
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.transform = 'translateY(0px)';
            }}
          >
            Login
          </Link>
          {/* Animated CTA Button with Border and Sweep Effects */}
          <div
            className="cta-button-wrapper"
            style={{
              position: 'relative',
              width: '140px',
              height: '42px',
              borderRadius: '8px',
              padding: '2px',
              overflow: 'hidden',
              cursor: 'pointer',
            }}
          >
            <style>{`
              @keyframes borderRotate {
                0% {
                  transform: rotate(0deg);
                }
                100% {
                  transform: rotate(360deg);
                }
              }
              
              @keyframes sweepArrow {
                0% {
                  transform: translateX(-100%) translateY(-50%) rotate(45deg);
                  opacity: 0;
                }
                5% {
                  opacity: 0.4;
                }
                50% {
                  opacity: 0.5;
                }
                95% {
                  opacity: 0.4;
                }
                100% {
                  transform: translateX(calc(100% + 140px)) translateY(-50%) rotate(45deg);
                  opacity: 0;
                }
              }
              
              .cta-button-wrapper::after {
                content: '';
                position: absolute;
                top: -2px;
                left: -2px;
                right: -2px;
                bottom: -2px;
                border-radius: 8px;
                background: conic-gradient(from 0deg, #FF00CC, #FF9900, #FF00CC);
                animation: borderRotate 8s linear infinite;
                z-index: 0;
                pointer-events: none;
              }
              
              .cta-button-wrapper::before {
                content: '';
                position: absolute;
                top: 50%;
                left: 0;
                width: 120px;
                height: 300%;
                background: linear-gradient(
                  45deg,
                  transparent 0%,
                  transparent 20%,
                  rgba(255, 255, 255, 0.5) 50%,
                  transparent 80%,
                  transparent 100%
                );
                transform-origin: center center;
                pointer-events: none;
                z-index: 2;
                mix-blend-mode: screen;
                animation: sweepArrow 2s ease-in-out infinite;
                animation-delay: 1s;
              }
              
              .cta-button-inner {
                position: relative;
                z-index: 1;
                background-color: #2563EB;
                color: #FFFFFF !important;
              }
              
              .cta-button-inner:hover {
                color: #FFFFFF !important;
              }
            `}</style>
            <Link href="/signup" className="w-full h-full block" style={{ cursor: 'pointer' }}>
              <Button
                className="cta-button-inner transition-all relative overflow-hidden"
                style={{
                  backgroundColor: '#2563EB',
                  color: '#FFFFFF',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '15px',
                  fontWeight: 700,
                  width: '100%',
                  height: '100%',
                  borderRadius: '6px',
                  boxShadow: '0 2px 8px rgba(37, 99, 235, 0.2)',
                  border: 'none',
                  cursor: 'pointer',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#1E40AF';
                  e.currentTarget.style.color = '#FFFFFF';
                  e.currentTarget.style.boxShadow = '0 4px 12px rgba(37, 99, 235, 0.4)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#2563EB';
                  e.currentTarget.style.color = '#FFFFFF';
                  e.currentTarget.style.boxShadow = '0 2px 8px rgba(37, 99, 235, 0.2)';
                }}
              >
                Get Started
              </Button>
            </Link>
          </div>
        </div>

        {/* Mobile Menu Button — H03: pointer + click without double-toggle; portal ensures menu is never clipped by ancestors */}
        <button
          type="button"
          className="md:hidden mobile-menu-toggle"
          style={{
            color: isVisible ? '#1E293B' : '#FFFFFF',
            minWidth: '44px',
            minHeight: '44px',
            padding: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'color 200ms ease',
            touchAction: 'manipulation',
            cursor: 'pointer',
          }}
          onPointerDown={() => {
            toggleHandledByPointer.current = true;
            setMobileMenuOpen((prev) => !prev);
          }}
          onClick={() => {
            if (toggleHandledByPointer.current) {
              toggleHandledByPointer.current = false;
              return;
            }
            setMobileMenuOpen((prev) => !prev);
          }}
          aria-label="Toggle menu"
          aria-expanded={mobileMenuOpen}
        >
          {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </nav>

      {/* H03: Mobile menu and backdrop rendered via portal into document.body so no ancestor can clip or stack-context them */}
      {isClient &&
        createPortal(
          <>
            <div
              className={`mobile-menu-backdrop ${mobileMenuOpen ? 'mobile-menu-backdrop-visible' : ''}`}
              onClick={() => setMobileMenuOpen(false)}
              aria-hidden="true"
            />
            <div
              className={`md:hidden bg-white mobile-menu ${mobileMenuOpen ? 'mobile-menu-open' : ''}`}
              aria-modal="true"
              aria-hidden={!mobileMenuOpen}
            >
              <div className="mobile-menu-header">
                <Link
                  href="/"
                  onClick={() => setMobileMenuOpen(false)}
                  style={{ display: 'flex', alignItems: 'center' }}
                >
                  <picture>
                    <source srcSet="/images/logos/skeldir-logo.webp" type="image/webp" />
                    <img
                      src="/images/logos/skeldir-logo.png"
                      alt="Skeldir"
                      width={140}
                      height={32}
                      className="h-[4.2rem] w-auto"
                      loading="eager"
                      decoding="async"
                    />
                  </picture>
                </Link>
                <button
                  type="button"
                  onClick={() => setMobileMenuOpen(false)}
                  className="mobile-menu-close"
                  aria-label="Close menu"
                >
                  <X className="h-6 w-6" />
                </button>
              </div>
              <div className="mobile-menu-content">
                <div className="space-y-4">
                  {navLinks.map((link) => (
                    <Link
                      key={link.href}
                      href={link.href}
                      className="mobile-menu-link block text-sm font-medium text-gray-700 transition-colors hover:text-blue-600"
                      style={{
                        minHeight: '44px',
                        display: 'flex',
                        alignItems: 'center',
                        padding: '8px 0',
                      }}
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      {link.label}
                    </Link>
                  ))}
                  <div className="pt-4 border-t border-gray-200 space-y-3 mt-4">
                    <Link
                      href="/Login"
                      className="mobile-menu-link block text-sm font-medium text-gray-700 transition-colors hover:text-blue-600"
                      style={{
                        minHeight: '44px',
                        display: 'flex',
                        alignItems: 'center',
                        padding: '8px 0',
                      }}
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      Login
                    </Link>
                    <Link href="/signup" className="w-full" style={{ cursor: 'pointer' }} onClick={() => setMobileMenuOpen(false)}>
                      <Button
                        className="w-full transition-all mobile-cta-button"
                        style={{
                          backgroundColor: '#2563EB',
                          color: '#FFFFFF',
                          fontFamily: 'Inter, sans-serif',
                          fontSize: '16px',
                          fontWeight: 700,
                          minHeight: '48px',
                          height: '48px',
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
                        Get Started
                      </Button>
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          </>,
          document.body
        )}

      <style>{`
        /* Mobile Menu Backdrop */
        .mobile-menu-backdrop {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.5);
          z-index: 9998;
          opacity: 0;
          pointer-events: none;
          backdrop-filter: blur(4px);
          transition: opacity 0.3s ease-out, pointer-events 0.3s ease-out;
        }

        .mobile-menu-backdrop-visible {
          opacity: 1;
          pointer-events: auto;
        }

        @keyframes fadeIn {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }

        /* Mobile Menu Container — H02: viewport-filling so menu is not clipped when user has scrolled */
        .mobile-menu {
          position: fixed;
          inset: 0;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          width: 100%;
          min-width: 100vw;
          height: 100vh;
          min-height: 100dvh;
          background: white;
          z-index: 9999;
          max-height: 0;
          overflow: hidden;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
          transition: max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease-out;
          opacity: 0;
          display: flex;
          flex-direction: column;
        }

        .mobile-menu-open {
          max-height: 100vh;
          max-height: 100dvh;
          height: 100vh;
          height: 100dvh;
          min-height: 100vh;
          min-height: 100dvh;
          opacity: 1;
          overflow: visible;
          visibility: visible;
          pointer-events: auto;
          animation: slideDown 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards;
        }

        .mobile-menu-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 20px;
          border-bottom: 1px solid #E5E7EB;
          flex-shrink: 0;
        }

        .mobile-menu-close {
          min-width: 44px;
          min-height: 44px;
          padding: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #1E293B;
          background: transparent;
          border: none;
          cursor: pointer;
          transition: transform 0.2s ease, opacity 0.2s ease;
        }

        .mobile-menu-close:active {
          transform: scale(0.9);
          opacity: 0.7;
        }

        .mobile-menu-content {
          flex: 1;
          overflow-y: auto;
          padding: 24px 16px;
          max-width: 100%;
        }

        .mobile-menu-content .container {
          max-width: 100%;
          padding: 0;
        }

        .mobile-menu:not(.mobile-menu-open) {
          max-height: 0;
          opacity: 0;
          visibility: hidden;
          pointer-events: none;
        }

        @keyframes slideDown {
          from {
            transform: translateY(-100%);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }

        @keyframes slideUp {
          from {
            transform: translateY(0);
            opacity: 1;
          }
          to {
            transform: translateY(-20px);
            opacity: 0;
          }
        }

        /* Staggered animation for menu items */
        .mobile-menu-open .mobile-menu-link,
        .mobile-menu-open .mobile-cta-button {
          opacity: 0;
          transform: translateX(-10px);
          animation: slideInItem 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards;
        }

        .mobile-menu-open .mobile-menu-link:nth-child(1) {
          animation-delay: 0.05s;
        }
        .mobile-menu-open .mobile-menu-link:nth-child(2) {
          animation-delay: 0.1s;
        }
        .mobile-menu-open .mobile-menu-link:nth-child(3) {
          animation-delay: 0.15s;
        }
        .mobile-menu-open .mobile-menu-link:nth-child(4) {
          animation-delay: 0.2s;
        }
        .mobile-menu-open .mobile-menu-link:nth-child(5) {
          animation-delay: 0.25s;
        }
        .mobile-menu-open .mobile-cta-button {
          animation-delay: 0.3s;
        }

        @keyframes slideInItem {
          from {
            opacity: 0;
            transform: translateX(-10px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }

        /* Hamburger icon rotation */
        .mobile-menu-toggle svg {
          transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease;
        }

        .mobile-menu-toggle[aria-expanded="true"] svg {
          transform: rotate(90deg);
        }

        /* Hide mobile menu toggle on desktop (md and above) */
        @media (min-width: 768px) {
          .mobile-menu-toggle {
            display: none !important;
          }
          .mobile-menu {
            display: none !important;
          }
          .mobile-menu-backdrop {
            display: none !important;
          }
        }

        @media (max-width: 767px) {
          .mobile-menu-toggle {
            min-width: 44px !important;
            min-height: 44px !important;
            display: flex !important;
            transition: transform 0.2s ease;
          }

          .mobile-menu-toggle:active {
            transform: scale(0.95);
          }

          .mobile-menu-link {
            min-height: 44px !important;
            padding: 12px 0 !important;
            transition: background-color 0.2s ease, color 0.2s ease;
          }

          .mobile-menu-link:active {
            background-color: rgba(37, 99, 235, 0.1);
          }

          .mobile-cta-button {
            min-height: 48px !important;
            height: 48px !important;
            font-size: 16px !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
          }

          .mobile-cta-button:active {
            transform: scale(0.98);
          }
        }
      `}</style>
    </header>
  );
}
