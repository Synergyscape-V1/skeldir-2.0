import fs from "node:fs";
import path from "node:path";

const storyFiles = [
  "src/stories/agent-a-channel-comparison.stories.tsx",
  "src/stories/agent-b-channel-comparison.stories.tsx",
  "src/stories/agent-c-channel-comparison.stories.tsx",
  "src/stories/agent-d-channel-comparison.stories.tsx",
  "src/stories/agent-e-channel-comparison.stories.tsx",
  "src/stories/compare-channel-comparison-overview.stories.tsx",
  "src/stories/sharedChannelComparisonStoryFactory.tsx",
];

for (const relativePath of storyFiles) {
  const fullPath = path.join(process.cwd(), relativePath);
  if (!fs.existsSync(fullPath)) {
    console.error("Missing Channel Comparison story:", relativePath);
    process.exit(1);
  }
}

console.log("Channel Comparison story presence check passed.");
