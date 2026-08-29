import {
  assertLevel4AgentAccessAbsent,
  assertLevel4RoutesExist,
  runLevel4SabotageProbes,
} from '../../src/audit/level4NegativeScopeScan.ts';

console.log('assertLevel4AgentAccessAbsent', JSON.stringify(assertLevel4AgentAccessAbsent()));
console.log('assertLevel4RoutesExist', JSON.stringify(assertLevel4RoutesExist()));

const sabotageSample =
  'path="/audit" path="/claims" All systems operational fetch( in modal path="agents" agent-access';
console.log('sabotage', JSON.stringify(runLevel4SabotageProbes(sabotageSample)));
