"use client";

import type { CSSProperties } from "react";
import { SECTION_DISPLAY_TITLE_CLASS } from "@/components/layout/sectionDisplayFont";
import { CATEGORY_ANCHOR_BODY } from "@/lib/categoryAnchorCopy";
import { PRICING_PAGE_H1 } from "@/lib/schema/pageSchemas";

/** Matches `CategoryAnchor` body typography */
const PRICING_HERO_BODY_STYLE: CSSProperties = {
    margin: 0,
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
    fontSize: "17px",
    lineHeight: 1.55,
    fontWeight: 400,
    color: "#374151",
};

export function PricingHero() {
    return (
        <section className="w-full bg-white pt-24 pb-16 md:pt-32 md:pb-24">
            <div className="container mx-auto px-4 md:px-6">
                <div className="flex flex-col items-center text-center max-w-4xl mx-auto">
                    <h1
                        className={`${SECTION_DISPLAY_TITLE_CLASS} mb-5 md:mb-6`}
                        style={{
                            margin: 0,
                            fontSize: "36px",
                            lineHeight: 1.08,
                            fontWeight: 900,
                            letterSpacing: "-0.02em",
                            color: "#111827",
                        }}
                    >
                        {PRICING_PAGE_H1}
                    </h1>
                    <p className="max-w-3xl mx-auto" style={PRICING_HERO_BODY_STYLE}>
                        {CATEGORY_ANCHOR_BODY}
                    </p>
                </div>
            </div>
        </section>
    );
}
