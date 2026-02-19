import type { CSSProperties, ReactNode } from "react";
import { bottomBullets, platformRows, type PlatformRow } from "./problemArticulationData";

type CandidateTheme = {
  pageBg: string;
  chartBg: string;
  calloutBg: string;
  budgetBar: string;
  blueStripe: string;
  greenBar: string;
  greenStripe: string;
  redHatch: string;
  over: string;
  under: string;
  border: string;
  headingColor: string;
  bodyColor: string;
  subduedText: string;
  maxWidth: string;
  titleSize: string;
  subtitleSize: string;
  chartTitleSize: string;
  radius: string;
  rowGap: string;
};

export type CandidateProps = {
  theme: CandidateTheme;
};

const CHART_MAX = 46;

function barPercent(value: number) {
  return `${(value / CHART_MAX) * 100}%`;
}

function usesDarkText(style: PlatformRow["revenueStyle"]) {
  return style === "greenWithWhiteHatch";
}

const NAV_HEIGHT_PX = 73;

export function ProblemStatementCandidate({ theme }: CandidateProps) {
  return (
    <section
      className="problem-statement-section"
      style={{
        background: "#ffffff",
        padding: `${Math.max(44, NAV_HEIGHT_PX + 8)}px 16px 52px`,
        scrollMarginTop: `${NAV_HEIGHT_PX}px`,
      }}
    >
      <div
        className="problem-statement-inner"
        style={{
          width: "100%",
          maxWidth: theme.maxWidth,
          margin: "0 auto",
          color: theme.bodyColor,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "20px" }}>
          <h2
            style={{
              margin: "0 0 12px",
              fontSize: theme.titleSize,
              lineHeight: 1.08,
              fontWeight: 900,
              color: theme.headingColor,
            }}
          >
            Why Your Current Attribution
            <br />
            Is Lying to You
          </h2>
          <p
            style={{
              margin: 0,
              fontSize: theme.subtitleSize,
              lineHeight: 1.45,
              color: theme.bodyColor,
              maxWidth: "1100px",
              marginInline: "auto",
            }}
          >
            Last-click and platform-reported numbers misallocate 35-50% of your budget. Here&apos;s what it looks like.
          </p>
        </div>

        <h3
          style={{
            margin: "0 0 18px",
            textAlign: "center",
            fontSize: theme.chartTitleSize,
            fontWeight: 800,
            lineHeight: 1.2,
            color: theme.headingColor,
          }}
        >
          Budget vs. Actual Revenue Contribution
        </h3>

        <div
          className="problem-statement-chart"
          style={{
            background: theme.chartBg,
            borderRadius: theme.radius,
            padding: "14px 14px",
            display: "flex",
            flexDirection: "column",
            gap: theme.rowGap,
          }}
        >
          {platformRows.map((row, index) => {
            const labelColor = row.status === "overfunded" ? theme.over : theme.under;
            const isLastRow = index === platformRows.length - 1;
            return (
              <div
                key={row.platform}
                className="problem-statement-chart-row"
                style={{
                  display: "grid",
                  gridTemplateColumns: "110px 1fr",
                  gap: "10px",
                  borderBottom: isLastRow ? undefined : "2px solid rgba(15, 23, 42, 0.22)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "4px",
                  }}
                >
                  <img
                    src={row.logoPath}
                    alt={`${row.platform} logo`}
                    loading="lazy"
                    decoding="async"
                    style={{ width: "38px", height: "38px", objectFit: "contain" }}
                  />
                  <span
                    style={{
                      fontSize: "12px",
                      fontWeight: 700,
                      lineHeight: 1.2,
                      textAlign: "center",
                      color: theme.headingColor,
                    }}
                  >
                    {row.platform}
                  </span>
                </div>

                <div
                  className="problem-statement-chart-bars"
                  style={{
                    position: "relative",
                    display: "flex",
                    flexDirection: "column",
                    gap: "6px",
                    paddingRight: row.annotation === "metaDualOver" ? "56px" : undefined,
                    backgroundImage:
                      "linear-gradient(to right, rgba(15, 23, 42, 0.08) 1px, transparent 1px)",
                    backgroundSize: "25% 100%",
                    backgroundPosition: "0 0",
                  }}
                >
                  <BarLine
                    width={barPercent(row.budget)}
                    label={`${row.budget}% Budget`}
                    styleKey={row.budgetStyle}
                    theme={theme}
                    preferDarkText={false}
                    overfundedSplitPercent={
                      row.budgetStyle === "blueWithRedHatch"
                        ? (row.revenue / row.budget) * 100
                        : undefined
                    }
                    annotation={
                      row.status === "underfunded" ? (
                        <InlineAnnotation
                          type="underfunded"
                          delta={row.delta}
                          color={labelColor}
                        />
                      ) : undefined
                    }
                  />
                  <BarLine
                    width={barPercent(row.revenue)}
                    label={`${row.revenue}% Actual Revenue`}
                    styleKey={row.revenueStyle}
                    theme={theme}
                    preferDarkText={row.revenueLabelWhite ? false : usesDarkText(row.revenueStyle)}
                    annotation={
                      row.status === "overfunded" ? (
                        <InlineAnnotation
                          type="overfunded"
                          delta={row.delta}
                          color={labelColor}
                        />
                      ) : undefined
                    }
                  />
                  {row.annotation === "metaDualOver" && <MetaBracketArrow color={labelColor} />}
                </div>
              </div>
            );
          })}
        </div>

        <div
          className="problem-statement-callout"
          style={{
            marginTop: "20px",
            marginLeft: "auto",
            marginRight: "auto",
            maxWidth: "750px",
            background: theme.calloutBg,
            border: `2px solid ${theme.border}`,
            borderRadius: "12px",
            padding: "18px 16px",
            textAlign: "center",
          }}
        >
          <h4
            style={{
              margin: "0 0 10px",
              fontSize: "25px",
              lineHeight: 1.2,
              fontWeight: 800,
              color: theme.headingColor,
            }}
          >
            Platform discrepancies don&apos;t discriminate by budget
          </h4>
          <ul
            style={{
              listStyle: "disc",
              paddingLeft: "24px",
              margin: "0 auto",
              fontSize: "15px",
              lineHeight: 1.45,
              color: theme.headingColor,
              display: "inline-block",
              textAlign: "left",
            }}
          >
            {bottomBullets.map((bullet) => (
              <li key={bullet}>{bullet}</li>
            ))}
          </ul>
          <p
            style={{
              margin: "12px 0 0",
              fontSize: "12px",
              color: theme.subduedText,
            }}
          >
            [Source: Skeldir analysis of 200+ ecommerce brands]
          </p>
        </div>
      </div>

      <style>{responsiveStyles}</style>
    </section>
  );
}

