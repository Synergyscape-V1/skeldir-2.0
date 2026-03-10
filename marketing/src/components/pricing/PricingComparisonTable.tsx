"use client";

import React, { useState } from "react";
import { Check, X, ChevronDown, ChevronUp } from "lucide-react";

// ============================================================================
// PRICING COMPARISON TABLE
// Simplified "Key Differences" view
// ============================================================================

// =============================================================================
// TYPES & DATA
// =============================================================================

type FeatureValue = string | boolean;

interface FeatureItem {
    name: string;
    starter: FeatureValue;
    pro: FeatureValue;
    enterprise: FeatureValue;
}

// Simplified data structure - Flat list of key differentiators
const keyDifferences: FeatureItem[] = [
    { name: "Platform Integrations", starter: "3 platforms", pro: "Unlimited", enterprise: "Unlimited" },
    { name: "Attribution Models", starter: "Basic", pro: "Full Bayesian", enterprise: "Custom Bayesian" },
    { name: "Data Retention", starter: "90 days", pro: "1 year", enterprise: "Unlimited" },
    { name: "Budget Optimization", starter: false, pro: "AI-Assisted", enterprise: "Custom Rules" },
    { name: "Support Level", starter: "Self-serve", pro: "Priority Email", enterprise: "Dedicated CSM" },
    { name: "Onboarding", starter: "Self-serve", pro: "Assisted", enterprise: "White-glove" },
];

// =============================================================================
// HELPER COMPONENTS
// =============================================================================

function ValueCell({ value }: { value: FeatureValue }) {
    if (value === true) {
        return (
            <div className="flex justify-center">
                <Check className="w-5 h-5 text-emerald-500" aria-label="Included" />
            </div>
        );
    }
    if (value === false) {
        return (
            <div className="flex justify-center">
                <div className="w-4 h-0.5 bg-gray-300 rounded-full" aria-label="Not included" />
            </div>
        );
    }
    return (
        <span className="text-sm text-slate-600 font-medium text-center block">
            {value}
        </span>
    );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function PricingComparisonTable() {
    return (
        <section className="w-full bg-white py-16 md:py-24 border-t border-gray-100">
            <div className="container mx-auto px-4 md:px-6 max-w-6xl">
                <div className="text-center mb-12">
                    <h2 className="text-2xl md:text-3xl font-bold text-slate-900 mb-3">Compare Key Differences</h2>
                    <p className="text-slate-500">A quick look at what sets each plan apart.</p>
                </div>

                {/* DESKTOP TABLE (>= 1024px) */}
                <div className="hidden lg:block overflow-hidden rounded-2xl border border-gray-200 shadow-sm">
                    <table className="w-full border-collapse bg-white text-left text-sm">
                        <caption className="sr-only">Pricing plan feature comparison</caption>
                        <thead>
                            <tr className="bg-gray-50/80 border-b border-gray-200">
                                <th scope="col" className="p-6 font-semibold text-slate-900 w-1/4">Feature</th>
                                <th scope="col" className="p-6 text-center w-1/4 font-bold text-slate-900">Starter</th>
                                <th scope="col" className="p-6 text-center w-1/4 font-bold text-blue-600 bg-blue-50/30">Pro</th>
                                <th scope="col" className="p-6 text-center w-1/4 font-bold text-slate-900">Enterprise</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {keyDifferences.map((item) => (
                                <tr key={item.name} className="hover:bg-gray-50/50 transition-colors">
                                    <th scope="row" className="px-6 py-4 font-medium text-slate-700">
                                        {item.name}
                                    </th>
                                    <td className="px-6 py-4">
                                        <ValueCell value={item.starter} />
                                    </td>
                                    <td className="px-6 py-4 bg-blue-50/10">
                                        <ValueCell value={item.pro} />
                                    </td>
                                    <td className="px-6 py-4">
                                        <ValueCell value={item.enterprise} />
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* MOBILE ACCORDION (< 1024px) */}
                <div className="lg:hidden space-y-6">
                    {/* Starter Tier */}
                    <MobileTierCard
                        name="Starter"
                        price="$199/mo"
                        data={keyDifferences}
                        tierKey="starter"
                    />
                    {/* Pro Tier */}
                    <MobileTierCard
                        name="Pro"
                        price="$499/mo"
                        data={keyDifferences}
                        tierKey="pro"
                        isPopular
                    />
                    {/* Enterprise Tier */}
                    <MobileTierCard
                        name="Enterprise"
                        price="$999/mo"
                        data={keyDifferences}
                        tierKey="enterprise"
                    />
                </div>
            </div>
        </section>
    );
}

// =============================================================================
// MOBILE TIER CARD COMPONENT
// =============================================================================

function MobileTierCard({
    name,
    price,
    data,
    tierKey,
    isPopular,
}: {
    name: string;
    price: string;
    data: FeatureItem[];
    tierKey: "starter" | "pro" | "enterprise";
    isPopular?: boolean;
}) {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <div className={`rounded-xl border ${isPopular ? 'border-blue-200 shadow-md ring-1 ring-blue-100' : 'border-gray-200 shadow-sm'} bg-white overflow-hidden`}>
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full p-5 flex items-center justify-between text-left focus:outline-none"
            >
                <div>
                    <div className="flex items-center gap-2">
                        <h3 className={`text-lg font-bold ${isPopular ? 'text-blue-600' : 'text-slate-900'}`}>{name}</h3>
                        {isPopular && (
                            <span className="bg-blue-100 text-blue-700 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide">
                                Popular
                            </span>
                        )}
                    </div>
                    <p className="text-sm font-medium text-slate-500 mt-1">{price}</p>
                </div>
                <div className={`p-2 rounded-full ${isOpen ? 'bg-gray-100' : 'bg-transparent'}`}>
                    {isOpen ? <ChevronUp className="w-5 h-5 text-slate-500" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
                </div>
            </button>

            {isOpen && (
                <div className="border-t border-gray-100 bg-gray-50/30 px-5 py-4 space-y-3">
                    {data.map((item) => (
                        <div key={item.name} className="flex justify-between items-center gap-4 text-sm">
                            <span className="text-slate-600 font-medium">{item.name}</span>
                            <div className="flex-shrink-0">
                                <ValueCell value={item[tierKey]} />
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
