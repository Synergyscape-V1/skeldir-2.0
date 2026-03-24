import fs from "node:fs";
import path from "node:path";

const storyFiles = [
  "src/stories/agent-a-data-health.stories.tsx",
  "src/stories/agent-b-data-health.stories.tsx",
  "src/stories/agent-c-data-health.stories.tsx",
  "src/stories/agent-d-data-health.stories.tsx",
  "src/stories/agent-e-data-health.stories.tsx",
  "src/stories/compare-data-health-overview.stories.tsx",
];

for (const relativePath of storyFiles) {
  const fullPath = path.join(process.cwd(), relativePath);
  if (!fs.existsSync(fullPath)) {
    console.error("Missing Data Health story:", relativePath);
    process.exit(1);
  }
}

console.log("Data Health story presence check passed.");
