/**
 * D6-C — Entity semantics drift scanner (D4 registry binding for evidence routes).
 */

import fs from 'node:fs';
import path from 'node:path';
import { extractMainAndBody, normalizedPosition } from './d6-evidence-frontload.mjs';

const DEFAULT_REGISTRY = 'entity-semantics-registry.json';

/**
 * @param {string} marketingRoot
 */
export function loadEntitySemanticsRegistry(marketingRoot) {
  const p = path.join(marketingRoot, DEFAULT_REGISTRY);
  if (!fs.existsSync(p)) {
    throw new Error(`Missing ${p} — required for D6 entity semantics drift control`);
  }
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

/**
 * @param {string} html
 */
function extractTitle(html) {
  const m = /<title[^>]*>([^<]*)<\/title>/i.exec(html);
  return m ? m[1].trim() : '';
}

/**
 * @param {string} html
 */
function extractMetaDescription(html) {
  const m =
    /<meta[^>]*name=["']description["'][^>]*content=["']([^"']*)["']/i.exec(html) ||
    /<meta[^>]*content=["']([^"']*)["'][^>]*name=["']description["']/i.exec(html);
  return m ? m[1].trim() : '';
}

/**
 * @param {string} html
 */
function extractH1(html) {
  const m = /<h1[^>]*>([\s\S]*?)<\/h1>/i.exec(html);
  if (!m) return '';
  return m[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}

/**
 * @param {string} mainHtml
 * @param {string} sectionLabel
 */
function extractSectionText(mainHtml, sectionLabel) {
  const re = new RegExp(
    `<h2[^>]*>\\s*${sectionLabel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*</h2>([\\s\\S]*?)(?=<h2\\b|$)`,
    'i',
  );
  const m = re.exec(mainHtml);
  if (!m) return '';
  return m[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}

/**
 * @param {string} mainHtml
 * @param {number} fraction
 */
function firstFractionOfMainText(mainHtml, fraction = 0.3) {
  const len = mainHtml.length;
  const slice = mainHtml.slice(0, Math.ceil(len * fraction));
  return slice.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}

/**
 * @param {object} reg
 */
export function validateEntitySemanticsRegistryShape(reg) {
  const errors = [];
  if (!reg?.version) errors.push('entity-semantics-registry: missing version');
  for (const f of ['canonicalName', 'disallowedTerminology', 'highRiskTerminology']) {
    if (!(f in reg)) errors.push(`entity-semantics-registry: missing ${f}`);
  }
  return errors;
}

/**
 * @param {string} route
 * @param {object} reg
 */
function routeHasException(route, termId, reg) {
  return (reg.routeExceptions || []).some(
    (ex) => ex.route === route && (ex.allowTermIds || []).includes(termId),
  );
}

/**
 * @param {string} text
 * @param {object} term
 * @param {string} route
 * @param {object} reg
 * @param {'disallowed'|'highRisk'} kind
 */
function matchTerm(text, term, route, reg, kind) {
  if (routeHasException(route, term.id, reg)) return null;
  const re = new RegExp(term.pattern, term.flags || 'i');
  const m = re.exec(text);
  if (!m) return null;
  if (kind === 'highRisk' && term.unlessNearPattern) {
    const start = Math.max(0, m.index - 120);
    const end = Math.min(text.length, m.index + m[0].length + 120);
    const window = text.slice(start, end);
    const ctx = new RegExp(term.unlessNearPattern, 'i');
    if (ctx.test(window)) return null;
  }
  return { id: term.id, match: m[0], kind };
}

/**
 * @param {string} logicalPath
 * @param {string} html
 * @param {object} reg
 * @returns {{ errors: string[], scan: object }}
 */
export function validateD6EntitySemanticsDrift(logicalPath, html, reg) {
  const errors = [];
  const fields = {
    title: extractTitle(html),
    metaDescription: extractMetaDescription(html),
    h1: extractH1(html),
    bluf: '',
    keyFacts: '',
    mainEarly: '',
    jsonLd: '',
  };

  const extracted = extractMainAndBody(html);
  if (extracted) {
    fields.bluf = extractSectionText(extracted.main, 'Bottom line');
    fields.keyFacts = extractSectionText(extracted.main, 'Key Facts');
    fields.mainEarly = firstFractionOfMainText(extracted.main, 0.3);
  }

  const ldBlocks = [...html.matchAll(/<script[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi)];
  fields.jsonLd = ldBlocks.map((b) => b[1]).join('\n');

  const scannedLabels = [];
  const hits = [];

  const buckets = [
    ['title', fields.title],
    ['meta description', fields.metaDescription],
    ['H1', fields.h1],
    ['BLUF', fields.bluf],
    ['Key Facts', fields.keyFacts],
    ['first 30% of main', fields.mainEarly],
    ['JSON-LD', fields.jsonLd],
  ];

  for (const [label, text] of buckets) {
    if (!text) continue;
    scannedLabels.push(label);
    for (const term of reg.disallowedTerminology || []) {
      const hit = matchTerm(text, term, logicalPath, reg, 'disallowed');
      if (hit) {
        hits.push({ ...hit, field: label });
        errors.push(
          `${logicalPath}: disallowed entity term "${hit.id}" in ${label}: "${hit.match}"`,
        );
      }
    }
    for (const term of reg.highRiskTerminology || []) {
      const hit = matchTerm(text, term, logicalPath, reg, 'highRisk');
      if (hit) {
        hits.push({ ...hit, field: label });
        errors.push(
          `${logicalPath}: high-risk entity term "${hit.id}" in ${label} without qualifying context: "${hit.match}"`,
        );
      }
    }
  }

  return {
    errors,
    scan: {
      route: logicalPath,
      scannedFields: scannedLabels,
      disallowedTermsFound: hits.filter((h) => h.kind === 'disallowed').map((h) => h.id),
      highRiskTermsFound: hits.filter((h) => h.kind === 'highRisk').map((h) => h.id),
      exceptions: (reg.routeExceptions || []).filter((e) => e.route === logicalPath),
      result: errors.length ? 'fail' : 'pass',
    },
  };
}
