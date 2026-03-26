import type {
  components as BudgetComponents,
  operations as BudgetOperations,
  paths as BudgetPaths,
} from "./types/api/llm-budget";
import type {
  components as InvestigationComponents,
  operations as InvestigationOperations,
  paths as InvestigationPaths,
} from "./types/api/llm-investigations";
import type {
  BudgetSeparatedResult,
  InvestigationSeparatedResult,
} from "./api/contracts";

type Assert<T extends true> = T;
type HasPath<TPaths, TPath extends string> = TPath extends keyof TPaths ? true : false;
type HasOperation<TOps, TOperationId extends string> = TOperationId extends keyof TOps
  ? true
  : false;

type _investigationsCreatePath = Assert<
  HasPath<InvestigationPaths, "/api/investigations">
>;
type _investigationsStatusPath = Assert<
  HasPath<InvestigationPaths, "/api/investigations/{investigation_id}/status">
>;
type _investigationsResultPath = Assert<
  HasPath<InvestigationPaths, "/api/investigations/{investigation_id}">
>;
type _investigationsCreateOperation = Assert<
  HasOperation<InvestigationOperations, "createInvestigation">
>;
type _investigationsStatusOperation = Assert<
  HasOperation<InvestigationOperations, "getInvestigationStatus">
>;
type _investigationsResultOperation = Assert<
  HasOperation<InvestigationOperations, "getInvestigationResult">
>;

type _budgetCreatePath = Assert<HasPath<BudgetPaths, "/api/budget/optimize">>;
type _budgetStatusPath = Assert<
  HasPath<BudgetPaths, "/api/budget/recommendations/{job_id}/status">
>;
type _budgetResultPath = Assert<
  HasPath<BudgetPaths, "/api/budget/recommendations/{job_id}">
>;
type _budgetCreateOperation = Assert<
  HasOperation<BudgetOperations, "createBudgetOptimization">
>;
type _budgetStatusOperation = Assert<
  HasOperation<BudgetOperations, "getBudgetRecommendationStatus">
>;
type _budgetResultOperation = Assert<
  HasOperation<BudgetOperations, "getBudgetRecommendation">
>;

type InvestigationResultPayload =
  InvestigationComponents["schemas"]["InvestigationResultPayload"];
type BudgetResultPayload = BudgetComponents["schemas"]["BudgetResultPayload"];

const investigationsSeparationShape: InvestigationSeparatedResult = {
  authority: {
    deterministic_findings: [],
  },
  synthesis: {
    non_authoritative_summary: "non-authoritative synthesis",
    generated_at: "2026-01-01T00:00:00Z",
  },
};

const budgetSeparationShape: BudgetSeparatedResult = {
  authority: {
    deterministic_recommendation: {
      optimization_goal: "maximize_roas",
      allocations: [],
      evidence: [],
      generated_at: "2026-01-01T00:00:00Z",
    },
  },
  synthesis: {
    non_authoritative_summary: "non-authoritative synthesis",
    generated_at: "2026-01-01T00:00:00Z",
  },
};

declare const investigationPayload: InvestigationResultPayload;
declare const budgetPayload: BudgetResultPayload;

const investigationAuthorityOnly = investigationPayload.deterministic_findings;
const investigationSynthesisOnly = investigationPayload.llm_synthesis;
const budgetAuthorityOnly = budgetPayload.deterministic_recommendation;
const budgetSynthesisOnly = budgetPayload.llm_synthesis;

void investigationsSeparationShape;
void budgetSeparationShape;
void investigationAuthorityOnly;
void investigationSynthesisOnly;
void budgetAuthorityOnly;
void budgetSynthesisOnly;
