export type PlatformRow = {
  platform: string;
  logoPath: string;
  budget: number;
  revenue: number;
  budgetStyle: "blue" | "blueWithRedHatch";
  revenueStyle: "blue" | "green" | "greenWithWhiteHatch";
  status: "overfunded" | "underfunded";
  delta: number;
  revenueLabelWhite?: boolean;
  annotation:
    | "default"
    | "metaDualOver"
    | "googleCurvedUnder"
    | "linkedinCurvedUnder"
    | "pinterestCurvedUnder"
    | "tiktokOverToRed";
};

export const platformRows: PlatformRow[] = [
  {
    platform: "Meta",
    logoPath: "/images/meta-ads-official.svg",
    budget: 45,
    revenue: 32,
    budgetStyle: "blueWithRedHatch",
    revenueStyle: "blue",
    status: "overfunded",
    delta: 13,
    annotation: "metaDualOver",
  },
  {
    platform: "Google Ads",
    logoPath: "/images/google-ads-icon.webp",
    budget: 30,
    revenue: 41,
    budgetStyle: "blue",
    revenueStyle: "green",
    status: "underfunded",
    delta: 11,
    annotation: "googleCurvedUnder",
  },
  {
    platform: "TikTok",
    logoPath: "/images/tiktok-icon.png",
    budget: 15,
    revenue: 12,
    budgetStyle: "blueWithRedHatch",
    revenueStyle: "blue",
    status: "overfunded",
    delta: 3,
    annotation: "tiktokOverToRed",
  },
  {
    platform: "LinkedIn Ads",
    logoPath: "/images/linkedin-ads-logo.svg",
    budget: 8,
    revenue: 11,
    budgetStyle: "blue",
    revenueStyle: "green",
    status: "underfunded",
    delta: 3,
    annotation: "linkedinCurvedUnder",
  },
  {
    platform: "Pinterest",
    logoPath: "/images/pinterest-ads-official.svg",
    budget: 8,
    revenue: 15,
    budgetStyle: "blue",
    revenueStyle: "green",
    status: "underfunded",
    delta: 7,
    annotation: "pinterestCurvedUnder",
  },
];

export type BottomBulletRow = {
  spendPhrase: string;
  misallocatePhrase: string;
};

/** Third-party citation under problem-statement callout — single source for measure + render */
export const PROBLEM_STATEMENT_CALLOUT_CITATION =
  "Forrester research indicates that 37% of wasted marketing spend stems from poor media data quality, linked to attribution failures.";

/** Spend → misallocation mapping; rendered with a visible arrow in ProblemStatementCandidate. */
export const bottomBulletRows: BottomBulletRow[] = [
  { spendPhrase: "At $200K annual spend", misallocatePhrase: "$70K-$100K misallocated" },
  { spendPhrase: "At $500K annual spend", misallocatePhrase: "$175K-$250K misallocated" },
  { spendPhrase: "At $1M+ annual spend", misallocatePhrase: "$350K-$500K+ misallocated" },
];
