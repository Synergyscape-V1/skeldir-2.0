import type { Metadata } from "next";
import { AgenciesHeroSection } from "@/components/layout/AgenciesHeroSection";
import { AgenciesPostHeroSection } from "@/components/layout/AgenciesPostHeroSection";
import { AgenciesScalabilitySection } from "@/components/layout/AgenciesScalabilitySection";
import { AgenciesSection4 } from "@/components/layout/AgenciesSection4";
import { Footer } from "@/components/layout/Footer";

export const metadata: Metadata = {
  title: "Skeldir for Agencies — Enterprise Attribution Intelligence",
  description:
    "Skeldir delivers Bayesian confidence ranges for multi-client portfolios. White-label dashboards, REST API access, and deployment in days—not months.",
};

export default function AgenciesPage() {
  return (
    <main className="min-h-screen flex flex-col font-sans">
      {/* Hero Section */}
      <AgenciesHeroSection />

      {/* Post-Hero Section: Social proof + Metrics */}
      <AgenciesPostHeroSection />

      {/* Section 3: Agency Scalability Proof */}
      <AgenciesScalabilitySection />

      {/* Section 4: Statistical Authority & Lead Capture */}
      <AgenciesSection4 />

      {/* Footer */}
      <Footer />
    </main>
  );
}
