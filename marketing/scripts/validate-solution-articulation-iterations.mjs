import { createHash } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const IMPLEMENTATIONS_ROOT = path.join(ROOT, "public", "implementations");
const OUTPUT_ROOT = path.join(ROOT, "orchestration", "problem-articulation", "comparisons");

const AGENTS = ["agent-a", "agent-b", "agent-c", "agent-d", "agent-e"];
const REQUIRED_FILES = [
  "index.html",
  "metadata.json",
  path.join("screenshots", "desktop-1440.png"),
  path.join("screenshots", "tablet-768.png"),
  path.join("screenshots", "mobile-375.png"),
];

async function exists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function sha256(filePath) {
  const data = await fs.readFile(filePath);
  return createHash("sha256").update(data).digest("hex");
}

async function fileSize(filePath) {
  const stat = await fs.stat(filePath);
  return stat.size;
}

async function analyzeAgent(agentId) {
  const basePath = path.join(IMPLEMENTATIONS_ROOT, agentId);
  const checks = [];
  let missingCount = 0;

  for (const rel of REQUIRED_FILES) {
    const fullPath = path.join(basePath, rel);
    const present = await exists(fullPath);
    if (!present) {
      missingCount += 1;
      checks.push({
        requiredPath: rel.replaceAll("\\", "/"),
        present: false,
      });
      continue;
    }

    checks.push({
      requiredPath: rel.replaceAll("\\", "/"),
      present: true,
      bytes: await fileSize(fullPath),
      sha256: await sha256(fullPath),
    });
  }

  return {
    agentId,
    basePath: path.relative(ROOT, basePath).replaceAll("\\", "/"),
    missingCount,
    complete: missingCount === 0,
    checks,
  };
}

async function ensureDir(dir) {
  await fs.mkdir(dir, { recursive: true });
}

async function main() {
  const startedAt = new Date().toISOString();
  if (!(await exists(IMPLEMENTATIONS_ROOT))) {
    console.warn(
      "SKIP: public/implementations/ is absent (removed from public export per D2-C). Run scripts/populate-solution-iterations.mjs locally if you need Storybook comparison mounts.",
    );
    process.exit(0);
  }
  const agents = await Promise.all(AGENTS.map((id) => analyzeAgent(id)));
  const completeCount = agents.filter((a) => a.complete).length;
  const incompleteCount = agents.length - completeCount;

  const report = {
    generatedAt: startedAt,
    root: path.relative(ROOT, IMPLEMENTATIONS_ROOT).replaceAll("\\", "/"),
    totals: {
      agents: agents.length,
      complete: completeCount,
      incomplete: incompleteCount,
      passed: incompleteCount === 0,
    },
    agents,
  };

  await ensureDir(OUTPUT_ROOT);
  const jsonPath = path.join(OUTPUT_ROOT, "iteration-validation-report.json");
  const mdPath = path.join(OUTPUT_ROOT, "iteration-validation-report.md");

  await fs.writeFile(jsonPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");

  const lines = [];
  lines.push("# Iteration Validation Report");
  lines.push("");
  lines.push(`Generated: ${startedAt}`);
  lines.push("");
  lines.push(`- Agents complete: ${completeCount}/${agents.length}`);
  lines.push(`- Overall pass: ${incompleteCount === 0 ? "YES" : "NO"}`);
  lines.push("");
  for (const agent of agents) {
    lines.push(`## ${agent.agentId}`);
    lines.push(`- Complete: ${agent.complete ? "YES" : "NO"}`);
    lines.push(`- Missing files: ${agent.missingCount}`);
    for (const check of agent.checks) {
      if (!check.present) {
        lines.push(`- [MISSING] ${check.requiredPath}`);
        continue;
      }
      lines.push(`- [OK] ${check.requiredPath} (${check.bytes} bytes) sha256=${check.sha256}`);
    }
    lines.push("");
  }

  await fs.writeFile(mdPath, `${lines.join("\n")}\n`, "utf8");

  if (incompleteCount > 0) {
    console.error(
      `Validation failed: ${incompleteCount} agent(s) incomplete. See ${path.relative(ROOT, jsonPath)}`
    );
    process.exit(1);
  }

  console.log(`Validation passed. Report: ${path.relative(ROOT, jsonPath)}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
