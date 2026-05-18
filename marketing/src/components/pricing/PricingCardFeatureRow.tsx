import { PRICING_CARD_BODY_CLASS, PRICING_CARD_FEATURE_ROW_CLASS } from "@/components/pricing/pricingCardTypography";

function CheckmarkIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
      <path
        d="M13.5 4.5L6 12L2.5 8.5"
        stroke="#2563EB"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function PricingCardFeatureRow({ text }: { text: string }) {
  return (
    <div className={PRICING_CARD_FEATURE_ROW_CLASS}>
      <CheckmarkIcon />
      <span className={PRICING_CARD_BODY_CLASS}>{text}</span>
    </div>
  );
}
