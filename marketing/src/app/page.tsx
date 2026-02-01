import type { Metadata } from "next";
import { Navigation } from "@/components/layout/Navigation";
import { HeroSection } from "@/components/layout/HeroSection";
import { PartnerLogos } from "@/components/layout/PartnerLogos";
import { ProblemStatement } from "@/components/layout/ProblemStatement";
import { SolutionOverview } from "@/components/layout/SolutionOverview";
import { HowItWorks } from "@/components/layout/HowItWorks";
import { PricingTiers } from "@/components/layout/PricingTiers";
import { TestimonialCarousel } from "@/components/layout/TestimonialCarousel";
import { InteractiveDemo } from "@/components/layout/InteractiveDemo";
import { FinalCTA } from "@/components/layout/FinalCTA";
import { Footer } from "@/components/layout/Footer";

export const metadata: Metadata = {
  

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col font-sans">
      {/* Hero Section - responsive img (replaces CSS background) for instant LCP */}
      <section
        className="hero-section hero-background-reveal"
        style={{
          position: "relative",
          width: "100%",
          minHeight: "100vh",
          overflow: "hidden",
          margin: 0,
        }}
      >
        <img
          src="/assets/images/hero/hero-800w.jpg"
          srcSet="/assets/images/hero/hero-400w.jpg 400w, /assets/images/hero/hero-800w.jpg 800w, /assets/images/hero/hero-1200w.jpg 1200w"
          sizes="(max-width: 767px) 100vw, (max-width: 1023px) 80vw, 1200px"
          alt="Abstract blue-purple gradient wave background"
          width={1200}
          height={661}
          loading="eager"
                  decoding="sync"
          fetchPriority="high"
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: "center",
                      display: "block",
                      willChange: "transform",
                      opacity: 1,
          
            zIndex: 0,
          }}
        />
        {/* Overlay content - preserved z-index above image */}
        <div style={{ position: "relative", zIndex: 1, display: "flex", flexDirection: "column", minHeight: "100vh" }}>
          <Navigation />
          <section className="relative flex flex-col overflow-hidden flex-1">
            <HeroSection />
            <div className="container mx-auto px-4 md:px-6 pb-16 lg:pb-24 partner-logos-section">
              <div
                className="partner-logos-label"
                style={{
                  fontFamily: "Inter, sans-serif",
                  fontSize: "14px",
                  fontWeight: 400,
                  lineHeight: 1.4,
                  color: "#6C757D",
                  textAlign: "center",
                  letterSpacing: "0.02em",
                  maxWidth: "700px",
                  margin: "0 auto",
                  transform: "translateY(50px)",
                }}
              >
                Trusted by agencies and brands managing $50M+ in annual ad spend
              </div>
              <PartnerLogos />
            </div>

            <style>{`
              @media (max-width: 767px) {
                .partner-logos-section {
                  padding-left: 16px !important;
                  padding-right: 16px !important;
                }

                .partner-logos-label {
                  font-size: 13px !important;
                  line-height: 1.5 !important;
                  margin-bottom: 24px !important;
                  transform: translateY(0) !important;
                  padding: 0 16px !important;
                }

                .partner-logos-container {
                  margin-top: 0 !important;
                }
              }
              @keyframes hero-bg-reveal {
                from { opacity: 0; }
                to { opacity: 1; }
              }
              .hero-background-reveal {
                animation: hero-bg-reveal 0.55s ease-out 0.1s both;
              }
            `}</style>
          </section>
        </div>
      </section>

      {/* Problem Statement Section */}
      <ProblemStatement />

      {/* Solution Overview Section */}
      <SolutionOverview />

      {/* Interactive Product Demo Section */}
      <InteractiveDemo />

      {/* How It Works Timeline Section */}
      <HowItWorks />

      {/* Pricing Tiers Section */}
      <PricingTiers />

      {/* Testimonial Carousel Section */}
      <TestimonialCarousel />

      {/* Final CTA Section - Homepage Conversion Finale */}
      <FinalCTA />

      {/* Footer Section */}
      <Footer />
    </main>
  );
}
