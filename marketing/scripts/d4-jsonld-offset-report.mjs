import fs from "node:fs";
import path from "node:path";

const re = /<script[^>]*type=["']application\/ld\+json["'][^>]*>/gi;
const files = [
  "out/index.html",
  "out/product.html",
  "out/pricing.html",
  "out/agencies.html",
  "out/resources.html",
  "out/resources/why-your-attribution-numbers-never-match.html",
];

for (const rel of files) {
  const p = path.join(process.cwd(), rel);
  if (!fs.existsSync(p)) {
    console.log(rel, "MISSING");
    continue;
  }
  const s = fs.readFileSync(p, "utf8");
  const headEnd = s.search(/<\/head>/i);
  console.log(`\n## ${rel} (</head> @ ${headEnd})`);
  let m;
  re.lastIndex = 0;
  let n = 0;
  while ((m = re.exec(s)) !== null) {
    n++;
    console.log(`  block ${n}: byte ${m.index}, inHead=${m.index < headEnd}`);
  }
}
