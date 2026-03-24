import fs from "node:fs";
import path from "node:path";

const root = path.join(process.cwd(), "src", "channel-comparison");
const files = [];

function walk(dir) {
  for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
    const next = path.join(dir, item.name);
    if (item.isDirectory()) walk(next);
    else if (item.isFile() && /\.(ts|tsx)$/.test(item.name)) files.push(next);
  }
}

walk(root);

const colorPattern = /#[0-9a-fA-F]{3,8}\b/;
const violations = [];

for (const file of files) {
  const text = fs.readFileSync(file, "utf8");
  const lines = text.split(/\r?\n/);
  lines.forEach((line, index) => {
    if (colorPattern.test(line)) {
      violations.push(`${path.relative(process.cwd(), file)}:${index + 1}`);
    }
  });
}

if (violations.length > 0) {
  console.error("Hardcoded color values found in channel-comparison TypeScript files:");
  for (const violation of violations) console.error(` - ${violation}`);
  process.exit(1);
}

console.log("Channel Comparison token check passed.");
