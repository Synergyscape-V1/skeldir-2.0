import { SECTION_DISPLAY_TITLE_CLASS } from "@/components/layout/sectionDisplayFont";
import {
  CATEGORY_ANCHOR_BODY,
  CATEGORY_ANCHOR_CLOSER_PARTS,
} from "@/lib/categoryAnchorCopy";

type CategoryAnchorProps = {
  /** Home: follows problem articulation. Pricing: bridges hero to tier cards. */
  variant: "home" | "pricing";
};

const VARIANT_STYLE = {
  home: {
    paddingTop: "56px",
    paddingBottom: "64px",
    background: "#fbfaf6",
    borderTop: "1px solid #E5E7EB",
    borderBottom: "1px solid #E5E7EB",
  },
  pricing: {
    paddingTop: "40px",
    paddingBottom: "48px",
    background: "#FFFFFF",
    borderTop: "1px solid #F3F4F6",
    borderBottom: "none",
  },
} as const;

export function CategoryAnchor({ variant }: CategoryAnchorProps) {
  const v = VARIANT_STYLE[variant];

  return (
    <section
      className="category-anchor-section"
      aria-label="How Skeldir differs from probabilistic attribution tools"
      style={{
        background: v.background,
        borderTop: v.borderTop,
        borderBottom: v.borderBottom,
        paddingTop: v.paddingTop,
        paddingBottom: v.paddingBottom,
      }}
    >
      <div
        style={{
          maxWidth: "896px",
          margin: "0 auto",
          textAlign: "center",
        }}
      >
        <p
          style={{
            margin: 0,
            fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
            fontSize: "17px",
            lineHeight: 1.55,
            fontWeight: 400,
            color: "#374151",
          }}
        >
          {CATEGORY_ANCHOR_BODY}
        </p>

        <p className={`category-anchor-closer ${SECTION_DISPLAY_TITLE_CLASS}`}>
          {CATEGORY_ANCHOR_CLOSER_PARTS.map((part, index) => (
            <span key={part} style={{ display: "contents" }}>
              {index > 0 ? (
                <span aria-hidden="true" className="category-anchor-closer__sep">
                  /
                </span>
              ) : null}
              <span className="category-anchor-closer__part">{part}</span>
            </span>
          ))}
        </p>
      </div>
    </section>
  );
}
