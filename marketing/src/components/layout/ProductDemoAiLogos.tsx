import { PRODUCT_DEMO_AI_TOOLS } from "@/components/layout/aiToolLogos";
import {
  PRODUCT_DEMO_AI_LOGOS_STYLES,
  PRODUCT_HERO_AI_LOGOS_MOBILE_STYLES,
} from "@/components/layout/productDemoAiLogosPhysics";

type ProductDemoAiLogosProps = {
  className?: string;
};

export function ProductDemoAiLogos({ className = "" }: ProductDemoAiLogosProps) {
  const rowClass = className
    ? `product-demo-ai-logos ${className}`
    : "product-demo-ai-logos";
  const isProductHero = className.includes("product-hero__ai-logos");

  return (
    <>
      <div
        className={rowClass}
        role="list"
        aria-label="Compatible AI tools and agents"
      >
        {PRODUCT_DEMO_AI_TOOLS.map((tool) => (
          <div
            key={tool.id}
            role="listitem"
            className="product-demo-ai-logo"
            title={tool.name}
          >
            <img
              src={tool.logoSrc}
              alt={tool.name}
              height={tool.heightPx}
              loading="lazy"
              decoding="async"
              className={`product-demo-ai-logo-img product-demo-ai-logo-img--${tool.id}`}
            />
          </div>
        ))}
      </div>
      <style>
        {PRODUCT_DEMO_AI_LOGOS_STYLES}
        {isProductHero ? PRODUCT_HERO_AI_LOGOS_MOBILE_STYLES : ""}
      </style>
    </>
  );
}
