import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useRef, useState } from 'react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import { Drawer } from '../components/layout/Drawer/Drawer';
import { Modal } from '../components/layout/Modal/Modal';
import { Tabs } from '../components/layout/Tabs/Tabs';
import { EmptyState } from '../components/layout/EmptyState/EmptyState';
import { Toast } from '../components/layout/Toast/Toast';

function DrawerHarness() {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  return (
    <>
      <button ref={triggerRef} type="button" onClick={() => setOpen(true)}>
        Open drawer
      </button>
      <Drawer open={open} onClose={() => setOpen(false)} triggerRef={triggerRef} title="Audit artifact">
        Drawer content
      </Drawer>
    </>
  );
}

function ModalHarness({ type = 'standard' as 'standard' | 'destructive' }) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  return (
    <>
      <button ref={triggerRef} type="button" onClick={() => setOpen(true)}>
        Open modal
      </button>
      <Modal open={open} onClose={() => setOpen(false)} triggerRef={triggerRef} title="Confirm" type={type}>
        Modal body
      </Modal>
    </>
  );
}

describe('Level 0 — Interaction accessibility', () => {
  it('Drawer closes on Escape and returns focus to trigger', async () => {
    const user = userEvent.setup();
    render(<DrawerHarness />);
    const trigger = screen.getByRole('button', { name: 'Open drawer' });
    await user.click(trigger);
    expect(screen.getByRole('dialog', { name: 'Audit artifact' })).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it('Drawer shell shares Modal chrome DNA (header/body/backdrop contract)', () => {
    const drawerCss = readFileSync(resolve(process.cwd(), 'src/components/layout/Drawer/Drawer.module.css'), 'utf8');
    const modalCss = readFileSync(resolve(process.cwd(), 'src/components/layout/Modal/Modal.module.css'), 'utf8');
    expect(drawerCss).toMatch(/background:\s*rgba\(15,\s*23,\s*42,\s*0\.5\)/);
    expect(modalCss).toMatch(/background:\s*rgba\(15,\s*23,\s*42,\s*0\.5\)/);
    expect(drawerCss).toMatch(/box-shadow:\s*var\(--sk-elevation-modal\)/);
    expect(drawerCss).toMatch(/\.header\s*\{[\s\S]*padding:\s*var\(--sk-space-4\)\s+var\(--sk-space-6\)/);
    expect(modalCss).toMatch(/\.header\s*\{[\s\S]*padding:\s*var\(--sk-space-4\)\s+var\(--sk-space-6\)/);
    expect(drawerCss).toMatch(/\.body\s*\{[\s\S]*padding:\s*var\(--sk-space-6\)/);
    expect(modalCss).toMatch(/\.body\s*\{[\s\S]*padding:\s*var\(--sk-space-6\)/);
    expect(drawerCss).toMatch(/\.footer\s*\{/);
    expect(modalCss).toMatch(/\.footer\s*\{/);
  });

  it('Modal standard closes on Escape', async () => {
    const user = userEvent.setup();
    render(<ModalHarness />);
    await user.click(screen.getByRole('button', { name: 'Open modal' }));
    expect(screen.getByRole('dialog', { name: 'Confirm' })).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('Modal destructive does not close on Escape alone', async () => {
    const user = userEvent.setup();
    render(<ModalHarness type="destructive" />);
    await user.click(screen.getByRole('button', { name: 'Open modal' }));
    expect(screen.getByRole('dialog', { name: 'Confirm' })).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.getByRole('dialog', { name: 'Confirm' })).toBeInTheDocument();
  });

  it('Tabs support arrow-key navigation', async () => {
    const user = userEvent.setup();
    render(
      <Tabs
        items={[
          { id: 'a', label: 'Summary', panel: <div>Summary panel</div> },
          { id: 'b', label: 'Evidence', panel: <div>Evidence panel</div> },
        ]}
      />,
    );
    const summary = screen.getByRole('tab', { name: 'Summary' });
    summary.focus();
    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Evidence' })).toHaveFocus();
  });

  it('EmptyState filtered variant supports clear filters action', async () => {
    const onClear = vi.fn();
    const user = userEvent.setup();
    render(<EmptyState title="No matches" variant="filtered" onClearFilters={onClear} />);
    await user.click(screen.getByRole('button', { name: 'Clear filters' }));
    expect(onClear).toHaveBeenCalled();
  });

  it('Toast dismiss button is reachable and activatable', async () => {
    const onDismiss = vi.fn();
    const user = userEvent.setup();
    render(<Toast severity="error" open onDismiss={onDismiss} />);
    const dismiss = screen.getByRole('button', { name: 'Dismiss notification' });
    expect(dismiss).toBeInTheDocument();
    await user.click(dismiss);
    expect(onDismiss).toHaveBeenCalled();
  });

  it('Tabs unknown type renders configuration error', () => {
    render(<Tabs items={[{ id: 'a', label: 'A', panel: 'x' }]} unknownType />);
    expect(screen.getByRole('alert')).toHaveTextContent('Configuration error');
  });
});

describe('Level 0 — Target size token contract', () => {
  it('Toast dismiss meets minimum target height via CSS variable contract', () => {
    const css = readFileSync(resolve(process.cwd(), 'src/tokens/tokens.css'), 'utf8');
    expect(css).toContain('--sk-dimension-target-min: 44px');
  });
});
