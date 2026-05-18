/** Self-hosted product marks — paths under /public/images/ai-tools */
export type AiToolLogo = {
  id: string;
  name: string;
  logoSrc: string;
  /** Fixed visual height (px) — width follows aspect ratio */
  heightPx: number;
};

export const PRODUCT_DEMO_AI_TOOLS: readonly AiToolLogo[] = [
  {
    id: "claude",
    name: "Claude",
    logoSrc: "/images/ai-tools/claude.svg",
    heightPx: 28,
  },
  {
    id: "chatgpt",
    name: "ChatGPT",
    logoSrc: "/images/ai-tools/chatgpt.svg",
    heightPx: 26,
  },
  {
    id: "gemini",
    name: "Google Gemini",
    logoSrc: "/images/ai-tools/gemini.svg",
    heightPx: 30,
  },
  {
    id: "perplexity",
    name: "Perplexity",
    logoSrc: "/images/ai-tools/perplexity.svg",
    heightPx: 26,
  },
  {
    id: "cursor",
    name: "Cursor",
    logoSrc: "/images/ai-tools/cursor.svg",
    heightPx: 26,
  },
] as const;
