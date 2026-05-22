"use client";

import { useState, useEffect } from "react";
import { Linkedin, Twitter, Share2 } from "lucide-react";

interface SocialShareProps {
    title: string;
    url: string;
}

export function SocialShare({ title, url }: SocialShareProps) {
    const [isVisible, setIsVisible] = useState(false);
    const [isMobile, setIsMobile] = useState(false);

    useEffect(() => {
        const checkMobile = () => {
            setIsMobile(window.innerWidth < 1024);
        };

        const handleScroll = () => {
            // Show after scrolling 300px
            setIsVisible(window.scrollY > 300);
        };

        checkMobile();
        handleScroll();

        window.addEventListener("resize", checkMobile);
        window.addEventListener("scroll", handleScroll, { passive: true });

        return () => {
            window.removeEventListener("resize", checkMobile);
            window.removeEventListener("scroll", handleScroll);
        };
    }, []);

    const shareText = {
        linkedin: `Why Your Attribution Numbers Never Match – Understanding the 16-40% discrepancy gap | via @Skeldir`,
        twitter: `Finally, a clear explanation for why platform attribution numbers never match your verified revenue. ${url}`,
    };

    const handleLinkedInShare = () => {
        const linkedInUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(
            url
        )}`;
        window.open(linkedInUrl, "_blank", "width=600,height=600");
    };

    const handleTwitterShare = () => {
        const twitterUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(
            shareText.twitter
        )}`;
        window.open(twitterUrl, "_blank", "width=600,height=400");
    };

    // Desktop: Fixed sidebar
    if (!isMobile) {
        return (
            <div
                className="fixed right-8 top-1/2 -translate-y-1/2 flex flex-col gap-3 transition-opacity duration-300 z-50"
                style={{ opacity: isVisible ? 1 : 0, pointerEvents: isVisible ? "auto" : "none" }}
            >
                <span
                    className="text-xs font-medium text-center mb-1"
                    style={{ color: "#9CA3AF", letterSpacing: "0.5px" }}
                >
                    SHARE
                </span>
                <button
                    onClick={handleLinkedInShare}
                    className="w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200 hover:scale-110"
                    style={{ backgroundColor: "#0A66C2" }}
                    aria-label="Share on LinkedIn"
                >
                    <Linkedin className="w-5 h-5 text-white" />
                </button>
                <button
                    onClick={handleTwitterShare}
                    className="w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200 hover:scale-110"
                    style={{ backgroundColor: "#000000" }}
                    aria-label="Share on X (Twitter)"
                >
                    <Twitter className="w-5 h-5 text-white" />
                </button>
            </div>
        );
    }

    // Mobile: Bottom sticky bar
    return (
        <div
            className="fixed bottom-0 left-0 right-0 px-4 py-3 flex items-center justify-center gap-4 transition-transform duration-300 z-50"
            style={{
                backgroundColor: "rgba(255, 255, 255, 0.95)",
                backdropFilter: "blur(10px)",
                borderTop: "1px solid #E5E7EB",
                transform: isVisible ? "translateY(0)" : "translateY(100%)",
            }}
        >
            <span
                className="text-sm font-medium flex items-center gap-2"
                style={{ color: "#6B7280" }}
            >
                <Share2 className="w-4 h-4" />
                Share
            </span>
            <button
                onClick={handleLinkedInShare}
                className="w-11 h-11 rounded-full flex items-center justify-center transition-transform duration-200 active:scale-95"
                style={{ backgroundColor: "#0A66C2" }}
                aria-label="Share on LinkedIn"
            >
                <Linkedin className="w-5 h-5 text-white" />
            </button>
            <button
                onClick={handleTwitterShare}
                className="w-11 h-11 rounded-full flex items-center justify-center transition-transform duration-200 active:scale-95"
                style={{ backgroundColor: "#000000" }}
                aria-label="Share on X (Twitter)"
            >
                <Twitter className="w-5 h-5 text-white" />
            </button>
        </div>
    );
}
