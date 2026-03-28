#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

function parseArgs(argv) {
  const args = new Map();
  for (let index = 2; index < argv.length; index += 1) {
    const current = argv[index];
    if (!current.startsWith("--")) {
      continue;
    }
    const key = current.slice(2);
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      args.set(key, "true");
      continue;
    }
    args.set(key, next);
    index += 1;
  }
  return args;
}

function resolvePath(repoRoot, rawPath) {
  if (path.isAbsolute(rawPath)) {
    return path.resolve(rawPath);
  }
  return path.resolve(repoRoot, rawPath);
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

function normalizePath(filePath) {
  return path.resolve(filePath).replace(/\\/g, "/");
}

function toRepoRelative(repoRoot, filePath) {
  const normalizedRepo = normalizePath(repoRoot);
  const normalizedFile = normalizePath(filePath);
  if (normalizedFile.startsWith(`${normalizedRepo}/`)) {
    return normalizedFile.slice(normalizedRepo.length + 1);
  }
  return normalizedFile;
}

function isTsSource(filePath) {
  return [".ts", ".tsx", ".js", ".jsx", ".mts", ".cts"].includes(
    path.extname(filePath).toLowerCase(),
  );
}

function collectFilesUnderRoot(rootPath) {
  const files = [];
  if (!fs.existsSync(rootPath)) {
    return files;
  }
  const stack = [rootPath];
  while (stack.length > 0) {
    const current = stack.pop();
    const stat = fs.statSync(current);
    if (stat.isDirectory()) {
      const children = fs.readdirSync(current);
      for (const child of children) {
        stack.push(path.join(current, child));
      }
      continue;
    }
    if (stat.isFile() && isTsSource(current)) {
      files.push(current);
    }
  }
  return files;
}

function readTsConfig(tsConfigFile) {
  const readResult = ts.readConfigFile(tsConfigFile, ts.sys.readFile);
  if (readResult.error) {
    throw new Error(
      `failed to read tsconfig: ${ts.flattenDiagnosticMessageText(readResult.error.messageText, "\n")}`,
    );
  }
  const parsed = ts.parseJsonConfigFileContent(
    readResult.config,
    ts.sys,
    path.dirname(tsConfigFile),
  );
  if (parsed.errors && parsed.errors.length > 0) {
    const rendered = parsed.errors
      .map((error) => ts.flattenDiagnosticMessageText(error.messageText, "\n"))
      .join("\n");
    throw new Error(`failed to parse tsconfig:\n${rendered}`);
  }
  return parsed;
}

function getTerminalIdentifierName(expressionNode) {
  if (!expressionNode) {
    return "";
  }
  if (ts.isIdentifier(expressionNode)) {
    return expressionNode.text;
  }
  if (ts.isPropertyAccessExpression(expressionNode)) {
    return expressionNode.name.text;
  }
  return "";
}

function collectSourceMetadata({
  sourceFile,
  importMatcherSet,
  newExpressionMatcherSet,
  callExpressionMatcherSet,
  stringLiteralMatcherSet,
}) {
  const importUsages = [];
  const signatureViolations = [];
  const sourceText = sourceFile.getFullText();

  const pushSignatureViolation = (node, signatureId, matchValue) => {
    const position = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
    signatureViolations.push({
      signature_id: signatureId,
      match: matchValue,
      line: position.line + 1,
      column: position.character + 1,
    });
  };

  const visit = (node) => {
    if (
      ts.isImportDeclaration(node) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      const specifier = node.moduleSpecifier.text;
      const position = sourceFile.getLineAndCharacterOfPosition(node.moduleSpecifier.getStart(sourceFile));
      importUsages.push({
        specifier,
        line: position.line + 1,
        column: position.character + 1,
      });
      const signatureId = importMatcherSet.get(specifier);
      if (signatureId) {
        pushSignatureViolation(node.moduleSpecifier, signatureId, specifier);
      }
    }

    if (
      ts.isExportDeclaration(node) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      const specifier = node.moduleSpecifier.text;
      const position = sourceFile.getLineAndCharacterOfPosition(node.moduleSpecifier.getStart(sourceFile));
      importUsages.push({
        specifier,
        line: position.line + 1,
        column: position.character + 1,
      });
      const signatureId = importMatcherSet.get(specifier);
      if (signatureId) {
        pushSignatureViolation(node.moduleSpecifier, signatureId, specifier);
      }
    }

    if (
      ts.isImportEqualsDeclaration(node) &&
      ts.isExternalModuleReference(node.moduleReference) &&
      node.moduleReference.expression &&
      ts.isStringLiteral(node.moduleReference.expression)
    ) {
      const specifier = node.moduleReference.expression.text;
      const position = sourceFile.getLineAndCharacterOfPosition(node.moduleReference.expression.getStart(sourceFile));
      importUsages.push({
        specifier,
        line: position.line + 1,
        column: position.character + 1,
      });
      const signatureId = importMatcherSet.get(specifier);
      if (signatureId) {
        pushSignatureViolation(node.moduleReference.expression, signatureId, specifier);
      }
    }

    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments.length > 0 &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      const specifier = node.arguments[0].text;
      const position = sourceFile.getLineAndCharacterOfPosition(node.arguments[0].getStart(sourceFile));
      importUsages.push({
        specifier,
        line: position.line + 1,
        column: position.character + 1,
      });
      const signatureId = importMatcherSet.get(specifier);
      if (signatureId) {
        pushSignatureViolation(node.arguments[0], signatureId, specifier);
      }
    }

    if (ts.isNewExpression(node)) {
      const identifierName = getTerminalIdentifierName(node.expression);
      const signatureId = newExpressionMatcherSet.get(identifierName);
      if (signatureId) {
        pushSignatureViolation(node, signatureId, identifierName);
      }
    }

    if (ts.isCallExpression(node)) {
      const identifierName = getTerminalIdentifierName(node.expression);
      const signatureId = callExpressionMatcherSet.get(identifierName);
      if (signatureId) {
        pushSignatureViolation(node, signatureId, identifierName);
      }
    }

    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      const value = sourceText.slice(node.getStart(sourceFile) + 1, node.getEnd() - 1);
      const signatureId = stringLiteralMatcherSet.get(value);
      if (signatureId) {
        pushSignatureViolation(node, signatureId, value);
      }
    }

    ts.forEachChild(node, visit);
  };

  visit(sourceFile);
  return { importUsages, signatureViolations };
}

