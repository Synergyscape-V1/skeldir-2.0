"use client";

import { useState, type ReactNode } from "react";
import { Footer } from "@/components/layout/Footer";
import { CategoryFilter } from "@/components/resources/CategoryFilter";
import type { CategoryFilter as CategoryFilterType } from "@/data/articlesData";

type ResourcesPageClientProps = {
    /** Pre-rendered server content per category (RSC composition — do not import article grid/hero here). */
    sections: Record<CategoryFilterType, ReactNode>;
};

export function ResourcesPageClient({ sections }: ResourcesPageClientProps) {
    const [activeCategory, setActiveCategory] = useState<CategoryFilterType>("All");

    return (
        <div className="min-h-screen flex flex-col bg-white">
            <main className="flex-grow pt-20">
                <header className="w-full pt-12 md:pt-16 lg:pt-20 pb-4 md:pb-6 text-center">
                    <div className="container mx-auto px-4 md:px-6">
                        <h1
                            className="mb-4"
                            style={{
                                fontFamily: "var(--font-manrope), ui-sans-serif, system-ui, sans-serif",
                                fontSize: "clamp(36px, 6vw, 56px)",
                                lineHeight: "1.1",
                                color: "#111827",
                                fontWeight: 700,
                                letterSpacing: "-0.03em",
                            }}
                        >
                            What&apos;s new at Skeldir?
                        </h1>
                        <p
                            className="max-w-2xl mx-auto"
                            style={{
                                fontSize: "18px",
                                lineHeight: "1.6",
                                color: "#4B5563",
                            }}
                        >
                            Learn how to navigate attribution discrepancies, understand ROAS ranges, and defend budget
                            shifts with evidence-based frameworks.
                        </p>
                    </div>
                </header>

                <CategoryFilter activeCategory={activeCategory} onCategoryChange={setActiveCategory} />

                {sections[activeCategory]}
            </main>

            <Footer />
        </div>
    );
}
