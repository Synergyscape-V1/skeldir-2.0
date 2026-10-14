#!/usr/bin/env node

/**
 * One-shot migration: discoverability.routes.json v1 → v2
 * Run: node scripts/discoverability/migrate-registry-to-v2.mjs
 */

import fs from 'node:fs';
import path from 'node:path';
import { parseArticleSlugsFromContent } from './lib/content-slugs.mjs';
import { scanFileBoundaries, deriveIsolationStatus } from './lib/import-boundary-scan.mjs';

const MARKETING_ROOT = process.cwd();
const REGISTRY_PATH = path.join(MARKETING_ROOT, 'discoverability.routes.json');

function implementedDefaults(route) {
  const notes = route.evidence_notes || '';
  const hasCanonicalInBuild = /Has canonical|canonical via/.test(notes);
  return {
    sitemap_implemented: false,
    canonical_implemented: hasCanonicalInBuild,
    jsonld_implemented: false,
    noindex_implemented: false,
    legal_link_required: route.logical_route === '/book-demo',
    legal_link_implemented: false,
  };
}

function isolationDefaults(route) {
  const sourcePath = route.source_path;
  let scan = {
    imports_auth_code: false,
    imports_backend_api_client: false,
    imports_tenant_logic: false,
    imports_token_handling: false,
    imports_dashboard_provider: false,
  };

  if (sourcePath) {
    const full = path.join(MARKETING_ROOT, sourcePath);
    scan = scanFileBoundaries(full);
  }

  const sharedRoot = route.physical_surface !== 'review_public_static' &&
    route.physical_surface !== 'missing_required' &&
    route.physical_surface !== 'external_backend';

  return {
    ...scan,
    shared_root_layout: sharedRoot,
    shared_client_chunks_observed: sharedRoot && route.physical_surface !== 'review_public_static',
    isolation_status: deriveIsolationStatus(scan, route.physical_surface || 'unknown'),
  };
}

function migrateRoute(route) {
  const base = {
    ...route,
    ...implementedDefaults(route),
    ...isolationDefaults(route),
    runtime_api: route.runtime_api ?? false,
    static_export_compatible: route.static_export_compatible ?? true,
  };

  if (base.canonical_url && !base.canonical_required) {
    base.canonical_required = true;
  }
  if (base.canonical_required === undefined) {
    base.canonical_required = Boolean(base.canonical_url);
  }

  return base;
}

