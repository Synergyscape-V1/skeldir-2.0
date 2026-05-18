"use client";

import Link from "next/link";
import { DashboardStage } from "@/components/layout/DashboardStage";
import { INTERACTIVE_DEMO_DASHBOARD_ASSET } from "@/components/layout/dashboardStagePhysics";
import { ProductDemoAiLogos } from "@/components/layout/ProductDemoAiLogos";
import { SECTION_DISPLAY_TITLE_CLASS } from "@/components/layout/sectionDisplayFont";

const DEMO_COPY_LINES = [
  "Your AI stack needs data it can trust, not dashboards it has to interpret.",
  "Skeldir's MCP connection gives any agent direct access to verified revenue—ask questions, shift budgets, take action.",
] as const;

const DEMO_STAGE_MAX_WIDTH = "1100px";

// =============================================================================
// MAIN COMPONENT EXPORT
// =============================================================================
export function InteractiveDemo() {
  return (
    <section
      id="product-demo-section"
      role="region"
      aria-labelledby="demo-section-title"
      className="product-demo-section"
    >
      <div className="product-demo-inner">
        <h2
          id="demo-section-title"
          className={`product-demo-title ${SECTION_DISPLAY_TITLE_CLASS}`}
        >
          See Skeldir in Action
        </h2>

        <p id="demo-section-copy" className="product-demo-copy">
          {DEMO_COPY_LINES.map((line) => (
            <span key={line} className="product-demo-copy-line">
              {line}
            </span>
          ))}
        </p>

        <ProductDemoAiLogos className="product-demo-ai-logos--section" />

        {/* 3D stage — same physics vocabulary as hero product visual */}
        <div
          className="demo-dashboard-stage"
          style={{ maxWidth: DEMO_STAGE_MAX_WIDTH }}
        >
          <DashboardStage asset={INTERACTIVE_DEMO_DASHBOARD_ASSET} />
        </div>

        <div className="product-demo-cta-row">
          <Link href="/book-demo" className="product-demo-cta">
            See your revenue discrepancies
          </Link>
        </div>
      </div>

      <style>{`
        .product-demo-section {
          width: 100%;
          padding: 80px 48px;
          background-color: #ffffff;
          display: flex;
          flex-direction: column;
          align-items: center;
          overflow: visible;
          position: relative;
        }

        .product-demo-inner {
          width: 100%;
          max-width: 1440px;
          margin: 0 auto;
          display: flex;
          flex-direction: column;
          align-items: center;
          position: relative;
          z-index: 2;
        }

        .product-demo-title {
          font-size: 48px;
          font-weight: 700;
          line-height: 1.2;
          letter-spacing: -0.02em;
          color: #0f172a;
          text-align: center;
          margin: 0 0 20px;
        }

        .product-demo-copy {
          max-width: 720px;
          margin: 0 0 20px;
          text-align: center;
          font-family: Inter, ui-sans-serif, system-ui, sans-serif;
          font-size: 18px;
          font-weight: 400;
          line-height: 1.6;
          color: #475569;
        }

        .product-demo-copy-line {
          display: block;
        }

        .product-demo-copy-line + .product-demo-copy-line {
          margin-top: 8px;
        }

        .product-demo-ai-logos--section {
          margin-bottom: 40px;
        }

        .demo-dashboard-stage {
          width: 100%;
          margin: 0 auto 40px;
        }

        .product-demo-cta-row {
          display: flex;
          justify-content: center;
        }

        .product-demo-cta {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 260px;
          height: 52px;
          padding: 0 28px;
          background-color: #2563eb;
          color: #ffffff;
          font-family: Inter, ui-sans-serif, system-ui, sans-serif;
          font-size: 16px;
          font-weight: 600;
          border-radius: 12px;
          text-decoration: none;
          box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
          transition: background 150ms ease, transform 150ms ease, box-shadow 150ms ease;
        }

        .product-demo-cta:hover {
          background-color: #1d4ed8;
          transform: translateY(-2px);
          box-shadow: 0 8px 20px rgba(37, 99, 235, 0.45);
        }

        .product-demo-cta:focus-visible {
          outline: 3px solid #93c5fd;
          outline-offset: 3px;
        }

        @media (max-width: 767px) {
          .product-demo-section {
            padding: 48px 20px;
          }

          .product-demo-title {
            font-size: 32px;
            line-height: 1.25;
            margin-bottom: 16px;
            padding: 0 8px;
          }

          .product-demo-copy {
            font-size: 16px;
            line-height: 1.55;
            margin-bottom: 16px;
            padding: 0 8px;
            text-align: left;
          }

          .product-demo-ai-logos {
            justify-content: flex-start;
            gap: 16px 24px;
            margin-bottom: 28px;
            padding: 0 8px;
          }

          .demo-dashboard-stage {
            margin-bottom: 28px;
          }

          .product-demo-cta {
            width: 100%;
            max-width: 100%;
          }
        }

      `}</style>
    </section>
  );
}
