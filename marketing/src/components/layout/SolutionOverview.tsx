// ============================================================================
// SOLUTION OVERVIEW — Desktop single canvas + mobile vertical pipeline
//
// Desktop: one wide PNG (columnar pipeline in one frame).
// Mobile (≤767px): three crops from the same artwork, stacked top → bottom in
// causal order (sources → engine → dashboards), with SVG connectors as vertical
// down-links. Raster crops omit the artwork's horizontal-flow connector strips so
// only the vertical SVG bridges read as inter-stage flow on small viewports.
// Connector SVGs include subtle drifting “packet” dots (mobile-only CSS) along
// the stem — never on the stage images.
//
// Layout physics (CLS / decode / fetch):
//   • Explicit width/height on every <img> + matching aspect-ratio style
//   • Desktop: eager + sync decode + high fetch priority + preload (≥768px)
//   • Mobile stage 1: eager + high fetch priority + preload (≤767px)
//   • Mobile stages 2–3: lazy + async decode (below typical first viewport)
//   • Column split x ∈ {566, 1198} from luminance-gutter analysis on 1672×941
//
// Mobile figures are borderless (≤767px): no ring, no connector side rules.
// Desktop solution image is borderless; the ring treatment on
// .problem-statement-inner (≥768px) lives in ProblemStatementCandidate.
// ============================================================================

const IMG_FULL_SRC = "/assets/images/solution-articulation/solution-articulation-full.png";
const IMG_FULL_W = 1672;
const IMG_FULL_H = 941;

const MOBILE_STAGE_1_SRC =
  "/assets/images/solution-articulation/solution-mobile-stage-1-sources.png";
const MOBILE_STAGE_1_W = 451;
const MOBILE_STAGE_1_H = 825;

const MOBILE_STAGE_2_SRC =
  "/assets/images/solution-articulation/solution-mobile-stage-2-engine.png";
const MOBILE_STAGE_2_W = 526;
const MOBILE_STAGE_2_H = 790;

const MOBILE_STAGE_3_SRC =
  "/assets/images/solution-articulation/solution-mobile-stage-3-dashboard.png";
const MOBILE_STAGE_3_W = 430;
const MOBILE_STAGE_3_H = 825;

