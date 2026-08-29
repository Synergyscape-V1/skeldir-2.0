import type { ExceptionCategory, ExceptionCategoryCounts } from '../../../ledger/types';
import { EXCEPTION_CATEGORY_LABELS, EXCEPTIONS_PAGE_COPY } from '../../../exceptions/copy';
import { EXCEPTION_CATEGORY_ORDER } from '../../../exceptions/exceptionsFilterConfig';
import { filterMarketerVisibleExceptionCategories } from '../../../benchmarks/benchmarkMarketingVisibility';
import filterChip from '../../../styles/filterChip.module.css';
import shared from '../../../styles/shared.module.css';
import styles from './ExceptionsCategoryTabs.module.css';

export interface ExceptionsCategoryTabsProps {
  activeCategory: ExceptionCategory | 'all';
  counts: ExceptionCategoryCounts;
  onChange: (category: ExceptionCategory | 'all') => void;
  disabled?: boolean;
}

export function ExceptionsCategoryTabs({
  activeCategory,
  counts,
  onChange,
  disabled = false,
}: ExceptionsCategoryTabsProps) {
  const tabs: Array<{ key: ExceptionCategory | 'all'; label: string; count: number }> = [
    { key: 'all', label: EXCEPTIONS_PAGE_COPY.categoryTabs.all, count: counts.all },
    ...filterMarketerVisibleExceptionCategories(EXCEPTION_CATEGORY_ORDER).map((category) => ({
      key: category,
      label: EXCEPTION_CATEGORY_LABELS[category],
      count: counts[category],
    })),
  ];

  return (
    <div
      className={styles.bar}
      role="tablist"
      aria-label={EXCEPTIONS_PAGE_COPY.categoryTabs.ariaLabel}
      data-exceptions-category-tabs
    >
      {tabs.map((tab) => {
        const active = activeCategory === tab.key;
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={active}
            className={[
              active ? filterChip.chip : filterChip.chipInactive,
              styles.tab,
              shared.focusVisible,
            ]
              .filter(Boolean)
              .join(' ')}
            disabled={disabled}
            data-exception-category-tab={tab.key}
            onClick={() => onChange(tab.key)}
          >
            <span>{tab.label}</span>
            <span className={filterChip.count}>{tab.count}</span>
          </button>
        );
      })}
    </div>
  );
}
