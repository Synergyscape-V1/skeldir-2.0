import type { MetadataRoute } from "next";
import botPolicy from "../../discoverability.bot-policy.json";
import { robotsSitemapUrl } from "@/lib/crawlUrls";

export const dynamic = "error";

type BotEntry = (typeof botPolicy.bots)[number];

/**
 * Root robots.txt for static export — compiled from `discoverability.bot-policy.json` (Phase D3).
 * Do not hand-edit stanzas here; update the manifest and `BOT_POLICY.md` together.
 */
export default function robots(): MetadataRoute.Robots {
  const bots = botPolicy.bots as BotEntry[];
  const rules: MetadataRoute.Robots["rules"] = [];

  const disallowBots = bots.filter((b) => b.robots_required && b.robots_rule === "disallow_root");
  const allowBots = bots.filter((b) => b.robots_required && b.robots_rule === "allow_root");

  for (const b of disallowBots) {
    const disallow = b.paths_disallowed?.length ? b.paths_disallowed : ["/"];
    rules.push({ userAgent: b.user_agent_token, disallow });
  }
  for (const b of allowBots) {
    const allow = b.paths_allowed?.length ? b.paths_allowed : ["/"];
    rules.push({ userAgent: b.user_agent_token, allow });
  }

  rules.push({ userAgent: "*", allow: "/" });

  return {
    rules,
    host: botPolicy.site_host_robots,
    sitemap: robotsSitemapUrl(),
  };
}
