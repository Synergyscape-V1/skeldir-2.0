import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(process.cwd());

function read(rel: string): string {
  return readFileSync(join(ROOT, rel), 'utf8');
}

export interface ShellBrandProbe {
  name: string;
  ok: boolean;
  detail?: string;
}

export function runShellBrandIntegrityProbes(): ShellBrandProbe[] {
  const shellBrand = read('src/components/shell/ShellBrand/ShellBrand.tsx');
  const shellBrandCss = read('src/components/shell/ShellBrand/ShellBrand.module.css');
  const responsiveShell = read('src/components/layout/ResponsiveShell/ResponsiveShell.tsx');
  const responsiveCss = read('src/components/layout/ResponsiveShell/ResponsiveShell.module.css');

  return [
    {
      name: 'wordmark-svg-import',
      ok: shellBrand.includes("from '../../../assets/icons/brand/wordmark.svg'"),
    },
    {
      name: 'wordmark-dom-marker',
      ok: shellBrand.includes('data-shell-brand-wordmark'),
    },
    {
      name: 'shield-dom-marker',
      ok: shellBrand.includes('data-shell-brand-shield'),
    },
    {
      name: 'no-interim-text-wordmark',
      ok: !shellBrand.includes('>Skeldir<') && !shellBrand.includes('className={styles.wordmark}'),
    },
    {
      name: 'shield-dominant-lockup-size',
      ok:
        shellBrand.includes('width={SHIELD_SIZE}') &&
        shellBrandCss.includes('brand-shield-size') &&
        shellBrandCss.includes('brand-wordmark-height') &&
        shellBrandCss.includes('brand-lockup-gap') &&
        shellBrandCss.includes('brand-lockup-pull') &&
        shellBrandCss.includes('brand-lockup-wordmark-offset-y'),
    },
    {
      name: 'wordmark-subordinate-to-shield',
      ok:
        shellBrand.includes('height={WORDMARK_HEIGHT}') &&
        shellBrandCss.includes('brand-wordmark-max-width'),
    },
    {
      name: 'sidebar-column-full-height',
      ok: responsiveCss.includes('.sidebar') && responsiveCss.includes('min-height: 100vh'),
    },
    {
      name: 'header-in-main-column',
      ok:
        responsiveShell.includes('data-shell-main-column') &&
        responsiveShell.includes('data-shell-header-column') &&
        responsiveShell.includes('data-shell-sidebar-column'),
    },
    {
      name: 'header-not-above-sidebar',
      ok:
        responsiveShell.indexOf('data-shell-sidebar-column') < responsiveShell.indexOf('data-shell-main-column') &&
        responsiveShell.includes('data-shell-header-column'),
    },
    {
      name: 'main-content-centered',
      ok:
        responsiveCss.includes('.main > *') &&
        responsiveCss.includes('align-items: center') &&
        responsiveCss.includes('max-width: var(--sk-dimension-content-max-width)'),
    },
    {
      name: 'shell-header-content-centered',
      ok:
        responsiveCss.includes('.header > *') &&
        responsiveCss.includes('align-items: center') &&
        responsiveCss.includes('max-width: var(--sk-dimension-content-max-width)'),
    },
    {
      name: 'main-padding-compact',
      ok: responsiveCss.includes('--sk-dimension-main-padding-inline'),
    },
  ];
}

export function runShellBrandSabotageProbes(): Array<{ name: string; triggered: boolean }> {
  const shellBrand = read('src/components/shell/ShellBrand/ShellBrand.tsx');
  const responsiveShell = read('src/components/layout/ResponsiveShell/ResponsiveShell.tsx');

  return [
    {
      name: 'text-wordmark-restored',
      triggered: shellBrand.includes('>Skeldir<') && !shellBrand.includes('wordmark.svg'),
    },
    {
      name: 'wordmark-marker-removed',
      triggered: !shellBrand.includes('data-shell-brand-wordmark'),
    },
    {
      name: 'full-width-header-above-sidebar',
      triggered:
        responsiveShell.includes('{header ?') &&
        responsiveShell.indexOf('{header ?') < responsiveShell.indexOf('{sidebar ?'),
    },
  ];
}
