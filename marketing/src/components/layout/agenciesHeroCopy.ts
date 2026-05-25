/** Agencies hero headline — one string per tone block; order is layout-stable */
export const AGENCIES_HERO_HEADLINE_LEAD =
  "One verification layer across every client account—";
export const AGENCIES_HERO_HEADLINE_ACCENT =
  "so your agency owns the revenue truth your clients' ad platforms can't be trusted to report.";

/** Visible and assistive headline — lead, space, accent (matches DOM text order). */
export const AGENCIES_PAGE_H1_TEXT = `${AGENCIES_HERO_HEADLINE_LEAD} ${AGENCIES_HERO_HEADLINE_ACCENT}`;

export const AGENCIES_HERO_HEADLINE_ARIA_LABEL = AGENCIES_PAGE_H1_TEXT;

/** First hero body paragraph — must match JSON-LD / page meta where used for D4 parity. */
export const AGENCIES_HERO_SUBHEAD =
  "Skeldir delivers Bayesian confidence ranges for multi-client portfolios—exposing platform over-reporting discrepancies, eliminating manual reconciliation cycles, with deployment measured in days instead of months.";
