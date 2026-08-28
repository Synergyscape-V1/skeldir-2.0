import { join } from 'node:path';
import { runLevel5NegativeScopeScan } from '../level5NegativeScopeScan';

const ROOT = join(import.meta.dirname, '..', '..', '..');

async function main() {
  const result = runLevel5NegativeScopeScan();
  if (result.violations.length > 0) {
    console.error('Level 5 scope violations:', result.violations);
    process.exit(1);
  }
  console.log(`Level 5 scope scan passed (${result.filesScanned} files)`);
}

void main();
