import { runLevel6NegativeScopeScan } from '../level6NegativeScopeScan';

const result = runLevel6NegativeScopeScan();
if (result.violations.length > 0) {
  console.error('Level 6 negative scope violations:');
  for (const v of result.violations) {
    console.error(`  [${v.type}] ${v.file}: ${v.value}`);
  }
  process.exit(1);
}
console.log(`Level 6 scope scan passed (${result.filesScanned} files)`);
