import { runLevel4NegativeScopeScan } from '../level4NegativeScopeScan';
import { runSecretScan } from '../secretScan';

const scope = runLevel4NegativeScopeScan();
const secrets = runSecretScan();

if (scope.violations.length) {
  console.error('Level 4 scope violations:', scope.violations);
  process.exit(1);
}

if (secrets.violations.length) {
  console.error('Secret scan violations:', secrets.violations);
  process.exit(1);
}

console.log(
  `Level 4 scope scan: ${scope.filesScanned} files, 0 violations. Secret scan: ${secrets.filesScanned} files, 0 violations.`,
);
