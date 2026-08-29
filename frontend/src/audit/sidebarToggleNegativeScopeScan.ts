import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(process.cwd());

function read(rel: string): string {
  return readFileSync(join(ROOT, rel), 'utf8');
}

export interface SidebarToggleProbe {
  name: string;
  ok: boolean;
  detail?: string;
}

export function runSidebarToggleIntegrityProbes(): SidebarToggleProbe[] {
  const toggle = read('src/components/shell/SidebarToggle/SidebarToggle.tsx');
  const toggleCss = read('src/components/shell/SidebarToggle/SidebarToggle.module.css');

  return [
    {
      name: 'open-navbar-svg-import',
      ok: toggle.includes("from '../../../assets/icons/nav/open_navbar.svg'"),
    },
    {
      name: 'close-navbar-svg-import',
      ok: toggle.includes("from '../../../assets/icons/nav/close_navbar.svg'"),
    },
    {
      name: 'no-inline-hand-drawn-icons',
      ok: !toggle.includes('function IconSidebar') && !toggle.includes('<svg width={18}'),
    },
    {
      name: 'icon-intent-dom-marker',
      ok: toggle.includes('data-sidebar-toggle-icon'),
    },
    {
      name: 'collapsed-shows-open-icon',
      ok: toggle.includes('collapsed ? openNavbarIcon : closeNavbarIcon'),
    },
    {
      name: 'directional-hover-physics',
      ok:
        toggleCss.includes("[data-sidebar-toggle-state='collapsed']:hover") &&
        toggleCss.includes("[data-sidebar-toggle-state='expanded']:hover") &&
        toggleCss.includes('translateX(0.5px)') &&
        toggleCss.includes('translateX(-0.5px)'),
    },
    {
      name: 'reduced-motion-respects-transform',
      ok: toggleCss.includes('prefers-reduced-motion') && toggleCss.includes('transform: none'),
    },
  ];
}

export function runSidebarToggleSabotageProbes(): Array<{ name: string; triggered: boolean }> {
  const toggle = read('src/components/shell/SidebarToggle/SidebarToggle.tsx');

  return [
    {
      name: 'inline-svg-regression',
      triggered: toggle.includes('function IconSidebar'),
    },
    {
      name: 'wrong-icon-mapping',
      triggered: toggle.includes('collapsed ? closeNavbarIcon : openNavbarIcon'),
    },
  ];
}
