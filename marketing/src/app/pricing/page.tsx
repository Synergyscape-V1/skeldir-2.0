import type { Metadata } from "next";
import { Footer } from "@/components/layout/Footer";
import { PricingHero } from "@/components/pricing/PricingHero";
import { PricingPageTiers } from "@/components/pricing/PricingPageTiers";
import { FinalCTA } from "@/components/pricing/FinalCTA";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "Pricing | Skeldir",
  description: "Skeldir pricing and plans for verified ad revenue intelligence.",
  alternates: {
    canonical: absoluteUrl("/pricing"),
  },
};

export default function PricingPage() {
    return (
        <div className="min-h-screen flex flex-col bg-white">
            <main className="flex-grow">
                <PricingHero />
                <PricingPageTiers />
                <FinalCTA />
            </main>
            <Footer />
        </div>
    );
}