function main() {
  const raw = JSON.parse(fs.readFileSync(REGISTRY_PATH, 'utf8'));
  const contentSlugs = parseArticleSlugsFromContent(MARKETING_ROOT);

  const articleRoutes = raw.routes.filter((r) => r.dynamic_route_pattern === '/resources/[slug]');
  const nonArticleRoutes = raw.routes.filter((r) => r.dynamic_route_pattern !== '/resources/[slug]');

  const articlePattern = {
    id: 'route-article-pattern',
    logical_route: '/resources/[slug]',
    source_path: 'src/app/resources/[slug]/page.tsx',
    next_resolved_route: '/resources/[slug]',
    dynamic_route_pattern: '/resources/[slug]',
    generated_concrete_routes: [],
    build_output_path_expected: 'out/resources/[slug].html',
    production_url: 'https://skeldir.com/resources/[slug]',
    route_type: 'article_pattern',
    indexability_class: 'indexable',
    physical_surface: 'marketing_static',
    deployment_surface: 'netlify_static',
    root_layout_group: 'root',
    shared_layouts: [
      'src/app/layout.tsx',
      'src/app/resources/layout.tsx',
      'src/app/resources/[slug]/layout.tsx',
    ],
    shared_client_providers: [],
    bundle_isolation_required: 'investigate',
    future_split_candidate: false,
    source_of_truth: 'src/data/articlesData.ts + generateStaticParams in src/app/resources/[slug]/layout.tsx',
    generated_instances_policy: 'auto_discovered',
    canonical_required: true,
    canonical_implemented: false,
    sitemap_required: true,
    sitemap_implemented: false,
    jsonld_required: true,
    jsonld_implemented: false,
    noindex_required: false,
    noindex_implemented: false,
    runtime_api: false,
    static_export_compatible: true,
    owner: 'content',
    status: 'active_defective',
    evidence_notes:
      'Pattern route. Concrete instances auto-discovered from articlesData.ts and out/resources/*.html. Page is use client with Loading... shell defect (D1 fix).',
    unknowns: [],
    ...isolationDefaults({ source_path: 'src/app/resources/[slug]/page.tsx', physical_surface: 'marketing_static' }),
  };

  const generatedArticles = contentSlugs.map((slug, idx) => {
    const old = articleRoutes.find((r) => r.logical_route === `/resources/${slug}`) || articleRoutes[idx] || {};
    return migrateRoute({
      ...old,
      id: `route-article-generated-${slug}`,
      logical_route: `/resources/${slug}`,
      generated_from: '/resources/[slug]',
      content_id: slug,
      route_type: 'article',
      dynamic_route_pattern: null,
      generated_concrete_routes: [`/resources/${slug}`],
      build_output_path_expected: `out/resources/${slug}.html`,
      production_url: `https://skeldir.com/resources/${slug}`,
      indexability_class: 'indexable',
      status: 'active_defective',
      source_of_truth: 'src/data/articlesData.ts',
      generated_instances_policy: 'auto_discovered',
      evidence_notes:
        old.evidence_notes ||
        'Generated instance from content manifest. Static HTML body is Loading... only until D1.',
    });
  });

  const migrated = nonArticleRoutes.map((route) => {
    let r = { ...route };

    if (r.id === 'route-api') {
      r = {
        ...r,
        id: 'route-api-docs',
        route_type: 'api_docs',
        physical_surface: 'docs_static',
        runtime_api: false,
        static_export_compatible: true,
        owner: 'content',
        status: 'missing_required',
        evidence_notes:
          'Static API documentation page (NOT runtime Trust API). Footer API Reference incorrectly links to /resources. Must be a static-export-compatible docs page under marketing/, not app/api route handlers.',
      };
    }

    if (r.id === 'route-book-demo') {
      r = {
        ...r,
        indexability_class: 'indexable_candidate',
        status: 'active_defective_until_static_body_verified',
        sitemap_required: false,
        sitemap_implemented: false,
        canonical_required: true,
        canonical_implemented: false,
        noindex_required: false,
        noindex_implemented: false,
        approval_required: 'growth/legal',
        evidence_notes:
          'Client component with spinner-only static export body. Links to /privacy (404). NOT sitemap-eligible until static body, canonical, and privacy link verified in D1/D2.',
      };
    }

    if (r.route_type === 'missing_required' && r.logical_route === '/docs') {
      r.physical_surface = 'docs_static';
      r.static_export_compatible = true;
      r.runtime_api = false;
    }

    if (r.route_type === 'missing_required' && r.logical_route === '/trust-envelope') {
      r.physical_surface = 'docs_static';
      r.static_export_compatible = true;
    }

    return migrateRoute(r);
  });

  const v2 = {
    ...raw,
    version: '2.0.0',
    generated: new Date().toISOString(),
    phase: 'D0-corrective',
    route_truth_hierarchy: [
      'out_build_artifacts',
      'next_build_artifacts',
      'content_generateStaticParams',
      'source_route_scan',
      'app_router_resolver_advisory',
    ],
    resolver_authority: 'advisory_only',
    indexability_class_enum: [
      'indexable',
      'indexable_candidate',
      'nonindex',
      'missing_required',
      'deprecated',
      'external',
      'unknown_requires_resolution',
    ],
    route_type_enum: [
      ...raw.route_type_enum.filter((t) => t !== 'unknown'),
      'article_pattern',
      'runtime_api_external',
    ],
    infrastructure_surfaces: [
      {
        id: 'infra-trust-api-runtime',
        name: 'Trust API runtime',
        route_type: 'runtime_api_external',
        physical_surface: 'external_backend',
        runtime_api: true,
        static_export_compatible: false,
        must_not_be_implemented_under: 'marketing/src/app/api',
        target_backend: 'Skeldir deterministic Python/FastAPI/Postgres backend (backend/app/trust/api.py)',
        routing_requirement: 'reverse_proxy_or_separate_api_domain',
        owner: 'backend/infrastructure',
        status: 'planned_external',
        evidence_notes:
          'Runtime Trust API is NOT part of the static marketing export. Do not implement as Next.js app/api route handlers under marketing/.',
      },
    ],
    physical_surface_governance: {
      physical_split_required_during_d0: 'not_established',
      current_condition: 'shared_static_export_and_shared_next_static_chunks',
      risk_level: 'structural_isolation_risk_not_yet_proven_breach',
      d1_allowed_scope: 'marketing_static_retrieval_fixes_only',
      split_trigger:
        'Before authenticated dashboard, Trust API runtime, or tenant-aware app surfaces ship: route-group/app-level split or equivalent isolation proof required.',
    },
    routes: [articlePattern, ...migrated, ...generatedArticles],
  };

  fs.writeFileSync(REGISTRY_PATH, `${JSON.stringify(v2, null, 2)}\n`, 'utf8');
  console.log(`Migrated registry to v2.0.0 (${v2.routes.length} routes, 1 pattern, ${generatedArticles.length} generated articles)`);
}

main();
