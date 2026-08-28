import { runLevel2NegativeScopeScan } from '../level2NegativeScopeScan';

const result = runLevel2NegativeScopeScan();
console.log(JSON.stringify(result, null, 2));
if (result.violations.length > 0) process.exit(1);
