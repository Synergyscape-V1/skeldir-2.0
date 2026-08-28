import { runLevel7NegativeScopeScanCli } from '../level7NegativeScopeScan';

const scan = runLevel7NegativeScopeScanCli();
console.log(`Level 7 scope scan: ${scan.filesScanned} files, ${scan.violations.length} violations`);
if (scan.violations.length > 0) {
  for (const v of scan.violations) {
    console.error(`${v.file}: [${v.type}] ${v.value}`);
  }
  process.exit(1);
}
process.exit(0);
