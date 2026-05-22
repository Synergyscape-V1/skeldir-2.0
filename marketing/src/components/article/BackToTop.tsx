"use client";

import { useState, useEffect } from "react";
import { ArrowUp } from "lucide-react";

export function BackToTop() {
    const [isVisible, setIsVisible] = useState(false);
    const [isHovered, setIsHovered] = useState(false);

    useEffect(() => {
        const handleScroll = () => {
            // Show button after scrolling 500px
            setIsVisible(window.scrollY > 500);
        };

        window.addEventListener("scroll", handleScroll, { passive: true });
        handleScroll(); // Initial check

        return () => {
            window.removeEventListener("scroll", handleScroll);
        };
    }, []);

    const scrollToTop = () => {
        window.scrollTo({
            top: 0,
            behavior: "smooth",
        });
    };

    return (
        <button
            onClick={scrollToTop}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            className="fixed bottom-24 md:bottom-8 right-6 md:right-8 w-12 h-12 md:w-12 md:h-12 rounded-full flex items-center justify-center transition-all duration-300 z-40 shadow-lg hover:shadow-xl"
            style={{
                backgroundColor: isHovered ? "#3B82F6" : "#111827",
                opacity: isVisible ? 1 : 0,
                pointerEvents: isVisible ? "auto" : "none",
                transform: isVisible
                    ? "translateY(0) scale(1)"
                    : "translateY(20px) scale(0.8)",
            }}
            aria-label="Back to top"
        >
            <ArrowUp
                className="w-5 h-5 transition-transform duration-200"
                style={{
                    color: "white",
                    transform: isHovered ? "translateY(-2px)" : "translateY(0)",
                }}
            />
        </button>
    );
}
