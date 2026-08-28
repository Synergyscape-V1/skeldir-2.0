import { runSecretScan } from '../secretScan';

const result = runSecretScan();
if (result.violations.length) {
  console.error(result.violations);
  process.exit(1);
}
console.log(`Secret scan: ${result.filesScanned} files, 0 violations`);