function InlineAnnotation({
  type,
  delta,
  color,
}: {
  type: "overfunded" | "underfunded";
  delta: number;
  color: string;
}) {
  if (type === "overfunded") {
    return (
      <span
        className="problem-statement-annotation problem-statement-annotation--over"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          marginLeft: "10px",
          whiteSpace: "nowrap",
        }}
      >
        <LeftArrow color={color} />
        <span
          style={{
            color,
            fontSize: "13px",
            fontWeight: 800,
            letterSpacing: "0.01em",
          }}
        >
          OVERFUNDED by {delta}%
        </span>
      </span>
    );
  }
  return (
    <span
      className="problem-statement-annotation problem-statement-annotation--under"
      style={{
        display: "inline-flex",
        flexDirection: "column",
        alignItems: "flex-start",
        gap: "4px",
        marginLeft: "10px",
        whiteSpace: "nowrap",
        lineHeight: 1,
      }}
    >
      <span
        style={{
          color,
          fontSize: "13px",
          fontWeight: 800,
          letterSpacing: "0.01em",
          lineHeight: 1,
        }}
      >
        UNDERFUNDED by {delta}%
      </span>
      <CurvedDownArrow color={color} />
    </span>
  );
}

function LeftArrow({ color }: { color: string }) {
  return (
    <svg
      className="problem-statement-arrow problem-statement-arrow--left"
      width="22"
      height="14"
      viewBox="0 0 22 14"
      fill="none"
      aria-hidden
      style={{ flexShrink: 0 }}
    >
      <line
        x1="21"
        y1="7"
        x2="8"
        y2="7"
        stroke={color}
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <polygon points="0,7 9,2 9,12" fill={color} />
    </svg>
  );
}

function CurvedDownArrow({ color }: { color: string }) {
  return (
    <svg
      className="problem-statement-arrow problem-statement-arrow--curved"
      width="32"
      height="26"
      viewBox="0 0 32 26"
      fill="none"
      aria-hidden
      style={{ flexShrink: 0, display: "block" }}
    >
      <path
        d="M3 4 C12 4, 20 10, 24 19"
        stroke={color}
        strokeWidth="2.5"
        fill="none"
        strokeLinecap="round"
      />
      <polygon points="24,25 19,17 29,17" fill={color} />
    </svg>
  );
}

