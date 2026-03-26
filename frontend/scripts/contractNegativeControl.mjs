import { spawnSync } from "node:child_process";

const runner = process.platform === "win32" ? "npx.cmd" : "npx";
const result = spawnSync(
  runner,
  ["tsc", "-p", "tsconfig.contract-gate.negative.json", "--noEmit"],
  {
    encoding: "utf-8",
    stdio: "pipe",
  },
);

if (result.stdout) {
  process.stdout.write(result.stdout);
}
if (result.stderr) {
  process.stderr.write(result.stderr);
}

if (result.status === 0) {
  process.stderr.write(
    "Negative control unexpectedly passed: stale operation/path or flattening regression not detected.\n",
  );
  process.exit(1);
}

process.stdout.write("Negative control produced expected compile failure.\n");
