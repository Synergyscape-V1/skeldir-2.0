/**
 * D6-C — Evidence page front-loading (retrieval priority in <main>).
 */

/** Required retrieval sections must begin within this fraction of normalized <main> HTML. */
export const D6_FRONTLOAD_MAX_NORMALIZED = 0.3;

export const D6_RETRIEVAL_SECTIONS = [
  {
    key: 'bluf',
    label: 'Bottom line',
    idPatterns: ['id="bottom-line-heading"', "id='bottom-line-heading'", 'id="bottom-line"'],
    headingPatterns: [/<h2[^>]*>\s*Bottom line\s*<\/h2>/i],
  },
  {
    key: 'keyFacts',
    label: 'Key Facts',
    idPatterns: ['id="key-facts-heading"', "id='key-facts-heading'", 'id="key-facts"'],
    headingPatterns: [/<h2[^>]*>\s*Key Facts\s*<\/h2>/i],
  },
  {
    key: 'claimsTable',
    label: 'Claims and evidence',
    idPatterns: ['id="claims-evidence-heading"', "id='claims-evidence-heading'", 'id="claims-and-evidence"'],
    headingPatterns: [/<h2[^>]*>\s*Claims and evidence\s*<\/h2>/i],
  },
];

export const D6_DEFERRED_SECTIONS = [
  {
    key: 'methodology',
    label: 'Methodology',
    idPatterns: ['id="methodology-heading"', "id='methodology-heading'", 'id="methodology"'],
    headingPatterns: [/<h2[^>]*>\s*Methodology\s*<\/h2>/i],
  },
  {
    key: 'limitations',
    label: 'Limitations',
    idPatterns: ['id="limitations-heading"', "id='limitations-heading'", 'id="limitations"'],
    headingPatterns: [/<h2[^>]*>\s*Limitations\s*<\/h2>/i],
  },
];

/**
 * @param {string} html
 * @returns {{ main: string, body: string } | null}
 */
export function extractMainAndBody(html) {
  const mainM = /<main\b[^>]*>([\s\S]*?)<\/main>/i.exec(html);
  if (!mainM) return null;
  const bodyM = /<body\b[^>]*>([\s\S]*?)<\/body>/i.exec(html);
  return { main: mainM[1], body: bodyM ? bodyM[1] : html };
}

/**
 * @param {string} haystack
 * @param {typeof D6_RETRIEVAL_SECTIONS[0]} spec
 * @returns {number}
 */
export function findSectionByteOffset(haystack, spec) {
  let best = -1;
  for (const p of spec.idPatterns) {
    const i = haystack.indexOf(p);
    if (i >= 0 && (best < 0 || i < best)) best = i;
  }
  for (const re of spec.headingPatterns) {
    const m = re.exec(haystack);
    if (m && m.index >= 0 && (best < 0 || m.index < best)) best = m.index;
  }
  return best;
}

/**
 * @param {number} offset
 * @param {number} len
 */
export function normalizedPosition(offset, len) {
  if (len <= 0) return offset <= 0 ? 0 : 1;
  if (offset < 0) return 1;
  return offset / len;
}

/**
 * @param {string} logicalPath
 * @param {string} html
 * @param {{ maxNormalized?: number }} [opts]
 * @returns {{ errors: string[], rows: object[] }}
 */
export function validateD6EvidenceFrontLoad(logicalPath, html, opts = {}) {
  const maxNorm = opts.maxNormalized ?? D6_FRONTLOAD_MAX_NORMALIZED;
  const errors = [];
  const rows = [];

  const extracted = extractMainAndBody(html);
  if (!extracted) {
    errors.push(`${logicalPath}: missing <main> — cannot measure retrieval front-loading`);
    return { errors, rows };
  }

  const { main, body } = extracted;
  const mainLen = main.length;
  const bodyLen = body.length;

  if (!/<main\b/i.test(html)) {
    errors.push(`${logicalPath}: BLUF must appear inside <main>`);
  }

  const offsets = {};
  for (const spec of D6_RETRIEVAL_SECTIONS) {
    const offsetMain = findSectionByteOffset(main, spec);
    const offsetBody = findSectionByteOffset(body, spec);
    const normMain = normalizedPosition(offsetMain, mainLen);
    const normBody = normalizedPosition(offsetBody, bodyLen);
    offsets[spec.key] = offsetMain;

    const pass = offsetMain >= 0 && normMain <= maxNorm;
    rows.push({
      route: logicalPath,
      section: spec.label,
      byteOffsetInMain: offsetMain,
      normalizedPositionInMain: Number(normMain.toFixed(4)),
      byteOffsetInBody: offsetBody,
      normalizedPositionInBody: Number(normBody.toFixed(4)),
      result: pass ? 'pass' : 'fail',
    });

    if (offsetMain < 0) {
      errors.push(`${logicalPath}: missing retrieval section "${spec.label}" in <main>`);
    } else if (normMain > maxNorm) {
      errors.push(
        `${logicalPath}: "${spec.label}" at ${(normMain * 100).toFixed(1)}% of <main> (max ${(maxNorm * 100).toFixed(0)}%)`,
      );
    }
  }

  for (const spec of D6_DEFERRED_SECTIONS) {
    const offsetMain = findSectionByteOffset(main, spec);
    const normMain = normalizedPosition(offsetMain, mainLen);
    rows.push({
      route: logicalPath,
      section: spec.label,
      byteOffsetInMain: offsetMain,
      normalizedPositionInMain: Number(normMain.toFixed(4)),
      byteOffsetInBody: findSectionByteOffset(body, spec),
      normalizedPositionInBody: Number(normalizedPosition(findSectionByteOffset(body, spec), bodyLen).toFixed(4)),
      result: offsetMain >= 0 ? 'info' : 'missing',
    });
  }

  const blufOff = offsets.bluf ?? -1;
  const methOff = findSectionByteOffset(main, D6_DEFERRED_SECTIONS[0]);
  const limOff = findSectionByteOffset(main, D6_DEFERRED_SECTIONS[1]);
  const claimsOff = offsets.claimsTable ?? -1;

  if (methOff >= 0 && claimsOff >= 0 && methOff < claimsOff) {
    errors.push(`${logicalPath}: Methodology appears before Claims and evidence`);
  }
  if (limOff >= 0 && blufOff >= 0 && limOff < blufOff) {
    errors.push(`${logicalPath}: Limitations appears before Bottom line (BLUF)`);
  }
  if (limOff >= 0 && methOff >= 0 && limOff < methOff) {
    errors.push(`${logicalPath}: Limitations appears before Methodology`);
  }

  return { errors, rows };
}

/**
 * @param {string} html
 * @returns {boolean}
 */
export function blufOutsideMain(html) {
  const blufInBody = /<body[\s\S]*Bottom line[\s\S]*<\/body>/i.test(html);
  const mainHasBluf = /<main\b[\s\S]*Bottom line[\s\S]*<\/main>/i.test(html);
  return blufInBody && !mainHasBluf;
}
