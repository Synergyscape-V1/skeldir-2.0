import fs from 'node:fs';
import path from 'node:path';

export const IMPLEMENTATION_FIELDS = [
  'sitemap_required',
  'sitemap_implemented',
  'canonical_required',
  'canonical_implemented',
  'jsonld_required',
  'jsonld_implemented',
  'noindex_required',
  'noindex_implemented',
];

export const ISOLATION_FIELDS = [
  'imports_auth_code',
  'imports_backend_api_client',
  'imports_tenant_logic',
  'imports_token_handling',
  'imports_dashboard_provider',
  'shared_root_layout',
  'shared_client_chunks_observed',
  'isolation_status',
];

export const ISOLATION_STATUS_ENUM = ['safe', 'risk', 'breach', 'inconclusive'];

/** Legacy ambiguous fields that must not remain as sole guarantees. */
export const DEPRECATED_AMBIGUOUS_FIELDS = ['sitemap', 'noindex', 'jsonld', 'canonical'];

/**
 * @param {string} marketingRoot
 */
export function loadRegistry(marketingRoot) {
  const registryPath = path.join(marketingRoot, 'discoverability.routes.json');
  const raw = fs.readFileSync(registryPath, 'utf8');
  const data = JSON.parse(raw);
  if (!Array.isArray(data.routes)) {
    throw new Error('discoverability.routes.json must contain a routes array');
  }
  return { data, registryPath };
}

/**
 * @param {object} route
 * @returns {string[]}
 */
export function validateRouteFields(route) {
  const errors = [];

  for (const field of DEPRECATED_AMBIGUOUS_FIELDS) {
    if (Object.prototype.hasOwnProperty.call(route, field)) {
      errors.push(`Route ${route.id}: deprecated ambiguous field "${field}" — use *_required/*_implemented`);
    }
  }

  for (const field of IMPLEMENTATION_FIELDS) {
    if (route[field] === undefined || route[field] === null) {
      if (route.route_type === 'missing_required' && field.endsWith('_implemented')) {
        continue;
      }
      if (route.route_type === 'runtime_api_external') continue;
      errors.push(`Route ${route.id}: missing required field "${field}"`);
    }
  }

  if (route.indexability_class === 'indexable' && route.noindex_required !== false) {
    errors.push(`Route ${route.id}: indexable routes must set noindex_required=false`);
  }

  if (route.indexability_class === 'indexable_candidate') {
    if (route.sitemap_required === true && route.status !== 'active_defective_until_static_body_verified') {
      errors.push(`Route ${route.id}: indexable_candidate must not have sitemap_required=true before verification`);
    }
  }

  if (route.indexability_class === 'nonindex' && route.noindex_required !== true) {
    errors.push(`Route ${route.id}: nonindex routes must set noindex_required=true`);
  }

  if (
    (route.physical_surface === 'auth_static' ||
      (route.physical_surface === 'transactional_static' && route.indexability_class !== 'indexable_candidate')) &&
    route.noindex_required !== true
  ) {
    errors.push(`Route ${route.id}: auth/transactional routes must set noindex_required=true`);
  }

  if (route.physical_surface === 'marketing_static' || route.physical_surface === 'auth_static' || route.physical_surface === 'transactional_static') {
    for (const field of ISOLATION_FIELDS) {
      if (route[field] === undefined || route[field] === null || route[field] === '') {
        errors.push(`Route ${route.id}: missing isolation field "${field}"`);
      }
    }
    if (route.isolation_status && !ISOLATION_STATUS_ENUM.includes(route.isolation_status)) {
      errors.push(`Route ${route.id}: invalid isolation_status "${route.isolation_status}"`);
    }
  }

  if (route.route_type === 'article' && !route.generated_from) {
    errors.push(`Route ${route.id}: article instance missing generated_from`);
  }

  if (route.route_type === 'article' && !route.content_id) {
    errors.push(`Route ${route.id}: article instance missing content_id`);
  }

  if (route.route_type === 'api_docs' && route.runtime_api !== false) {
    errors.push(`Route ${route.id}: api_docs must set runtime_api=false`);
  }

  if (route.route_type === 'api_docs' && route.static_export_compatible !== true) {
    errors.push(`Route ${route.id}: api_docs must set static_export_compatible=true`);
  }

  if (route.status === 'active' && route.indexability_class === 'indexable_candidate') {
    errors.push(`Route ${route.id}: indexable_candidate cannot have status=active`);
  }

  if (route.logical_route === '/book-demo') {
    if (route.indexability_class === 'indexable' && route.status === 'active') {
      errors.push(
        `Route ${route.id}: /book-demo must not be clean indexable — use indexable_candidate + active_defective_until_static_body_verified`
      );
    }
    if (route.sitemap_required === true && route.indexability_class !== 'indexable') {
      errors.push(`Route ${route.id}: /book-demo must not be sitemap_required=true before D1/D2 verification`);
    }
  }

  return errors;
}

/**
 * @param {object} registry
 * @returns {string[]}
 */
export function validateRegistryStructure(registry) {
  const errors = [];
  if (!registry.route_truth_hierarchy || registry.route_truth_hierarchy.length < 4) {
    errors.push('Registry missing route_truth_hierarchy with at least 4 levels');
  }
  if (registry.resolver_authority !== 'advisory_only') {
    errors.push('Registry must set resolver_authority=advisory_only');
  }
  if (!registry.infrastructure_surfaces?.some((s) => s.id === 'infra-trust-api-runtime')) {
    errors.push('Registry missing infra-trust-api-runtime infrastructure surface');
  }
  if (!registry.physical_surface_governance?.physical_split_required_during_d0) {
    errors.push('Registry missing physical_surface_governance.physical_split_required_during_d0');
  }
  return errors;
}

