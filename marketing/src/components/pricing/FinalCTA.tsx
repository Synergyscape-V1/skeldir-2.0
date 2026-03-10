"use client";

import Link from "next/link";

// ============================================================================
// FINAL CTA SECTION
// Redesigned: Light theme, clean aesthetic, consistent with Hero
// ============================================================================

export function FinalCTA() {
    return (
        <section className="w-full bg-white py-24 px-6 text-center border-t border-gray-200">
            <div className="max-w-3xl mx-auto">
                <h2 className="text-3xl md:text-5xl font-bold text-slate-900 mb-6 tracking-tight">
                    Get started with Skeldir.
                </h2>
                <p className="text-lg text-slate-600 mb-10 max-w-2xl mx-auto">
                    Stop guessing where your money is going. Start making data-driven decisions today.
                </p>

                <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                    {/* Primary Button */}
                    <Link
                        href="/signup"
                        style={{
                            display: "inline-flex",
                            flexDirection: "column",
                            alignItems: "center",
                            justifyContent: "center",
                            minWidth: "220px",
                            height: "56px",
                            padding: "0 28px",
                            borderRadius: "999px",
                            border: "none",
                            background: "#2563EB",
                            color: "#FFFFFF",
                            fontSize: "16px",
                            fontWeight: 600,
                            boxShadow: "0 8px 24px rgba(37, 99, 235, 0.35)",
                            cursor: "pointer",
                            transition: "all 200ms ease-out",
                            lineHeight: "1.2",
                            textDecoration: "none",
                        }}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.background = "#1D4ED8";
                            e.currentTarget.style.boxShadow = "0 10px 30px rgba(37, 99, 235, 0.45)";
                            e.currentTarget.style.transform = "translateY(-1px)";
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.background = "#2563EB";
                            e.currentTarget.style.boxShadow = "0 8px 24px rgba(37, 99, 235, 0.35)";
                            e.currentTarget.style.transform = "translateY(0)";
                        }}
                    >
                        Get started
                        <span style={{ fontSize: "14px", fontWeight: 500 }}>$199/mo</span>
                    </Link>

                    {/* Secondary Button */}
                    <Link
                        href="/book-demo"
                        className="flex items-center justify-center bg-white border border-gray-200 text-slate-700 rounded-lg px-8 py-3.5 min-w-[200px] h-[66px] sm:h-auto transition-all duration-200 hover:bg-gray-50 hover:border-gray-300 hover:text-slate-900 font-semibold shadow-sm"
                    >
                        Contact Sales
                    </Link>
                </div>
            </div>
        </section>
    );
}
