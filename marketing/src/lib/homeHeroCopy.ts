/**
 * Homepage hero headline — shared by HeroSection (client) and D4 JSON-LD / harness parity.
 * Must stay aligned with `HeroSection` aria-label and final typewriter phrase.
 */
export const HERO_HEADLINE_LEAD = "Every ad dollar traced, verified to the source—" as const;
export const HERO_TYPEWRITER_PREFIX = "So your AI Agents and teams " as const;
export const HERO_TYPEWRITER_SUFFIX_INITIAL = "never act on a guess." as const;
export const HERO_TYPEWRITER_SUFFIX_FINAL = "execute from confirmed truth." as const;

export const HERO_TYPEWRITER_PHRASE_INITIAL =
  `${HERO_TYPEWRITER_PREFIX}${HERO_TYPEWRITER_SUFFIX_INITIAL}` as const;
export const HERO_TYPEWRITER_PHRASE_FINAL =
  `${HERO_TYPEWRITER_PREFIX}${HERO_TYPEWRITER_SUFFIX_FINAL}` as const;

/** Accessible full headline after typewriter completes — matches JSON-LD WebPage `name`. */
export const HOME_PAGE_H1_ARIA_LABEL =
  `${HERO_HEADLINE_LEAD} ${HERO_TYPEWRITER_PHRASE_FINAL}` as const;
