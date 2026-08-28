#!/usr/bin/env node
/**
 * Token audit — scans component CSS/TSX for raw visual literals outside token layer.
 * Positive control: no violations in clean tree.
 * Negative control: injected hardcoded hex fails audit.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = join(import.meta.dirname, '..');
const TOKEN_LAYER = join(ROOT, 'src', 'tokens');
const COMPONENT_DIRS = [
  join(ROOT, 'src', 'components'),
  join(ROOT, 'src', 'dev'),
  join(ROOT, 'src', 'styles'),
];

const HEX_PATTERN = /#[0-9a-fA-F]{3,8}\b/g;

function walk(dir, acc = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else if (/\.(css|tsx|ts)$/.test(entry) && !entry.endsWith('.test.ts') && !entry.endsWith('.test.tsx'))
      acc.push(full);
  }
  return acc;
}

const ALLOWED_PX_VALUES = new Set(['1', '767', '768', '1023', '1024', '1439', '1440']);

function auditFile(filePath) {
  const rel = relative(ROOT, filePath);
  if (rel.startsWith('src\\tokens') || rel.startsWith('src/tokens')) return [];
  const content = readFileSync(filePath, 'utf8');
  const violations = [];

  for (const match of content.matchAll(HEX_PATTERN)) {
    violations.push({ file: rel, type: 'raw-hex', value: match[0] });
  }

  const lines = content.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.trim().startsWith('@media')) continue;
    for (const match of line.matchAll(/(\d+)px/g)) {
      if (ALLOWED_PX_VALUES.has(match[1])) continue;
      if (/var\(--sk-/.test(line)) continue;
      violations.push({ file: rel, type: 'raw-px', value: match[0], line: i + 1 });
    }
  }

  return violations;
}

export function runTokenAudit() {
  const files = COMPONENT_DIRS.flatMap((d) => walk(d, []));
  const violations = files.flatMap(auditFile);
  return { filesScanned: files.length, violations };
}

const isMain = process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/'));
if (isMain || process.argv[1]?.includes('token-audit')) {
  const result = runTokenAudit();
  console.log(JSON.stringify(result, null, 2));
  process.exit(result.violations.length ? 1 : 0);
}
