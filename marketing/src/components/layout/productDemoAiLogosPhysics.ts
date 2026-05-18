/** AI tool logo row — shared layout physics (InteractiveDemo + product hero) */
export const PRODUCT_DEMO_AI_LOGOS_STYLES = `
  .product-demo-ai-logos {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: 20px 32px;
    width: 100%;
    max-width: 720px;
    min-height: 36px;
    margin: 0;
    padding: 4px 0;
  }

  .product-demo-ai-logo {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 auto;
    height: 32px;
  }

  .product-demo-ai-logo-img {
    display: block;
    width: auto;
    height: 100%;
    max-height: 32px;
    object-fit: contain;
  }

  .product-demo-ai-logo-img--claude {
    height: 28px;
    max-height: 28px;
  }

  .product-demo-ai-logo-img--chatgpt {
    height: 26px;
    max-height: 26px;
  }

  .product-demo-ai-logo-img--gemini {
    height: 30px;
    max-height: 30px;
  }

  .product-demo-ai-logo-img--perplexity {
    height: 26px;
    max-height: 26px;
  }

  .product-demo-ai-logo-img--cursor {
    height: 26px;
    max-height: 26px;
    color: #171717;
  }
`;

/**
 * Product hero mobile — logo row must not form a painted box on the gradient canvas.
 * (min-height/padding from base row + compositing bleed from 3D stage above)
 */
export const PRODUCT_HERO_AI_LOGOS_MOBILE_STYLES = `
  @media (max-width: 767px) {
    .product-hero__ai-logos.product-demo-ai-logos {
      min-height: 0;
      padding: 0;
      margin: 0;
      border: none;
      box-shadow: none;
      background: transparent;
    }

    .product-hero__ai-logos .product-demo-ai-logo,
    .product-hero__ai-logos .product-demo-ai-logo-img {
      border: none;
      box-shadow: none;
      background: transparent;
    }
  }
`;
