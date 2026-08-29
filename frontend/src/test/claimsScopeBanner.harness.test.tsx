import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ClaimsScopeBanner } from '../components/claims/ClaimsScopeBanner/ClaimsScopeBanner';

/**
 * CRHAID 1 — CDO Audit 2 remediation harness.
 * Verifies the GlobalScopeIndicator (ClaimsScopeBanner) eliminates the
 * deep-link "State Amnesia" epistemic trap by broadcasting active scope
 * ambiently before the table renders.
 *
 * The active-filter chips (label/brand mark + per-filter × removal) are
 * consolidated INTO this banner from the filter panel, so the panel no longer
 * duplicates the chip row. The ambient "Clear all filters" CTA is the one-glance
 * reset to global truth.
 */

describe('CRHAID 1 — ClaimsScopeBanner (Audit 2 GlobalScopeIndicator)', () => {
  describe('State 1: Unfiltered (Global Truth)', () => {
    it('renders ambient unfiltered banner with no chips', () => {
      render(<ClaimsScopeBanner activeFilters={[]} onRemoveFilter={() => {}} onClearAll={() => {}} />);

      expect(screen.getByText('Viewing all revenue claims.')).toBeInTheDocument();
      expect(screen.queryByRole('list')).not.toBeInTheDocument();
      expect(screen.queryByText('Clear all filters')).not.toBeInTheDocument();
    });

    it('exposes data-scope-state=unfiltered for harness scanning', () => {
      const { container } = render(
        <ClaimsScopeBanner activeFilters={[]} onRemoveFilter={() => {}} onClearAll={() => {}} />,
      );
      const banner = container.querySelector('[data-claims-scope-banner]');
      expect(banner?.getAttribute('data-scope-state')).toBe('unfiltered');
    });
  });

  describe('State 2: Filtered (Restricted Scope) — Deep-Link Hydration', () => {
    it('renders summary + chips + clear-all when filters active (deep-link entry)', () => {
      const filters = [
        { key: 'claimSource', label: 'Meta Ads' },
        { key: 'discrepancyClass', label: 'Flagged' },
      ];

      render(
        <ClaimsScopeBanner
          activeFilters={filters}
          onRemoveFilter={() => {}}
          onClearAll={() => {}}
          totalCount={42}
        />,
      );

      // Scope is announced before the table — ambient, not buried in inputs.
      expect(screen.getByText('Viewing 42 claims matching filters:')).toBeInTheDocument();
      expect(screen.getByText('Meta Ads')).toBeInTheDocument();
      expect(screen.getByText('Flagged')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Clear all active filters' })).toBeInTheDocument();
    });

    it('exposes data-scope-state=filtered on first paint (no unfiltered flash)', () => {
      const { container } = render(
        <ClaimsScopeBanner
          activeFilters={[{ key: 'claimSource', label: 'Meta Ads' }]}
          onRemoveFilter={() => {}}
          onClearAll={() => {}}
        />,
      );
      const banner = container.querySelector('[data-claims-scope-banner]');
      expect(banner?.getAttribute('data-scope-state')).toBe('filtered');
      expect(container.querySelector('[data-scope-state="unfiltered"]')).toBeNull();
    });

    it('renders a removable chip per active filter, including a × button', () => {
      const filters = [
        { key: 'claimSource', label: 'Meta Ads' },
        { key: 'verificationStatus', label: 'Verified' },
        { key: 'dateRange', label: 'Last 30 days' },
      ];

      render(
        <ClaimsScopeBanner
          activeFilters={filters}
          onRemoveFilter={() => {}}
          onClearAll={() => {}}
        />,
      );

      expect(screen.getByText('Meta Ads')).toBeInTheDocument();
      expect(screen.getByText('Verified')).toBeInTheDocument();
      expect(screen.getByText('Last 30 days')).toBeInTheDocument();

      // Each chip now exposes a per-filter × remove button (consolidated from panel).
      expect(screen.getByRole('button', { name: 'Remove Meta Ads filter' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Remove Verified filter' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Remove Last 30 days filter' })).toBeInTheDocument();
    });

    it('renders only the brand mark (no text label) for vendor chips like Shopify/Stripe', () => {
      const filters = [
        { key: 'commerceSource', label: 'Shopify', logoKey: 'shopify' },
        { key: 'commerceSource', label: 'Stripe', logoKey: 'stripe' },
        { key: 'verificationStatus', label: 'Verified' },
      ];

      const { container } = render(
        <ClaimsScopeBanner
          activeFilters={filters}
          onRemoveFilter={() => {}}
          onClearAll={() => {}}
        />,
      );

      const shopifyMark = container.querySelector('[data-channel-logo="shopify"]');
      const stripeMark = container.querySelector('[data-channel-logo="stripe"]');
      expect(shopifyMark).toBeInTheDocument();
      expect(stripeMark).toBeInTheDocument();
      expect(shopifyMark?.tagName.toLowerCase()).toBe('img');

      // Vendor chips show the logo only — the text label is suppressed ...
      expect(screen.queryByText('Shopify')).not.toBeInTheDocument();
      expect(screen.queryByText('Stripe')).not.toBeInTheDocument();
      // ... but the accessible name is preserved via the chip + × button aria-labels.
      expect(screen.getByRole('button', { name: 'Remove Stripe filter' })).toBeInTheDocument();

      // Non-vendor filter still renders its text label
      expect(screen.getByText('Verified')).toBeInTheDocument();
      expect(container.querySelector('[data-channel-logo="verified"]')).toBeNull();
    });
  });

  describe('Negative controls', () => {
    it('per-filter × fires onRemoveFilter with the correct key', () => {
      const onRemoveFilter = vi.fn();
      const filters = [{ key: 'commerceSource', label: 'Stripe', logoKey: 'stripe' }];

      render(
        <ClaimsScopeBanner activeFilters={filters} onRemoveFilter={onRemoveFilter} onClearAll={() => {}} />,
      );

      screen.getByRole('button', { name: 'Remove Stripe filter' }).click();
      expect(onRemoveFilter).toHaveBeenCalledWith('commerceSource');
    });

    it('clear-all fires onClearAll (single ambient reset to global truth)', () => {
      const onClearAll = vi.fn();
      const filters = [{ key: 'claimSource', label: 'Meta Ads' }];

      render(
        <ClaimsScopeBanner activeFilters={filters} onRemoveFilter={() => {}} onClearAll={onClearAll} />,
      );

      screen.getByRole('button', { name: 'Clear all active filters' }).click();
      expect(onClearAll).toHaveBeenCalledTimes(1);
    });
  });

  describe('State: Permission errors', () => {
    it('marks a denied filter chip with error styling + tooltip when permission missing', () => {
      const filters = [{ key: 'policyAuthority', label: 'Pending Certification' }];

      const { container } = render(
        <ClaimsScopeBanner
          activeFilters={filters}
          onRemoveFilter={() => {}}
          onClearAll={() => {}}
          permissionErrors={['policyAuthority']}
        />,
      );

      const deniedChip = container.querySelector('[data-permission-error="true"]');
      expect(deniedChip).toBeInTheDocument();
      expect(screen.getByText('Insufficient permissions for this filter.')).toBeInTheDocument();
    });
  });

  describe('Meta-negative control — harness is non-vacuous', () => {
    it('filtered data renders filtered copy, never the unfiltered global-truth copy', () => {
      const { container } = render(
        <ClaimsScopeBanner
          activeFilters={[{ key: 'claimSource', label: 'Meta Ads' }]}
          onRemoveFilter={() => {}}
          onClearAll={() => {}}
        />,
      );
      const summary = container.querySelector('[data-claims-scope-banner]');
      expect(summary?.textContent).not.toMatch(/Viewing all revenue claims\./);
      expect(summary?.getAttribute('data-scope-state')).toBe('filtered');
    });
  });

  describe('Filter chip DNA — ExceptionsCategoryTabs / Benchmarks parity', () => {
    it('composes shared filterChip chip + chips primitives', () => {
      const bannerCss = readFileSync(
        join(process.cwd(), 'src', 'components', 'claims', 'ClaimsScopeBanner', 'ClaimsScopeBanner.module.css'),
        'utf8',
      );
      const channelsCss = readFileSync(
        join(
          process.cwd(),
          'src',
          'components',
          'channels',
          'ChannelsOverviewFilters',
          'ChannelsOverviewFilters.module.css',
        ),
        'utf8',
      );
      const categoryTabsCss = readFileSync(
        join(
          process.cwd(),
          'src',
          'components',
          'exceptions',
          'ExceptionsCategoryTabs',
          'ExceptionsCategoryTabs.module.css',
        ),
        'utf8',
      );

      expect(categoryTabsCss).toMatch(/composes:\s*chips from/);
      expect(bannerCss).toMatch(/\.chip\s*\{[\s\S]*composes:\s*chip from/);
      expect(bannerCss).toMatch(/\.chips\s*\{[\s\S]*composes:\s*chips from/);
      expect(bannerCss).toMatch(/\.chipRemove\s*\{[\s\S]*composes:\s*chipRemove from/);
      expect(channelsCss).toMatch(/\.chip\s*\{[\s\S]*composes:\s*chip from/);
      expect(channelsCss).toMatch(/\.chips\s*\{[\s\S]*composes:\s*chips from/);
      expect(channelsCss).toMatch(/\.chipRemove\s*\{[\s\S]*composes:\s*chipRemove from/);
      expect(bannerCss).not.toMatch(/border-radius:\s*var\(--sk-radius-pill\)/);
      expect(channelsCss).not.toMatch(/border-radius:\s*var\(--sk-radius-pill\)/);
    });
  });
});
