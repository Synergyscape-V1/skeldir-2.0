"use client";

import { PRICING_PAGE_DESCRIPTION, PRICING_PAGE_H1 } from "@/lib/schema/pageSchemas";

export function PricingHero() {
    return (
        <section className="w-full bg-white pt-24 pb-16 md:pt-32 md:pb-24">
            <div className="container mx-auto px-4 md:px-6">
                <div className="flex flex-col items-center text-center max-w-4xl mx-auto">
                    <h1 className="text-4xl md:text-6xl font-bold tracking-tight text-slate-900 leading-[1.1] mb-6 md:mb-8">
                        {PRICING_PAGE_H1}
                    </h1>
                    <p className="text-lg md:text-xl text-slate-600 leading-relaxed max-w-3xl mx-auto font-normal">
                        {PRICING_PAGE_DESCRIPTION}
                    </p>
                </div>
            </div>
        </section>
    );
}
