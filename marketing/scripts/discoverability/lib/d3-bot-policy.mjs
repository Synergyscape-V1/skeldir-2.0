/**
 * D3 — bot policy manifest validation, robots.txt alignment, sensitive-path scan helpers.
 * Keep compile order logic aligned with `src/app/robots.ts`.
 */

import fs from 'node:fs';
import path from 'node:path';

/** @typedef {{ user_agent_token: string, policy: string, robots_required: boolean, robots_rule: string, paths_allowed: string[], paths_disallowed: string[], source_url?: string, owner?: string, confidence?: string, functional_tier?: string, last_verified_date?: string, include_in_local_static_fetch_matrix?: boolean, fetch_test_user_agent?: string, id?: string }} BotEntry */

/**
 * @param {string} marketingRoot
 */
export function loadBotPolicyManifest(marketingRoot) {
  const p = path.join(marketingRoot, 'discoverability.bot-policy.json');
  if (!fs.existsSync(p)) throw new Error(`missing ${p}`);
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

/**
 * @param {any} manifest
 * @returns {string[]}
 */
export function validateBotManifestSchema(manifest) {
  const errors = [];
  if (!manifest || typeof manifest !== 'object') return ['manifest not an object'];
  if (!Array.isArray(manifest.bots) || manifest.bots.length < 1) errors.push('manifest.bots must be a non-empty array');

  const requiredIds = new Set(['oai_searchbot', 'gptbot', 'google_extended', 'ccbot']);
  const seen = new Set();

  for (const b of manifest.bots || []) {
    const id = b.id || '';
    if (id) seen.add(id);
    const fields = [
      'user_agent_token',
      'operator',
      'functional_tier',
      'policy',
      'robots_required',
      'robots_rule',
      'reason',
      'source_url',
      'last_verified_date',
      'confidence',
      'owner',
    ];
    for (const f of fields) {
      if (b[f] === undefined || b[f] === null || b[f] === '') {
        errors.push(`bot ${id || b.user_agent_token || '?'} missing or empty "${f}"`);
      }
    }
    if (b.policy === 'defer' || b.policy === 'monitor_only') {
      /* still require documentation fields above */
    }
    if (typeof b.robots_required !== 'boolean') errors.push(`bot ${id}: robots_required must be boolean`);
    if (!Array.isArray(b.paths_allowed)) errors.push(`bot ${id}: paths_allowed must be array`);
    if (!Array.isArray(b.paths_disallowed)) errors.push(`bot ${id}: paths_disallowed must be array`);
    if (b.functional_tier && String(b.functional_tier).includes('tier3') && b.policy === 'allow') {
      errors.push(`bot ${id}: training/bulk tier (tier3) must not use policy=allow without explicit exception note`);
    }
    if (b.functional_tier && String(b.functional_tier).includes('tier1') && b.policy === 'disallow') {
      errors.push(`bot ${id}: retrieval tier1 must not be policy=disallow without rationale (tiers conflated)`);
    }
  }

  for (const rid of requiredIds) {
    if (!seen.has(rid)) errors.push(`required bot id missing from manifest: ${rid}`);
  }

  if (!manifest.d2_dependency || typeof manifest.d2_dependency !== 'object') {
    errors.push('manifest.d2_dependency object required for release-governance reporting');
  }

  if (!manifest.llms_txt_scope || String(manifest.llms_txt_scope).trim() === '') {
    errors.push('manifest.llms_txt_scope required (D3 must not silently claim llms.txt)');
  }

  return errors;
}

/**
 * Build expected UA → { allowPaths: Set<string>, disallowPaths: Set<string> } from manifest compiler rules.
 * @param {any} manifest
 */
export function expectedRobotsAllowDisallowMap(manifest) {
  /** @type {Map<string, { allowPaths: Set<string>, disallowPaths: Set<string> }>} */
  const map = new Map();
  const bots = manifest.bots || [];

  const disallowFirst = bots.filter((b) => b.robots_required && b.robots_rule === 'disallow_root');
  const allowSecond = bots.filter((b) => b.robots_required && b.robots_rule === 'allow_root');

  function add(token, kind, pth) {
    const key = String(token).trim().toLowerCase();
    if (!map.has(key)) map.set(key, { allowPaths: new Set(), disallowPaths: new Set() });
    const g = map.get(key);
    if (kind === 'allow') g.allowPaths.add(pth);
    else g.disallowPaths.add(pth);
  }

  for (const b of disallowFirst) {
    const paths = b.paths_disallowed?.length ? b.paths_disallowed : ['/'];
    for (const p of paths) add(b.user_agent_token, 'disallow', p);
  }
  for (const b of allowSecond) {
    const paths = b.paths_allowed?.length ? b.paths_allowed : ['/'];
    for (const p of paths) add(b.user_agent_token, 'allow', p);
  }
  add('*', 'allow', '/');

  return map;
}

/**
 * Parse robots.txt into groups; each group has userAgents[] and rule lines.
 * Tolerates Next.js `User-Agent:` capitalization.
 * @param {string} body
 */
export function parseRobotsTxt(body) {
  const lines = body.split(/\r?\n/);
  /** @type {{ userAgents: string[], rules: { type: 'allow'|'disallow', path: string }[] }[]} */
  const groups = [];
  let current = null;

  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const ua = /^user-agent:\s*(.+)$/i.exec(line);
    if (ua) {
      if (!current) {
        current = { userAgents: [], rules: [] };
        groups.push(current);
      } else if (current.rules.length > 0) {
        current = { userAgents: [], rules: [] };
        groups.push(current);
      }
      current.userAgents.push(ua[1].trim());
      continue;
    }
    const allow = /^allow:\s*(.*)$/i.exec(line);
    if (allow) {
      if (!current) {
        current = { userAgents: ['*'], rules: [] };
        groups.push(current);
      }
      current.rules.push({ type: 'allow', path: allow[1].trim() });
      continue;
    }
    const disallow = /^disallow:\s*(.*)$/i.exec(line);
    if (disallow) {
      if (!current) {
        current = { userAgents: ['*'], rules: [] };
        groups.push(current);
      }
      current.rules.push({ type: 'disallow', path: disallow[1].trim() });
      continue;
    }
    if (/^sitemap:/i.test(line) || /^host:/i.test(line)) continue;
  }

  /** @type {Map<string, { allowPaths: Set<string>, disallowPaths: Set<string> }>} */
  const flattened = new Map();
  for (const g of groups) {
    const agents = g.userAgents.length ? g.userAgents : ['*'];
    for (const agent of agents) {
      const key = agent.trim().toLowerCase();
      if (!flattened.has(key)) flattened.set(key, { allowPaths: new Set(), disallowPaths: new Set() });
      const slot = flattened.get(key);
      for (const r of g.rules) {
        if (r.type === 'allow') slot.allowPaths.add(r.path || '/');
        else slot.disallowPaths.add(r.path || '/');
      }
    }
  }
  return { groups, byAgent: flattened };
}