function resolveModule({ specifier, containingFile, compilerOptions }) {
  const resolution = ts.resolveModuleName(specifier, containingFile, compilerOptions, ts.sys);
  if (!resolution || !resolution.resolvedModule) {
    return null;
  }
  const resolved = resolution.resolvedModule.resolvedFileName;
  if (!resolved) {
    return null;
  }
  return normalizePath(resolved);
}

function buildGraph({
  program,
  compilerOptions,
  importMatcherSet,
  newExpressionMatcherSet,
  callExpressionMatcherSet,
  stringLiteralMatcherSet,
}) {
  const sourceMetadata = new Map();
  const adjacency = new Map();

  for (const sourceFile of program.getSourceFiles()) {
    if (sourceFile.isDeclarationFile) {
      continue;
    }
    const normalizedFilePath = normalizePath(sourceFile.fileName);
    if (normalizedFilePath.includes("/node_modules/")) {
      continue;
    }
    const metadata = collectSourceMetadata({
      sourceFile,
      importMatcherSet,
      newExpressionMatcherSet,
      callExpressionMatcherSet,
      stringLiteralMatcherSet,
    });
    sourceMetadata.set(normalizedFilePath, metadata);
  }

  for (const [sourceFilePath, metadata] of sourceMetadata.entries()) {
    const neighbors = new Set();
    for (const importUsage of metadata.importUsages) {
      const resolved = resolveModule({
        specifier: importUsage.specifier,
        containingFile: sourceFilePath,
        compilerOptions,
      });
      if (!resolved) {
        continue;
      }
      if (resolved.includes("/node_modules/")) {
        continue;
      }
      if (!isTsSource(resolved)) {
        continue;
      }
      neighbors.add(resolved);
    }
    adjacency.set(sourceFilePath, neighbors);
  }

  return { sourceMetadata, adjacency };
}

function findImportFenceViolations({
  decisionFiles,
  exceptionFiles,
  adjacency,
  repoRoot,
  exceptionToId,
}) {
  const violations = [];
  const seen = new Set();

  for (const decisionFile of decisionFiles) {
    if (!adjacency.has(decisionFile)) {
      continue;
    }
    const queue = [decisionFile];
    const parents = new Map([[decisionFile, null]]);
    const visited = new Set([decisionFile]);

    while (queue.length > 0) {
      const current = queue.shift();
      if (exceptionFiles.has(current)) {
        const exceptionId = exceptionToId.get(current) || "unknown_exception";
        const uniqueKey = `${decisionFile}::${current}`;
        if (!seen.has(uniqueKey)) {
          seen.add(uniqueKey);
          const trace = [];
          let cursor = current;
          while (cursor !== null) {
            trace.push(toRepoRelative(repoRoot, cursor));
            cursor = parents.get(cursor) ?? null;
          }
          trace.reverse();
          violations.push({
            type: "realtime_import_fence",
            exception_id: exceptionId,
            file: toRepoRelative(repoRoot, decisionFile),
            trace,
          });
        }
      }
      const neighbors = adjacency.get(current) || new Set();
      for (const next of neighbors) {
        if (visited.has(next)) {
          continue;
        }
        visited.add(next);
        parents.set(next, current);
        queue.push(next);
      }
    }
  }

  return violations;
}

