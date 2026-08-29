import { runLevel3NegativeScopeScan } from '../level3NegativeScopeScan';

const result = runLevel3NegativeScopeScan();

if (result.violations.length > 0) {
  console.error('Level 3 negative scope violations:');
  for (const v of result.violations) {
    console.error(`  [${v.type}] ${v.file}: ${v.value}`);
  }
  process.exit(1);
}

console.log(`Level 3 scope scan: ${result.filesScanned} files, 0 violations`);
process.exit(0);
