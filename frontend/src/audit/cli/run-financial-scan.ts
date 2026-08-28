import { runFinancialScan } from '../financialScan';

const result = runFinancialScan();
console.log(JSON.stringify(result, null, 2));
process.exit(result.violations.length ? 1 : 0);