function normalizeSignatureMatchers(signatures) {
  const importMatcherSet = new Map();
  const newExpressionMatcherSet = new Map();
  const callExpressionMatcherSet = new Map();
  const stringLiteralMatcherSet = new Map();

  for (const signature of signatures) {
    const signatureId = String(signature.signature_id || "").trim();
    const kind = String(signature.kind || "").trim();
    const match = String(signature.match || "").trim();
    if (!signatureId || !kind || !match) {
      continue;
    }
    if (kind === "import_specifier") {
      importMatcherSet.set(match, signatureId);
    } else if (kind === "new_expression_identifier") {
      newExpressionMatcherSet.set(match, signatureId);
    } else if (kind === "call_expression_identifier") {
      callExpressionMatcherSet.set(match, signatureId);
    } else if (kind === "string_literal") {
      stringLiteralMatcherSet.set(match, signatureId);
    }
  }

  return {
    importMatcherSet,
    newExpressionMatcherSet,
    callExpressionMatcherSet,
    stringLiteralMatcherSet,
  };
}

function collectDecisionFiles(repoRoot, matrix) {
  const decisionFiles = new Set();
  for (const rawFile of matrix.decision_surface_files || []) {
    const resolved = normalizePath(resolvePath(repoRoot, rawFile));
    if (fs.existsSync(resolved) && fs.statSync(resolved).isFile()) {
      decisionFiles.add(resolved);
    }
  }
  for (const rawRoot of matrix.decision_surface_roots || []) {
    const resolvedRoot = resolvePath(repoRoot, rawRoot);
    for (const filePath of collectFilesUnderRoot(resolvedRoot)) {
      decisionFiles.add(normalizePath(filePath));
    }
  }
  return decisionFiles;
}

function collectExceptionFiles(repoRoot, registry) {
  const exceptionFiles = new Set();
  const exceptionToId = new Map();
  for (const exception of registry.exceptions || []) {
    const exceptionId = String(exception.exception_id || "").trim();
    for (const rawFile of exception.exception_surface_files || []) {
      const resolved = normalizePath(resolvePath(repoRoot, rawFile));
      if (fs.existsSync(resolved) && fs.statSync(resolved).isFile()) {
        exceptionFiles.add(resolved);
        if (exceptionId) {
          exceptionToId.set(resolved, exceptionId);
        }
      }
    }
  }
  return { exceptionFiles, exceptionToId };
}

function main() {
  const args = parseArgs(process.argv);
  const repoRoot = normalizePath(resolvePath(process.cwd(), args.get("repo-root") || "."));
  const matrixFile = resolvePath(repoRoot, args.get("matrix-file") || "contracts-internal/governance/b15_p6_prohibited_signature_matrix.main.json");
  const registryFile = resolvePath(repoRoot, args.get("registry-file") || "contracts-internal/governance/b15_p6_realtime_exception_registry.main.json");
  const tsConfigFile = resolvePath(repoRoot, args.get("tsconfig-file") || "frontend/tsconfig.json");

  const matrix = readJson(matrixFile);
  const registry = readJson(registryFile);
  const decisionFiles = collectDecisionFiles(repoRoot, matrix);
  const { exceptionFiles, exceptionToId } = collectExceptionFiles(repoRoot, registry);
  const missingDecisionFiles = [];
  if (decisionFiles.size === 0) {
    missingDecisionFiles.push("decision_surface_set_empty");
  }

  const parsedConfig = readTsConfig(tsConfigFile);
  const rootNames = Array.from(
    new Set([...parsedConfig.fileNames, ...Array.from(decisionFiles)]),
  );
  const program = ts.createProgram({
    rootNames,
    options: parsedConfig.options,
  });

  const matchers = normalizeSignatureMatchers(matrix.forbidden_signatures || []);
  const { sourceMetadata, adjacency } = buildGraph({
    program,
    compilerOptions: parsedConfig.options,
    ...matchers,
  });

  const violations = [];
  for (const errorCode of missingDecisionFiles) {
    violations.push({
      type: "contract_violation",
      violation_id: errorCode,
      file: "",
    });
  }

  for (const decisionFile of decisionFiles) {
    const metadata = sourceMetadata.get(decisionFile);
    if (!metadata) {
      violations.push({
        type: "contract_violation",
        violation_id: "decision_surface_not_parsed",
        file: toRepoRelative(repoRoot, decisionFile),
      });
      continue;
    }
    for (const signatureViolation of metadata.signatureViolations) {
      violations.push({
        type: "forbidden_signature",
        signature_id: signatureViolation.signature_id,
        file: toRepoRelative(repoRoot, decisionFile),
        line: signatureViolation.line,
        column: signatureViolation.column,
        detail: signatureViolation.match,
      });
    }
  }

  violations.push(
    ...findImportFenceViolations({
      decisionFiles,
      exceptionFiles,
      adjacency,
      repoRoot,
      exceptionToId,
    }),
  );

  process.stdout.write(`${JSON.stringify({ violations }, null, 2)}\n`);
}

try {
  main();
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`b15_p6_graph_guard_failed:${message}\n`);
  process.exit(1);
}
