export const PLATFORM_REGISTRY = [
  {
    id: "google_ads",
    name: "Google Ads",
    description: "Track campaigns, keywords, and ad performance from Google Ads",
    iconUrl: "/assets/platform-icons/google-ads.svg",
  },
  {
    id: "meta_ads",
    name: "Meta Ads",
    description: "Monitor campaigns and ad sets from Facebook and Instagram",
    iconUrl: "/assets/platform-icons/meta-ads.svg",
  },
  {
    id: "linkedin_ads",
    name: "LinkedIn Ads",
    description: "Monitor B2B campaigns and lead generation from LinkedIn",
    iconUrl: "/assets/platform-icons/linkedin-ads.svg",
  },
  {
    id: "tiktok_ads",
    name: "TikTok Ads",
    description: "Track TikTok campaign performance and conversions",
    iconUrl: "/assets/platform-icons/tiktok-ads.svg",
  },
  {
    id: "hubspot",
    name: "HubSpot",
    description: "Sync contacts, deals, and marketing activity from HubSpot CRM",
    iconUrl: "/assets/platform-icons/hubspot.svg",
  },
  {
    id: "salesforce",
    name: "Salesforce",
    description: "Import opportunities and lead data from Salesforce CRM",
    iconUrl: "/assets/platform-icons/salesforce.svg",
  },
] as const;

export const STATUS_CONFIG = {
  connected: {
    label: "Connected",
    color: "var(--pi-success, #10B981)",
    bgColor: "var(--pi-success-bg, #D1FAE5)",
  },
  disconnected: {
    label: "Not Connected",
    color: "var(--pi-muted, #6C757D)",
    bgColor: "var(--pi-muted-bg, #F8F9FA)",
  },
  syncing: {
    label: "Syncing\u2026",
    color: "var(--pi-info, #3B82F6)",
    bgColor: "var(--pi-info-bg, #DBEAFE)",
  },
  error: {
    label: "Connection Error",
    color: "var(--pi-error, #EF4444)",
    bgColor: "var(--pi-error-bg, #FEE2E2)",
  },
} as const;
