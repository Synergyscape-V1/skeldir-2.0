// ============================================================================
// SOLUTION OVERVIEW SECTION — Static Image Replacement
// Renders the solution articulation as a single pre-composed image.
//
// Anti-failure strategy (lazy load / waterfall / render):
//   1. loading="eager"       → disables native lazy loading
//   2. decoding="sync"       → decoded before paint frame (no decode waterfall)
//   3. fetchPriority="high"  → browser prioritises this fetch in the queue
//   4. Explicit width/height → reserves layout space, prevents CLS
//   5. <link rel="preload">  → issued from layout.tsx <head> for early fetch
//   6. No overflow:hidden    → zero clipping on any viewport
//   7. CSS max-width:100%    → fluid responsive, height auto-scales
// ============================================================================

const IMG_SRC = "/assets/images/solution-articulation/solution-articulation-full.png";
const IMG_WIDTH = 2816;
const IMG_HEIGHT = 1396;
const ASPECT = IMG_HEIGHT / IMG_WIDTH; // ≈ 0.4957

export function SolutionOverview() {
  return (
    <section
      className="solution-overview-section"
      style={{
        backgroundColor: "#FFFFFF",
        padding: "44px 0 80px 0",
        position: "relative",
      }}
    >
      {/* Gradient transition overlay at the top — matches adjacent sections */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: "120px",
          background:
            "linear-gradient(to bottom, rgba(255,255,255,1) 0%, rgba(255,255,255,1) 100%)",
          pointerEvents: "none",
          zIndex: 1,
        }}
      />

      <style>{`
        .solution-img-wrapper {
          max-width: 1400px;
          margin: 0 auto;
          padding: 0 48px;
          position: relative;
          z-index: 2;
        }
        .solution-img-wrapper img {
          display: block;
          width: 100%;
          max-width: 100%;
          height: auto;
          border-radius: 12px;
          box-shadow: 0 4px 24px rgba(0,0,0,0.08);
        }
        @media (max-width: 1024px) {
          .solution-img-wrapper {
            padding: 0 32px;
          }
        }
        @media (max-width: 767px) {
          .solution-overview-section {
            padding: 27px 0 48px 0 !important;
          }
          .solution-img-wrapper {
            padding: 0 16px;
            overflow: visible;
          }
          .solution-img-wrapper img {
            border-radius: 8px;
            transform: scale(1.15);
            transform-origin: center center;
          }
        }
      `}</style>

      <div className="solution-img-wrapper">
        <img
          src={IMG_SRC}
          alt="Decision Intelligence, Not Just Dashboards — Skeldir's four-stage pipeline: Connect all platform signals, Reconcile via Bayesian Engine (deduplication, refund adjustment, probabilistic modelling), Verify against real bank transactions, and Decide with calibrated confidence intervals instead of single-point estimates."
          width={IMG_WIDTH}
          height={IMG_HEIGHT}
          loading="eager"
          decoding="sync"
          fetchPriority="high"
          style={{
            aspectRatio: `${IMG_WIDTH} / ${IMG_HEIGHT}`,
            contentVisibility: "visible",
          }}
        />
      </div>
    </section>
  );
}
