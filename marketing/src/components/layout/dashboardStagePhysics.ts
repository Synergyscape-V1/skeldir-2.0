/** Intrinsic dashboard assets — width/height drive aspect-ratio everywhere */
export type DashboardStageAsset = {
  readonly src: string;
  readonly alt: string;
  readonly width: number;
  readonly height: number;
};

export const PRODUCT_HERO_ANALYZE_ASSET: DashboardStageAsset = {
  src: "/images/skeldir-analyze-channel-roas.png",
  alt: "Skeldir decision intelligence — analyze ROAS by marketing channel with AI-driven insights",
  width: 1438,
  height: 780,
} as const;

export const INTERACTIVE_DEMO_DASHBOARD_ASSET: DashboardStageAsset = {
  src: "/images/skeldir-dashboard-v2.png",
  alt: "Skeldir decision intelligence dashboard — verified revenue, confidence ranges, and budget control",
  width: 1200,
  height: 800,
} as const;

export function dashboardAspectRatio(asset: DashboardStageAsset): string {
  return `${asset.width} / ${asset.height}`;
}

/** Clip radius on glass shell — matches browser chrome in dashboard assets */
export const DASHBOARD_STAGE_CORNER_RADIUS = "20px";

/** Shared 3D stage CSS — one physics vocabulary sitewide */
export const DASHBOARD_STAGE_STYLES = `
  .demo-image-container {
    perspective: 1200px;
    perspective-origin: 50% 45%;
    width: 100%;
  }

  .demo-image-float-wrapper {
    position: relative;
    transform-style: preserve-3d;
    animation: demo-float 7s ease-in-out infinite;
    will-change: transform;
  }

  @keyframes demo-float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
  }

  .demo-image-float-wrapper::after {
    content: "";
    position: absolute;
    bottom: -22px;
    left: 14%;
    right: 14%;
    height: 50px;
    background: radial-gradient(
      ellipse at 50% 50%,
      rgba(0, 0, 0, 0.18) 0%,
      rgba(0, 0, 0, 0.06) 45%,
      transparent 75%
    );
    border-radius: 50%;
    z-index: -1;
    filter: blur(18px);
    pointer-events: none;
  }

  .demo-image-glass {
    position: relative;
    transform-style: preserve-3d;
    transform: translateX(0) scale(1.08) rotateY(-7deg) rotateX(4deg);
    transform-origin: center center;
    overflow: hidden;
    border-radius: ${DASHBOARD_STAGE_CORNER_RADIUS};
    isolation: isolate;
  }

  .demo-dashboard-image {
    display: block;
    width: 100%;
    height: auto;
    object-fit: contain;
    border-radius: inherit;
  }

  @media (prefers-reduced-motion: reduce) {
    .demo-image-float-wrapper {
      animation: none;
    }
  }

  @media (max-width: 767px) {
    .demo-image-container {
      perspective: 800px;
    }

    .demo-image-glass {
      transform: scale(1.02) rotateY(-3deg) rotateX(2deg);
    }

    .demo-image-float-wrapper::after {
      display: none;
    }
  }

  @media (min-width: 768px) and (max-width: 1023px) {
    .demo-image-glass {
      transform: scale(1.05) rotateY(-5deg) rotateX(3deg);
    }
  }

  @media (min-width: 1024px) {
    .demo-image-glass {
      transform: scale(1.1) rotateY(-8deg) rotateX(4deg);
    }

    .demo-dashboard-image {
      max-height: 640px;
    }
  }
`;
