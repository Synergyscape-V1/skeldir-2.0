import type { paths as AuthPaths } from "./types/api/auth";
import type { paths as AttributionPaths } from "./types/api/attribution";
import type { paths as HealthPaths } from "./types/api/health";
import type { paths as ReconciliationPaths } from "./types/api/reconciliation";
import type { paths as ExportPaths } from "./types/api/export";

type Assert<T extends true> = T;
type HasPath<TPaths, TPath extends string> = TPath extends keyof TPaths ? true : false;
type HasMethod<TPathItem, TMethod extends string> = TMethod extends keyof TPathItem ? true : false;
type HasResponse<TOperation extends { responses: unknown }, TCode extends number> =
  TCode extends keyof TOperation["responses"] ? true : false;

type _authPath = Assert<HasPath<AuthPaths, "/api/auth/login">>;
type _authMethod = Assert<HasMethod<AuthPaths["/api/auth/login"], "post">>;
type _authResponse200 = Assert<HasResponse<AuthPaths["/api/auth/login"]["post"], 200>>;

type _realtimePath = Assert<HasPath<AttributionPaths, "/api/attribution/revenue/realtime">>;
type _realtimeMethod = Assert<HasMethod<AttributionPaths["/api/attribution/revenue/realtime"], "get">>;
type _realtimeResponse200 = Assert<
  HasResponse<AttributionPaths["/api/attribution/revenue/realtime"]["get"], 200>
>;

type _healthPath = Assert<HasPath<HealthPaths, "/api/health">>;
type _healthMethod = Assert<HasMethod<HealthPaths["/api/health"], "get">>;
type _healthResponse200 = Assert<HasResponse<HealthPaths["/api/health"]["get"], 200>>;

type _reconciliationPath = Assert<HasPath<ReconciliationPaths, "/api/reconciliation/status">>;
type _reconciliationMethod = Assert<
  HasMethod<ReconciliationPaths["/api/reconciliation/status"], "get">
>;
type _reconciliationResponse200 = Assert<
  HasResponse<ReconciliationPaths["/api/reconciliation/status"]["get"], 200>
>;

type _exportPath = Assert<HasPath<ExportPaths, "/api/export/csv">>;
type _exportMethod = Assert<HasMethod<ExportPaths["/api/export/csv"], "get">>;
type _exportResponse200 = Assert<HasResponse<ExportPaths["/api/export/csv"]["get"], 200>>;

type AuthLogin200 =
  AuthPaths["/api/auth/login"]["post"]["responses"][200]["content"]["application/json"];
type RealtimeRevenue200 =
  AttributionPaths["/api/attribution/revenue/realtime"]["get"]["responses"][200]["content"]["application/json"];
type Health200 = HealthPaths["/api/health"]["get"]["responses"][200]["content"]["application/json"];

const authResponseShape: AuthLogin200 | null = null;
const revenueResponseShape: RealtimeRevenue200 | null = null;
const healthResponseShape: Health200 | null = null;

void authResponseShape;
void revenueResponseShape;
void healthResponseShape;
