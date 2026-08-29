import { runTokenAudit } from '../tokenAudit';

const result = runTokenAudit();
console.log(JSON.stringify(result, null, 2));
process.exit(result.violations.length ? 1 : 0);