function MetaBracketArrow({ color }: { color: string }) {
  return (
    <svg
      className="problem-statement-meta-bracket-arrow"
      width="36"
      height="66"
      viewBox="0 0 36 66"
      fill="none"
      aria-hidden
      style={{ position: "absolute", right: "12px", top: "0" }}
    >
      <path
        d="M8 51 C26 49, 32 41, 32 33 C32 25, 26 17, 8 15"
        stroke={color}
        strokeWidth="2.5"
        fill="none"
        strokeLinecap="round"
      />
      <polygon points="2,15 11,10 11,20" fill={color} />
    </svg>
  );
}

type BarLineProps = {
  width: string;
  label: string;
  styleKey: PlatformRow["budgetStyle"] | PlatformRow["revenueStyle"];
  theme: CandidateTheme;
  preferDarkText: boolean;
  /** When budget bar is overfunded, gray ends (and red hatch starts) at this % of bar width. Should match revenue/budget so red aligns with where actual-revenue bar ends. */
  overfundedSplitPercent?: number;
  annotation?: ReactNode;
};

function BarLine({
  width,
  label,
  styleKey,
  theme,
  preferDarkText,
  overfundedSplitPercent,
  annotation,
}: BarLineProps) {
  const numeric = Number.parseFloat(width);
  const tiny = numeric < 30;
  const textColor = preferDarkText ? "#0f172a" : "#ffffff";
  const splitPercent = overfundedSplitPercent ?? 86;

  const barStyle: CSSProperties = {
    position: "relative",
    width,
    minWidth: "110px",
    height: "28px",
    borderRadius: "2px",
    border: "1px solid rgba(15,23,42,0.2)",
    boxSizing: "border-box",
    overflow: "hidden",
    flexShrink: 0,
  };

  const barClassName = "problem-statement-bar";
  const wrapClassName = "problem-statement-bar-wrap";

  if (styleKey === "blue") {
    barStyle.background = theme.budgetBar;
  }
  if (styleKey === "green") {
    barStyle.background = theme.greenBar;
  }
  if (styleKey === "blueWithRedHatch") {
    barStyle.background = `linear-gradient(to right, ${theme.budgetBar} 0%, ${theme.budgetBar} ${splitPercent}%, transparent ${splitPercent}%), repeating-linear-gradient(135deg, ${theme.redHatch}, ${theme.redHatch} 8px, #fca5a5 8px, #fca5a5 16px)`;
  }
  if (styleKey === "greenWithWhiteHatch") {
    barStyle.background = `repeating-linear-gradient(135deg, ${theme.greenBar}, ${theme.greenBar} 9px, ${theme.greenStripe} 9px, ${theme.greenStripe} 18px)`;
  }

  return (
    <div className={wrapClassName} style={{ display: "flex", alignItems: "center", minHeight: "34px" }}>
      <div className={barClassName} style={barStyle} data-label={label}>
        {!tiny ? (
          <span
            className="problem-statement-bar-label-inside"
            style={{
              position: "absolute",
              right:
                styleKey === "blueWithRedHatch"
                  ? `calc(${100 - splitPercent}% + 8px)`
                  : "8px",
              top: "50%",
              transform: "translateY(-50%)",
              fontSize: "12px",
              fontWeight: 700,
              color: textColor,
              whiteSpace: "nowrap",
              textShadow:
                textColor === "#ffffff"
                  ? "0 0 1px rgba(0,0,0,0.6), 0 1px 2px rgba(0,0,0,0.4)"
                  : undefined,
            }}
          >
            {label}
          </span>
        ) : null}
      </div>
      {tiny ? (
        <span
          className="problem-statement-bar-label-outside"
          style={{
            marginLeft: "8px",
            fontSize: "12px",
            fontWeight: 700,
            color: "#0f172a",
            whiteSpace: "nowrap",
          }}
        >
          {label}
        </span>
      ) : null}
      {/* Mobile: show label outside bar for all bars */}
      {!tiny ? (
        <span
          className="problem-statement-bar-label-outside problem-statement-bar-label-outside-mobile"
          style={{
            marginLeft: "8px",
            fontSize: "12px",
            fontWeight: 700,
            color: "#0f172a",
            whiteSpace: "nowrap",
            display: "none",
          }}
        >
          {label}
        </span>
      ) : null}
      {annotation}
    </div>
  );
}

