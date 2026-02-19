import { Footer } from "@/components/layout/Footer";
import { PricingHero } from "@/components/pricing/PricingHero";
import { PricingPageTiers } from "@/components/pricing/PricingPageTiers";
import { FinalCTA } from "@/components/pricing/FinalCTA";

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
