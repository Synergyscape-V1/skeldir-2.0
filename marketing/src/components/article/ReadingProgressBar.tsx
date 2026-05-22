"use client";

import { useState, useEffect } from "react";

export function ReadingProgressBar() {
    const [progress, setProgress] = useState(0);

    useEffect(() => {
        const calculateProgress = () => {
            const scrollTop = window.scrollY;
            const docHeight = document.documentElement.scrollHeight - window.innerHeight;
            const scrollPercent = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
            setProgress(Math.min(scrollPercent, 100));
        };

        // Initial calculation
        calculateProgress();

        // Add scroll listener with passive option for better performance
        window.addEventListener("scroll", calculateProgress, { passive: true });

        return () => {
            window.removeEventListener("scroll", calculateProgress);
        };
    }, []);

    return (
        <div
            className="fixed top-0 left-0 right-0 h-[3px] z-[9999]"
            style={{ backgroundColor: "transparent" }}
        >
            <div
                className="h-full transition-all duration-75 ease-out"
                style={{
                    width: `${progress}%`,
                    backgroundColor: "#3B82F6",
                    boxShadow: "0 0 10px rgba(59, 130, 246, 0.5)",
                }}
            />
        </div>
    );
}
