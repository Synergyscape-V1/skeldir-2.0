import type { Metadata } from "next";
import { JsonLd } from "@/components/schema/JsonLd";
import { AgenciesHeroSection } from "@/components/layout/AgenciesHeroSection";
import { AgenciesPostHeroSection } from "@/components/layout/AgenciesPostHeroSection";
import { AgenciesScalabilitySection } from "@/components/layout/AgenciesScalabilitySection";
import { AgenciesSection4 } from "@/components/layout/AgenciesSection4";
import { Footer } from "@/components/layout/Footer";
import { absoluteUrl } from "@/lib/siteCrawl";
import { webPageJsonLd } from "@/lib/schema/entity";
import { AGENCIES_HERO_SUBHEAD, AGENCIES_PAGE_H1_TEXT } from "@/components/layout/agenciesHeroCopy";

export const metadata: Metadata = {
  title: "Skeldir for Agencies — Revenue verification for client portfolios",
  description: AGENCIES_HERO_SUBHEAD,
  alternates: {
    canonical: absoluteUrl("/agencies"),
  },
};

export default function AgenciesPage() {
  return (
    <main className="min-h-screen flex flex-col font-sans">
      <JsonLd
        data={webPageJsonLd("/agencies", {
          name: AGENCIES_PAGE_H1_TEXT,
          description: AGENCIES_HERO_SUBHEAD,
        })}
      />
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
