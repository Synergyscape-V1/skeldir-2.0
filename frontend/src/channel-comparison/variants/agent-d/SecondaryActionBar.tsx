import React, { useEffect, useRef, useState } from "react";
import { formatCurrency } from "../../../lib/formatters";
import type { BudgetRecommendation } from "../../../types/comparison";

interface SecondaryActionBarProps {
  recommendation: BudgetRecommendation | null;
  heroRef: React.RefObject<HTMLElement | null>;
}

export function SecondaryActionBar({ recommendation, heroRef }: SecondaryActionBarProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const target = heroRef.current;
    if (!target) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        setVisible(!entry.isIntersecting);
      },
      { threshold: 0 }
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [heroRef]);

  if (!recommendation) return null;

  return (
    <div className={`cc-d-action-bar ${visible ? "cc-d-action-bar-visible" : ""}`}>
      <span className="cc-d-action-bar-text">
        Shift {formatCurrency(recommendation.shiftAmount)} from {recommendation.fromChannelName} to{" "}
        {recommendation.toChannelName}
      </span>
      <a href="/budget?source=comparison" className="cc-d-action-bar-cta">
        Review in Budget Optimizer
      </a>
    </div>
  );
}
