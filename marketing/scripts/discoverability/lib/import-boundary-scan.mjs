import fs from 'node:fs';
import path from 'node:path';

const AUTH_IMPORT_RE = /from\s+['"]@\/components\/auth|from\s+['"].*\/auth\//;
const BACKEND_API_RE = /from\s+['"]@\/lib\/api|from\s+['"].*backend|fetch\s*\(\s*['"]\/api\//;
const TENANT_RE = /tenant|multi-tenant|tenantId|tenant_id/i;
const TOKEN_RE = /accessToken|refreshToken|tokenHandler|Bearer\s+/;
const DASHBOARD_PROVIDER_RE = /from\s+['"]@\/providers\/dashboard|DashboardProvider|useDashboardAuth/;

/**
 * Scan a source file for import/boundary markers.
 * @param {string} filePath
 */
export function scanFileBoundaries(filePath) {
  if (!fs.existsSync(filePath)) {
    return {
      imports_auth_code: false,
      imports_backend_api_client: false,
      imports_tenant_logic: false,
      imports_token_handling: false,
      imports_dashboard_provider: false,
      markers: [],
    };
  }

  const content = fs.readFileSync(filePath, 'utf8');
  const markers = [];

  const flags = {
    imports_auth_code: AUTH_IMPORT_RE.test(content),
    imports_backend_api_client: BACKEND_API_RE.test(content),
    imports_tenant_logic: TENANT_RE.test(content) && /import|from/.test(content),
    imports_token_handling: TOKEN_RE.test(content),
    imports_dashboard_provider: DASHBOARD_PROVIDER_RE.test(content),
  };

  if (flags.imports_auth_code) markers.push('auth_import');
  if (flags.imports_backend_api_client) markers.push('backend_api_import');
  if (flags.imports_tenant_logic) markers.push('tenant_logic');
  if (flags.imports_token_handling) markers.push('token_handling');
  if (flags.imports_dashboard_provider) markers.push('dashboard_provider');

  return { ...flags, markers };
}

/**
 * Derive isolation status from boundary flags and physical surface.
 * @param {object} flags
 * @param {string} physicalSurface
 */
export function deriveIsolationStatus(flags, physicalSurface) {
  const breach =
    flags.imports_backend_api_client ||
    flags.imports_token_handling ||
    flags.imports_dashboard_provider;

  if (breach && physicalSurface === 'marketing_static') {
    return 'breach';
  }

  if (
    physicalSurface === 'marketing_static' &&
    (flags.imports_auth_code || flags.imports_tenant_logic)
  ) {
    return 'risk';
  }

  if (physicalSurface === 'auth_static' || physicalSurface === 'transactional_static') {
    if (flags.imports_backend_api_client || flags.imports_token_handling) {
      return 'risk';
    }
    return flags.imports_auth_code ? 'risk' : 'inconclusive';
  }

  if (physicalSurface === 'marketing_static') {
    return 'inconclusive';
  }

  return 'safe';
}

/**
 * Scan all marketing page sources under src/app.
 * @param {string} marketingRoot
 */
export function scanMarketingImportBoundaries(marketingRoot) {
  const srcApp = path.join(marketingRoot, 'src', 'app');
  const results = [];

  function walk(dir) {
    if (!fs.existsSync(dir)) return;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (/^page\.(tsx|ts|jsx|js)$/.test(entry.name)) {
        const scan = scanFileBoundaries(full);
        results.push({
          file: path.relative(marketingRoot, full).replace(/\\/g, '/'),
          ...scan,
        });
      }
    }
  }

  walk(srcApp);
  return results;
}
