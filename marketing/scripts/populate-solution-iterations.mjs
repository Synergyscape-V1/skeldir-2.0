import { promises as fs } from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const DEST_ROOT = path.join(ROOT, "public", "implementations");
const AGENTS = ["agent-a", "agent-b", "agent-c", "agent-d", "agent-e"];
const REQUIRED = [
  "index.html",
  "metadata.json",
  path.join("screenshots", "desktop-1440.png"),
  path.join("screenshots", "tablet-768.png"),
  path.join("screenshots", "mobile-375.png"),
];

function normalize(p) {
  return p.replaceAll("\\", "/");
}

async function exists(p) {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

async function ensureDir(p) {
  await fs.mkdir(p, { recursive: true });
}

async function clearAgentDest(agentId) {
  const dir = path.join(DEST_ROOT, agentId);
  if (await exists(dir)) {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.name === ".gitkeep") continue;
      await fs.rm(path.join(dir, entry.name), { recursive: true, force: true });
    }
  }
  await ensureDir(path.join(dir, "screenshots"));
}

async function copyRequired(agentId, sourceRoot) {
  const sourceAgent = path.join(sourceRoot, agentId);
  const destAgent = path.join(DEST_ROOT, agentId);
  const missing = [];

  await clearAgentDest(agentId);

  for (const rel of REQUIRED) {
    const src = path.join(sourceAgent, rel);
    const dst = path.join(destAgent, rel);
    if (!(await exists(src))) {
      missing.push(normalize(path.join(agentId, rel)));
      continue;
    }
    await ensureDir(path.dirname(dst));
    await fs.copyFile(src, dst);
  }

  return { agentId, missing };
}

async function main() {
  const sourceArg = process.argv[2];
  if (!sourceArg) {
    console.error("Usage: npm run populate:solution-iterations -- <source-root>");
    console.error("Expected source layout:");
    console.error("  <source-root>/agent-a/index.html");
    console.error("  <source-root>/agent-a/metadata.json");
    console.error("  <source-root>/agent-a/screenshots/desktop-1440.png");
    console.error("  <source-root>/agent-a/screenshots/tablet-768.png");
    console.error("  <source-root>/agent-a/screenshots/mobile-375.png");
    process.exit(1);
  }

  const sourceRoot = path.resolve(ROOT, sourceArg);
  if (!(await exists(sourceRoot))) {
    console.error(`Source root not found: ${sourceRoot}`);
    process.exit(1);
  }

  const results = [];
  for (const agent of AGENTS) {
    results.push(await copyRequired(agent, sourceRoot));
  }

  const missing = results.flatMap((r) => r.missing);
  if (missing.length > 0) {
    console.error("Population incomplete. Missing required files:");
    for (const m of missing) console.error(`- ${m}`);
    process.exit(1);
  }

  console.log("Population complete. Mounted 5/5 agent iterations to public/implementations.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
