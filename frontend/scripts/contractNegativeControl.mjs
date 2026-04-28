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

const combinedOutput = `${result.stdout ?? ""}\n${result.stderr ?? ""}`;
const diagnosticLines = combinedOutput
  .split(/\r?\n/)
  .map((line) => line.trim())
  .filter((line) => line.includes("error TS"));
if (diagnosticLines.length === 0) {
  process.stderr.write(
    "Negative control failed without TypeScript diagnostics; unable to prove typed-boundary compile failure.\n",
  );
  process.exit(1);
}

const unexpectedDiagnostics = diagnosticLines.filter(
  (line) => !line.includes("src/contract-consumption-negative-control.ts("),
);
if (unexpectedDiagnostics.length > 0) {
  process.stderr.write(
    "Unexpected TypeScript diagnostics outside the controlled negative-control surface:\n",
  );
  for (const line of unexpectedDiagnostics) {
    process.stderr.write(`${line}\n`);
  }
  process.exit(1);
}

const requiredDiagnosticPatterns = [
  /contract-consumption-negative-control\.ts\(5,\d+\): error TS2339: Property 'startInvestigation'/,
  /contract-consumption-negative-control\.ts\(6,\d+\): error TS2339: Property '\/api\/budget\/optimization'/,
  /contract-consumption-negative-control\.ts\(9,\d+\): error TS2739:/,
];
for (const pattern of requiredDiagnosticPatterns) {
  if (!pattern.test(combinedOutput)) {
    process.stderr.write(
      `Negative control compile failure missing expected diagnostic pattern: ${pattern}\n`,
    );
    process.exit(1);
  }
}

process.stdout.write("Negative control produced expected compile failure.\n");