const responsiveStyles = `
  @media (max-width: 1024px) {
    h2 { font-size: 34px !important; }
    h3 { font-size: 21px !important; }
    h4 { font-size: 22px !important; }
  }

  /* Mobile: scale down component by ~1.8x (scale 0.55) with scientific centering */
  @media (max-width: 767px) {
    .problem-statement-section {
      display: flex;
      flex-direction: column;
      align-items: center;
      overflow: visible;
      padding-left: 12px !important;
      padding-right: 12px !important;
    }
    .problem-statement-inner {
      transform: scale(0.825);
      transform-origin: center top;
      /* Compensate for layout box: scaled content is ~17.5% smaller, pull up next section */
      margin-bottom: -15vh !important;
    }
    h2 { font-size: 30px !important; }
    h3 { font-size: 19px !important; }
    h4 { font-size: 20px !important; }
    section ul { font-size: 14px !important; }

    /* Callout box: lower by 0.2 (reduce margin-top by 20%) and maintain desktop shape */
    .problem-statement-callout {
      margin-top: 16px !important;
      max-width: 750px !important;
      border-radius: 12px !important;
      padding: 18px 16px !important;
    }

    /* Chart: keep logos beside bars; use narrower logo column and allow bars to shrink */
    .problem-statement-chart-row {
      grid-template-columns: 62px minmax(0, 1fr) !important;
      gap: 6px !important;
      padding-bottom: 6px !important;
    }
    .problem-statement-chart-row .problem-statement-bar {
      min-width: 0 !important;
      height: 18px !important;
    }
    /* Hide label inside bar on mobile */
    .problem-statement-chart-row .problem-statement-bar .problem-statement-bar-label-inside {
      display: none !important;
    }
    /* Show label outside bar on mobile */
    .problem-statement-chart-row .problem-statement-bar-label-outside-mobile {
      display: inline-block !important;
    }
    .problem-statement-chart-row .problem-statement-bar span {
      font-size: 11px !important;
      line-height: 1.2 !important;
    }
    .problem-statement-chart-row .problem-statement-bar-wrap {
      min-height: auto !important;
      display: block !important;
    }
    .problem-statement-chart {
      padding: 10px 8px !important;
      gap: 2px !important;
      overflow: visible !important;
    }
    .problem-statement-chart-bars {
      padding-right: 4px !important;
      min-width: 0 !important;
      overflow: visible !important;
      gap: 4px !important;
    }
    /* Slightly smaller logo on mobile to keep bars visible */
    .problem-statement-chart-row > div:first-child img {
      width: 28px !important;
      height: 28px !important;
    }
    .problem-statement-chart-row > div:first-child span {
      font-size: 10px !important;
      line-height: 1.1 !important;
    }
    .problem-statement-chart-row .problem-statement-bar-wrap > span {
      display: inline-block !important;
      margin-left: 0 !important;
      margin-top: 3px !important;
      font-size: 11px !important;
      white-space: nowrap !important;
    }
    .problem-statement-annotation {
      display: inline-flex !important;
      margin-left: 0 !important;
      margin-top: 40px !important;
      max-width: 100% !important;
      white-space: nowrap !important;
      font-size: 11px !important;
      line-height: 1.2 !important;
      vertical-align: middle !important;
    }
    /* Add spacing between tiny label and annotation on mobile - more specific rule */
    .problem-statement-chart-row .problem-statement-bar-wrap > span + .problem-statement-annotation {
      margin-top: 16px !important;
      display: block !important;
    }
    .problem-statement-annotation--under {
      flex-direction: row !important;
      align-items: center !important;
      gap: 4px !important;
    }
    .problem-statement-arrow--left {
      width: 17px !important;
      height: 11px !important;
    }
    .problem-statement-arrow--curved {
      width: 22px !important;
      height: 16px !important;
    }
    .problem-statement-meta-bracket-arrow {
      width: 24px !important;
      height: 46px !important;
      right: 2px !important;
      top: 2px !important;
    }
    /* Hide all arrows on mobile */
    .problem-statement-annotation svg,
    .inline-annotation svg,
    .inline-annotation-underfunded svg,
    .inline-annotation-overfunded svg,
    .problem-statement-meta-bracket-arrow {
      display: none !important;
    }
  }
`;
