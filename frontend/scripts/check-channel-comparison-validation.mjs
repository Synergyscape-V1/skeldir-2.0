import fs from "node:fs";
import path from "node:path";

const manifestPath = path.join(process.cwd(), "src", "channel-comparison", "core", "manifests.ts");
if (!fs.existsSync(manifestPath)) {
  console.error("Missing manifest file:", manifestPath);
  process.exit(1);
}

const text = fs.readFileSync(manifestPath, "utf8");
const requiredAgentIds = ["A", "B", "C", "D", "E"];
const requiredGateKeys = [
  "spatial",
  "typography",
  "logos",
  "color",
  "confidence",
  "deltaLabels",
  "states",
  "accessibility",
  "responsiveness",
  "dataContract",
];

for (const agentId of requiredAgentIds) {
  if (!text.includes(`agentId: \"${agentId}\"`)) {
    console.error(`Missing agent manifest for ${agentId}`);
    process.exit(1);
  }
}

for (const gateKey of requiredGateKeys) {
  if (!text.includes(`key: \"${gateKey}\"`)) {
    console.error(`Missing required gate key: ${gateKey}`);
    process.exit(1);
  }
}

if (text.includes("pass: false")) {
  console.error("Manifest contains failed validation gates.");
  process.exit(1);
}

console.log("Channel Comparison validation manifest check passed.");
