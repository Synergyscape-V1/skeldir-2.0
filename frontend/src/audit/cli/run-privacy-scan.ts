import { runPrivacyScan } from '../privacyScan';

const result = runPrivacyScan();

if (result.violations.length > 0) {
  console.error('Privacy/PII scan violations:');
  for (const v of result.violations) {
    console.error(`  [${v.type}] ${v.file}: ${v.value}`);
  }
  process.exit(1);
}

console.log(`Privacy scan: ${result.filesScanned} files, 0 violations`);
process.exit(0);
