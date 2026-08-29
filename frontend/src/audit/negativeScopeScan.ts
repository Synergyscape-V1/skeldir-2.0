import { readFileSync, readdirSync, statSync } from 'node:fs';

import { join, relative } from 'node:path';



const ROOT = join(import.meta.dirname, '..', '..');



/** Level 0 substrate paths — auth/app excluded so Level 0 audit stays green after Level 1 */

const LEVEL0_SCAN_ROOTS = [

  join(ROOT, 'src', 'components', 'layout'),

  join(ROOT, 'src', 'components', 'trust'),

  join(ROOT, 'src', 'components', 'financial'),

  join(ROOT, 'src', 'components', 'icons'),

  join(ROOT, 'src', 'dev', 'Level0SpecimenGallery.tsx'),

  join(ROOT, 'src', 'lib'),

  join(ROOT, 'src', 'styles'),

  join(ROOT, 'src', 'tokens'),

];



const FORBIDDEN_ROUTES = [

  '/login',

  '/signup',

  '/onboarding',

  '/app',

  '/claims',

  '/trust/',

  '/channels',

  '/benchmarks',

  '/budget',

  '/exceptions',

  '/audit',

  '/agents',

  '/integrations',

  '/settings/policy',

  '/settings/team',

  '/settings/billing',

  'Command Center',

  'LoginForm',

  'SignUpForm',

  'GitHubOAuth',

];



const FORBIDDEN_API = ['fetch(', 'axios', 'Trust API', '/api/trust', '/api/auth', 'useQuery', 'useSWR'];



const SCAN_EXCLUDE = ['negativeScopeScan.ts', 'level1NegativeScopeScan.ts', 'financialScan.ts', '.test.ts', '.test.tsx'];



function walkPath(path: string, acc: string[] = []): string[] {

  if (!statSync(path).isDirectory()) {

    if (/\.(tsx|ts)$/.test(path)) acc.push(path);

    return acc;

  }

  for (const entry of readdirSync(path)) {

    walkPath(join(path, entry), acc);

  }

  return acc;

}



function collectFiles(roots: string[]): string[] {

  const files: string[] = [];

  for (const root of roots) {

    if (!statSync(root).isDirectory() && /\.(tsx|ts)$/.test(root)) {

      files.push(root);

      continue;

    }

    walkPath(root, files);

  }

  return files;

}



export function runNegativeScopeScan() {

  const files = collectFiles(LEVEL0_SCAN_ROOTS);

  const violations: Array<{ file: string; type: string; value: string }> = [];



  for (const file of files) {

    const rel = relative(ROOT, file);

    if (SCAN_EXCLUDE.some((x) => rel.includes(x))) continue;



    const content = readFileSync(file, 'utf8');



    for (const term of FORBIDDEN_ROUTES) {

      if (content.includes(term)) {

        if (new RegExp(`['\`"]${term.replace('/', '\\/')}`).test(content)) {

          violations.push({ file: rel, type: 'forbidden-route', value: term });

        }

      }

    }



    for (const api of FORBIDDEN_API) {

      if (content.includes(api) && !rel.includes('copy.ts')) {

        violations.push({ file: rel, type: 'forbidden-api', value: api });

      }

    }

  }



  return { filesScanned: files.length, violations };

}


