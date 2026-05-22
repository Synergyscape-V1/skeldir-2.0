import React from 'react';
import Image from 'next/image';

// Using placeholder images for logos since we don't have the actual assets yet.
// In a real implementation, these would be imported from assets.
// For now, we'll use text or simple SVGs if possible, or just placeholders.
// Given the constraints, I'll use text representation styled to look like logos 
// or simple SVGs if I can inline them, but to keep it clean and fast, 
// I will assume we might need to fetch them or use a text fallback.
// Actually, the reference shows specific logos. I will create a component that 
// renders a grid of these logos. Since I don't have the SVG assets, 
// I will use a text-based representation for now to verify layout, 
// or simple colored blocks with names.
// BETTER APPROACH: Use a list of names and style them to look "logo-ish" 
// or use a reliable CDN for tech logos if allowed. 
// However, to be safe and self-contained, I'll use styled text for now.

const COMPANIES = [
    { name: 'Shopify', color: '#95BF47' },
    { name: 'Snowflake', color: '#29B5E8' },
    { name: 'Figma', color: '#F24E1E' },
    { name: 'Datadog', color: '#632CA6' },
    { name: 'Vercel', color: '#000000' },
    { name: 'Duolingo', color: '#58CC02' },
    { name: 'Ramp', color: '#C9F34F' },
    { name: 'Statsig', color: '#194B7D' },
];

export function SocialProofBanner() {
    return (
        <div className="mt-8 text-center space-y-6">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                Trusted by 65,000+ developers at top companies:
            </p>

            <div className="grid grid-cols-4 gap-x-8 gap-y-6 items-center justify-items-center opacity-60 grayscale hover:grayscale-0 transition-all duration-500">
                {/* 
          In a production environment, these would be <Image /> components.
          For this implementation without assets, we're using styled text 
          to represent the visual weight of the logos.
        */}
                {COMPANIES.map((company) => (
                    <div
                        key={company.name}
                        className="text-sm font-bold text-gray-400 hover:text-white transition-colors cursor-default"
                        title={company.name}
                    >
                        {company.name}
                    </div>
                ))}
            </div>
        </div>
    );
}