/**
 * @param {string} marketingRoot
 */
export function parseArticleSlugs(marketingRoot) {
  const file = path.join(marketingRoot, 'src', 'data', 'articlesData.ts');
  const content = fs.readFileSync(file, 'utf8');
  const slugs = [];
  const re = /slug:\s*['"]([^'"]+)['"]/g;
  let m;
  while ((m = re.exec(content)) !== null) {
    slugs.push(m[1]);
  }
  return slugs;
}

/**
 * @param {object} registry
 * @param {string[]} contentSlugs
 * @param {string[]} outArticleRoutes
 * @returns {{ errors: string[], warnings: string[] }}
 */
export function validateArticleInstanceGovernance(registry, contentSlugs, outArticleRoutes) {
  const errors = [];
  const warnings = [];
  const routes = registry.routes || [];

  const generatedRoutes = routes.filter((r) => r.route_type === 'article');
  const registrySlugs = new Set(generatedRoutes.map((r) => r.content_id));
  const contentSet = new Set(contentSlugs);
  const outSet = new Set(outArticleRoutes.map((r) => r.replace(/^\/resources\//, '')));

  for (const slug of contentSlugs) {
    if (!registrySlugs.has(slug)) {
      errors.push(
        `UNCLASSIFIED_NEW_CONTENT: article slug "${slug}" exists in articlesData.ts but has no registry generated instance — add route-article-generated-${slug}`
      );
    }
  }

  for (const route of generatedRoutes) {
    if (!contentSet.has(route.content_id)) {
      errors.push(
        `STALE_REGISTRY_ENTRY: registry article "${route.content_id}" no longer exists in articlesData.ts — remove or mark deprecated with redirect classification`
      );
    }
    if (!outSet.has(route.content_id)) {
      warnings.push(
        `BUILD_DRIFT: article "${route.content_id}" in registry/content but missing from out/resources/*.html (run npm run build)`
      );
    }
  }

  /** Top-level `out/resources/*.html` names that are not articlesData slugs (D6 evidence hub, etc.). */
  const RESERVED_RESOURCE_HTML_SLUGS = new Set(['evidence']);

  for (const slug of outSet) {
    if (RESERVED_RESOURCE_HTML_SLUGS.has(slug)) {
      continue;
    }
    if (!contentSet.has(slug)) {
      errors.push(
        `UNCLASSIFIED_BUILD_ARTIFACT: out/resources/${slug}.html exists but slug not in articlesData.ts — classify or remove`
      );
    }
  }

  const pattern = routes.find((r) => r.route_type === 'article_pattern');
  if (!pattern) {
    errors.push('Missing article_pattern route entry for /resources/[slug]');
  }

  return { errors, warnings };
}

/**
 * Simulate governance failures for negative controls.
 * @param {'new'|'removed'|'rename'} scenario
 * @param {object} registry
 * @param {string[]} contentSlugs
 */
export function simulateArticleGovernanceFailure(scenario, registry, contentSlugs) {
  const cloned = structuredClone(registry);
  if (scenario === 'new') {
    return validateArticleInstanceGovernance(cloned, [...contentSlugs, '__new-slug__'], []).errors;
  }
  if (scenario === 'removed') {
    return validateArticleInstanceGovernance(cloned, contentSlugs.slice(1), []).errors;
  }
  if (scenario === 'rename') {
    const renamed = contentSlugs.map((s, i) => (i === 0 ? '__renamed-slug__' : s));
    return validateArticleInstanceGovernance(cloned, renamed, []).errors;
  }
  return [];
}

/**
 * @param {string} marketingRoot
 * @param {object} registry
 * @returns {string[]}
 */
export function validateStaticExportApiBoundary(marketingRoot, registry) {
  const errors = [];
  const apiDir = path.join(marketingRoot, 'src', 'app', 'api');
  if (!fs.existsSync(apiDir)) return errors;

  const hasHandlers = walkForFiles(apiDir, /route\.(tsx|ts|js)$/);
  if (hasHandlers.length === 0) return errors;

  const classified = registry.routes.some(
    (r) =>
      r.source_path?.startsWith('src/app/api') &&
      r.static_export_compatible === true &&
      r.status === 'static_build_only_approved'
  );

  if (!classified) {
    errors.push(
      `STATIC_EXPORT_API_VIOLATION: marketing/src/app/api/** exists (${hasHandlers.join(', ')}) but no route is classified as static-build-only and static_export_compatible under static export`
    );
  }

  return errors;
}

/**
 * @param {string} dir
 * @param {RegExp} pattern
 * @param {string[]} results
 */
function walkForFiles(dir, pattern, results = []) {
  if (!fs.existsSync(dir)) return results;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walkForFiles(full, pattern, results);
    else if (pattern.test(entry.name)) results.push(path.relative(dir, full).replace(/\\/g, '/'));
  }
  return results;
}

/**
 * @param {object[]} scanResults
 * @param {object[]} routes
 * @returns {string[]}
 */
export function validateImportBoundaries(scanResults, routes) {
  const errors = [];
  for (const scan of scanResults) {
    const route = routes.find((r) => r.source_path === scan.file);
    if (!route || route.physical_surface !== 'marketing_static') continue;

    if (scan.imports_backend_api_client || scan.imports_token_handling || scan.imports_dashboard_provider) {
      errors.push(
        `IMPORT_BREACH: marketing_static route ${scan.file} imports backend/token/dashboard-provider code: ${scan.markers.join(', ')}`
      );
    }
  }
  return errors;
}