function PipelineConnectorDown() {
  return (
    <div className="solution-pipeline-connector" aria-hidden="true">
      <svg
        className="solution-pipeline-connector__svg"
        viewBox="0 0 56 96"
        width={56}
        height={96}
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Dotted stem — matches diagram connector language; dash drift mobile-only in CSS */}
        <line
          x1="28"
          y1="4"
          x2="28"
          y2="62"
          stroke="rgb(148, 163, 184)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="5 7"
        />
        {/* Teal flow nodes (static anchors) */}
        <circle cx="28" cy="4" r="4" fill="rgb(13, 148, 136)" />
        <circle cx="28" cy="62" r="4" fill="rgb(13, 148, 136)" />
        {/* Packet dots — travel top→bottom along stem; CSS animation scoped to ≤767px */}
        <g className="solution-pipeline-flow-dots">
          <g className="solution-pipeline-flow-dot solution-pipeline-flow-dot--1">
            <circle r="2.25" fill="rgb(13, 148, 136)" opacity="0.88" />
          </g>
          <g className="solution-pipeline-flow-dot solution-pipeline-flow-dot--2">
            <circle r="2" fill="rgb(45, 212, 191)" opacity="0.72" />
          </g>
          <g className="solution-pipeline-flow-dot solution-pipeline-flow-dot--3">
            <circle r="2.25" fill="rgb(13, 148, 136)" opacity="0.88" />
          </g>
        </g>
        {/* Down arrow */}
        <path
          d="M28 68 L28 88 M18 78 L28 90 L38 78"
          stroke="rgb(13, 148, 136)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>
    </div>
  );
}

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
          background-color: #ffffff;
        }
        .solution-overview-full {
          display: block;
          width: 100%;
          max-width: 100%;
          height: auto;
          border-radius: 12px;
          box-shadow: none;
          clip-path: inset(4px 4px 4px 4px);
        }
        .solution-overview-mobile-pipeline {
          display: none;
        }
        .solution-mobile-stage {
          margin: 0;
          width: 100%;
          max-width: 100%;
          box-sizing: border-box;
        }
        .solution-mobile-stage img {
          display: block;
          width: 100%;
          max-width: 100%;
          height: auto;
          box-shadow: none;
        }
        .solution-pipeline-connector {
          display: flex;
          justify-content: center;
          align-items: center;
          width: 100%;
          min-height: 72px;
          flex-shrink: 0;
          background: transparent;
        }
        .solution-pipeline-connector__svg {
          display: block;
        }

        @keyframes solution-pipeline-dot-drift {
          0% {
            transform: translate(28px, 12px);
            opacity: 0;
          }
          14% {
            opacity: 0.62;
          }
          86% {
            opacity: 0.62;
          }
          100% {
            transform: translate(28px, 52px);
            opacity: 0;
          }
        }

        @media (max-width: 1024px) {
          .solution-img-wrapper {
            padding: 0 32px;
          }
        }
        @media (max-width: 767px) {
          .solution-overview-section {
            padding: 30px 0 52px 0 !important;
          }
          .solution-img-wrapper {
            padding: 0 16px;
            overflow: visible;
            --sol-chassis-r: 14px;
            --sol-chassis-img-r: var(--sol-chassis-r);
          }
          .solution-overview-full {
            display: none !important;
          }
          .solution-overview-mobile-pipeline {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
            gap: 10px;
            --solution-pipeline-slot: min(90vw, 334px);
          }
          .solution-mobile-stage {
            max-width: var(--solution-pipeline-slot);
            width: 100%;
            padding: 0;
            border-radius: var(--sol-chassis-r);
            background: transparent;
            border: none;
            box-shadow: none;
          }
          .solution-mobile-stage img {
            border-radius: var(--sol-chassis-img-r);
          }
          .solution-pipeline-connector {
            max-width: var(--solution-pipeline-slot);
            min-height: 62px;
            margin: 0;
            border: none;
            box-sizing: border-box;
          }
          .solution-pipeline-connector__svg {
            transform: scale(0.88);
            transform-origin: center center;
          }

          /* Packet dots drift along connector stem only (≤767px); stage crops untouched */
          .solution-pipeline-flow-dot {
            animation: solution-pipeline-dot-drift 3.1s ease-in-out infinite;
            will-change: transform;
          }
          .solution-pipeline-flow-dot--1 {
            animation-delay: 0s;
          }
          .solution-pipeline-flow-dot--2 {
            animation-delay: 1.03s;
          }
          .solution-pipeline-flow-dot--3 {
            animation-delay: 2.06s;
          }
        }

        @media (max-width: 767px) and (prefers-reduced-motion: reduce) {
          .solution-pipeline-flow-dot {
            animation: none !important;
          }
        }
      `}</style>

      <div className="solution-img-wrapper">
        <img
          className="solution-overview-full"
          src={IMG_FULL_SRC}
          alt="Attribution intelligence engine dashboard mockup — Skeldir surfaces calibrated channel and campaign attribution with transparent modelling so finance and growth teams can defend budget shifts with evidence, not platform-reported aggregates alone."
          width={IMG_FULL_W}
          height={IMG_FULL_H}
          loading="eager"
          decoding="sync"
          fetchPriority="high"
          style={{
            aspectRatio: `${IMG_FULL_W} / ${IMG_FULL_H}`,
            contentVisibility: "visible",
          }}
        />

        <div
          className="solution-overview-mobile-pipeline"
          role="group"
          aria-label="Skeldir attribution pipeline in scroll order: ad platforms and data sources feed the Attribution Intelligence Engine, which powers the web dashboard and AI workspace."
        >
          <figure className="solution-mobile-stage">
            <img
              src={MOBILE_STAGE_1_SRC}
              alt="Ad platforms and connected data sources feeding Skeldir."
              width={MOBILE_STAGE_1_W}
              height={MOBILE_STAGE_1_H}
              loading="eager"
              decoding="sync"
              fetchPriority="high"
              sizes="(max-width: 767px) 334px, 0px"
              style={{
                aspectRatio: `${MOBILE_STAGE_1_W} / ${MOBILE_STAGE_1_H}`,
                contentVisibility: "visible",
              }}
            />
          </figure>

          <PipelineConnectorDown />

          <figure className="solution-mobile-stage">
            <img
              src={MOBILE_STAGE_2_SRC}
              alt="Skeldir Attribution Intelligence Engine — reconciliation, attribution, and incrementality."
              width={MOBILE_STAGE_2_W}
              height={MOBILE_STAGE_2_H}
              loading="lazy"
              decoding="async"
              sizes="(max-width: 767px) 334px, 0px"
              style={{
                aspectRatio: `${MOBILE_STAGE_2_W} / ${MOBILE_STAGE_2_H}`,
                contentVisibility: "auto",
              }}
            />
          </figure>

          <PipelineConnectorDown />

          <figure className="solution-mobile-stage">
            <img
              src={MOBILE_STAGE_3_SRC}
              alt="Web dashboard analytics and AI workspace integrations powered by Skeldir."
              width={MOBILE_STAGE_3_W}
              height={MOBILE_STAGE_3_H}
              loading="lazy"
              decoding="async"
              sizes="(max-width: 767px) 334px, 0px"
              style={{
                aspectRatio: `${MOBILE_STAGE_3_W} / ${MOBILE_STAGE_3_H}`,
                contentVisibility: "auto",
              }}
            />
          </figure>
        </div>
      </div>
    </section>
  );
}