/**
 * @param {Map<string, { allowPaths: Set<string>, disallowPaths: Set<string> }>} expected
 * @param {Map<string, { allowPaths: Set<string>, disallowPaths: Set<string> }>} actual
 * @param {any} manifest
 */
export function validateRobotsMatchesManifest(expected, actual, manifest) {
  const errors = [];
  for (const [key, ex] of expected) {
    const ac = actual.get(key);
    if (!ac) {
      errors.push(`robots.txt missing User-agent group for expected token "${key}"`);
      continue;
    }
    for (const p of ex.disallowPaths) {
      if (!ac.disallowPaths.has(p)) {
        errors.push(`robots mismatch: ${key} expected Disallow: ${p || '(empty)'} in merged rules`);
      }
    }
    for (const p of ex.allowPaths) {
      if (!ac.allowPaths.has(p)) {
        errors.push(`robots mismatch: ${key} expected Allow: ${p || '(empty)'} in merged rules`);
      }
    }
    if (key !== '*' && ac.allowPaths.has('/') && ac.disallowPaths.has('/')) {
      errors.push(`robots contradiction: ${key} has both Allow / and Disallow /`);
    }
  }

  /* Policy-driven checks: retrieval allow bots must not be fully blocked */
  for (const b of manifest.bots || []) {
    if (!b.robots_required) continue;
    if (b.policy !== 'allow') continue;
    const k = String(b.user_agent_token).toLowerCase();
    const ac = actual.get(k);
    if (!ac) {
      errors.push(`policy bot ${b.user_agent_token} (allow) missing from robots.txt`);
      continue;
    }
    if (ac.disallowPaths.has('/') && !ac.allowPaths.has('/')) {
      errors.push(`robots blocks ${b.user_agent_token} with Disallow / while policy=allow`);
    }
  }

  for (const b of manifest.bots || []) {
    if (!b.robots_required) continue;
    if (b.policy !== 'disallow') continue;
    const k = String(b.user_agent_token).toLowerCase();
    const ac = actual.get(k);
    if (!ac) {
      errors.push(`policy bot ${b.user_agent_token} (disallow) missing from robots.txt`);
      continue;
    }
    if (!ac.disallowPaths.has('/')) {
      errors.push(`robots allows ${b.user_agent_token} (no Disallow /) while policy=disallow`);
    }
  }

  return errors;
}

/**
 * Disallow values that suggest security-by-obscurity path disclosure (D3 H-D3-05).
 * @param {string} body
 */
export function validateRobotsDisallowNoSensitiveLeaks(body) {
  const errors = [];
  const forbiddenDisallowFragments = [
    /^\/admin/i,
    /^\/internal/i,
    /^\/api\//i,
    /^\/backend/i,
    /^\/tenant/i,
    /^\/dashboard/i,
    /^\/\.env/i,
    /^\/src\//i,
    /node_modules/i,
    /\.git/i,
  ];
  const { groups } = parseRobotsTxt(body);
  for (const g of groups) {
    for (const r of g.rules) {
      if (r.type !== 'disallow') continue;
      const p = r.path.trim();
      for (const re of forbiddenDisallowFragments) {
        if (re.test(p)) errors.push(`robots Disallow exposes sensitive pattern "${p}"`);
      }
    }
  }
  return errors;
}

/**
 * Exported for negative controls — mutate manifest copy in tests.
 * @param {any} manifest
 */
export function validatePolicyRobotsAlignmentCore(manifest, robotsBody) {
  const errs = [];
  errs.push(...validateBotManifestSchema(manifest));
  if (errs.some((e) => e.includes('missing'))) return errs;
  const expected = expectedRobotsAllowDisallowMap(manifest);
  const { byAgent: actual } = parseRobotsTxt(robotsBody);
  errs.push(...validateRobotsMatchesManifest(expected, actual, manifest));
  errs.push(...validateRobotsDisallowNoSensitiveLeaks(robotsBody));
  return errs;
}
