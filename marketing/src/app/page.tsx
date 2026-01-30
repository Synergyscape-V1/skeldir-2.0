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
  link: [
    { rel: "preload", as: "image", href: "/images/Background-2.png" },
  ],
};

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col font-sans">
      {/* Hero Section with Background - includes navigation area */}
      <div
        className="relative flex flex-col hero-background-reveal"
        style={{
          backgroundImage: 'url(/images/Background-2.png)',
          backgroundSize: 'cover',
          backgroundPosition: 'center top',
          backgroundRepeat: 'no-repeat',
          minHeight: '100vh'
        }}
      >
        {/* Sticky Navigation */}
        <Navigation />

        {/* Hero Content Section */}
        <section className="relative flex flex-col overflow-hidden flex-1">
          {/* Hero Content */}
          <HeroSection />

          {/* Partner Logos */}
          <div className="container mx-auto px-4 md:px-6 pb-16 lg:pb-24 partner-logos-section">
            {/* Section Label */}
            <div
              className="partner-logos-label"
              style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                fontWeight: 400,
                lineHeight: 1.4,
                color: '#6C757D',
                textAlign: 'center',
                letterSpacing: '0.02em',
                maxWidth: '700px',
                margin: '0 auto',
                transform: 'translateY(50px)',
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
