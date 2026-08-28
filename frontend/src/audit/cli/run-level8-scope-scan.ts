import { runLevel8NegativeScopeScanCli } from '../level8NegativeScopeScan';

const scan = runLevel8NegativeScopeScanCli();
console.log(`Level 8 scope scan: ${scan.filesScanned} files, ${scan.violations.length} violations`);
if (scan.violations.length > 0) {
  for (const v of scan.violations) {
    console.error(`${v.file}: [${v.type}] ${v.value}`);
  }
  process.exit(1);
}
process.exit(0);
