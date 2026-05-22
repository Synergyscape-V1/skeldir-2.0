import type { Metadata } from "next";
import { JsonLd } from "@/components/schema/JsonLd";
import { Footer } from "@/components/layout/Footer";
import { PricingHero } from "@/components/pricing/PricingHero";
import { PricingPageTiers } from "@/components/pricing/PricingPageTiers";
import { FinalCTA } from "@/components/pricing/FinalCTA";
import { absoluteUrl } from "@/lib/siteCrawl";
import { webPageJsonLd } from "@/lib/schema/entity";
import { PRICING_PAGE_DESCRIPTION, PRICING_PAGE_H1 } from "@/lib/schema/pageSchemas";

export const metadata: Metadata = {
  title: "Pricing | Skeldir",
  description: PRICING_PAGE_DESCRIPTION,
  alternates: {
    canonical: absoluteUrl("/pricing"),
  },
};

export default function PricingPage() {
    return (
        <div className="min-h-screen flex flex-col bg-white">
            <JsonLd
              data={webPageJsonLd("/pricing", {
                name: PRICING_PAGE_H1,
                description: PRICING_PAGE_DESCRIPTION,
              })}
            />
            <main className="flex-grow">
                <PricingHero />
                <PricingPageTiers />
                <FinalCTA />
            </main>
            <Footer />
        </div>
    );
}
