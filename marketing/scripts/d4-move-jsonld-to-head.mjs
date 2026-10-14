#!/usr/bin/env node
/**
 * D4-C2 — Static export contract: relocate `<script type="application/ld+json">` from
 * the React-rendered document body into `<head>` so crawlers see deterministic,
 * early semantic identity (Next.js App Router does not hoist body JSON-LD).
 *
 * Idempotent: scripts already wholly inside `<head>` are left unchanged.
 */

import fs from "node:fs";
import path from "node:path";

const OUT_DIR = path.join(process.cwd(), "out");

const JSON_LD_SCRIPT_RE = /<script[^>]*type=["']application\/ld\+json["'][^>]*>[\s\S]*?<\/script>/gi;

/** @param {string} dir */
function walkHtmlFiles(dir) {
  const out = [];
  if (!fs.existsSync(dir)) return out;
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) out.push(...walkHtmlFiles(p));
    else if (ent.name.endsWith(".html")) out.push(p);
  }
  return out;
}

/**
 * @param {string} html
 * @returns {{ html: string, moved: number }}
 */
export function moveJsonLdScriptsIntoHead(html) {
  const headClose = html.search(/<\/head>/i);
  if (headClose === -1) return { html, moved: 0 };

  const matches = [...html.matchAll(JSON_LD_SCRIPT_RE)];
  const toMove = [];
  for (const m of matches) {
    const start = m.index;
    const end = start + m[0].length;
    const whollyInHead = start < headClose && end <= headClose;
    if (!whollyInHead) toMove.push({ start, end, tag: m[0] });
  }
  if (toMove.length === 0) return { html, moved: 0 };

  toMove.sort((a, b) => b.start - a.start);
  let s = html;
  for (const { start, end, tag } of toMove) {
    s = s.slice(0, start) + s.slice(end);
  }
  const insertAt = s.search(/<\/head>/i);
  if (insertAt === -1) return { html, moved: 0 };
  const block = toMove
    .slice()
    .sort((a, b) => a.start - b.start)
    .map((x) => x.tag)
    .join("\n");
  const next = `${s.slice(0, insertAt)}\n${block}\n${s.slice(insertAt)}`;
  return { html: next, moved: toMove.length };
}

function main() {
  const files = walkHtmlFiles(OUT_DIR);
  if (files.length === 0) {
    console.warn("[d4-move-jsonld-to-head] no HTML files under out/ — skip");
    return;
  }
  let totalMoved = 0;
  for (const abs of files) {
    const raw = fs.readFileSync(abs, "utf8");
    const { html, moved } = moveJsonLdScriptsIntoHead(raw);
    if (moved > 0) {
      fs.writeFileSync(abs, html, "utf8");
      totalMoved += moved;
      console.log(`[d4-move-jsonld-to-head] ${path.relative(process.cwd(), abs)}: moved ${moved} block(s) into <head>`);
    }
  }
  if (totalMoved === 0) {
    console.log("[d4-move-jsonld-to-head] all JSON-LD already in <head> (0 moves)");
  }
}

main();
