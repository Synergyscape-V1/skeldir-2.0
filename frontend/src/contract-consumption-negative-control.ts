import type { operations as InvestigationOperations } from "./types/api/llm-investigations";
import type { paths as BudgetPaths } from "./types/api/llm-budget";
import type { InvestigationSeparatedResult } from "./api/contracts";

type StaleOperationNameShouldFail = InvestigationOperations["startInvestigation"];
type StaleBudgetPathShouldFail = BudgetPaths["/api/budget/optimization"];

declare const separated: InvestigationSeparatedResult;
const flattenedShouldFail: {
  deterministic_findings: InvestigationSeparatedResult["authority"]["deterministic_findings"];
  non_authoritative_summary: string;
} = separated;

void flattenedShouldFail;
void (null as unknown as StaleOperationNameShouldFail);
void (null as unknown as StaleBudgetPathShouldFail);
