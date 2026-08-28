import { useCallback, useRef, type KeyboardEvent, type ReactNode } from 'react';
import { ERROR_COPY } from '../../../lib/copy';
import shared from '../../../styles/shared.module.css';
import styles from './Tabs.module.css';

export interface TabItem {
  id: string;
  label: string;
  panel: ReactNode;
  disabled?: boolean;
}

export interface TabsProps {
  items: TabItem[];
  activeId?: string;
  onChange?: (id: string) => void;
  unknownType?: boolean;
}

export function Tabs({ items, activeId, onChange, unknownType }: TabsProps) {
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  if (unknownType) {
    return (
      <div className={shared.errorState} role="alert">
        {ERROR_COPY.configurationError}
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className={shared.errorState} role="alert">
        {ERROR_COPY.missingRequiredProp('items')}
      </div>
    );
  }

  const resolvedActive = activeId && items.some((i) => i.id === activeId) ? activeId : items[0].id;
  const activeIndex = items.findIndex((i) => i.id === resolvedActive);

  const focusTab = (index: number) => {
    tabRefs.current[index]?.focus();
  };

  const onKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key === 'ArrowRight') {
        event.preventDefault();
        const next = (activeIndex + 1) % items.length;
        onChange?.(items[next].id);
        focusTab(next);
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault();
        const prev = (activeIndex - 1 + items.length) % items.length;
        onChange?.(items[prev].id);
        focusTab(prev);
      } else if (event.key === 'Home') {
        event.preventDefault();
        onChange?.(items[0].id);
        focusTab(0);
      } else if (event.key === 'End') {
        event.preventDefault();
        onChange?.(items[items.length - 1].id);
        focusTab(items.length - 1);
      }
    },
    [activeIndex, items, onChange],
  );

  const activePanel = items.find((i) => i.id === resolvedActive);

  return (
    <div className={styles.tabs} onKeyDown={onKeyDown}>
      <div role="tablist" aria-label="Tabs" className={styles.tablist}>
        {items.map((item, index) => (
          <button
            key={item.id}
            ref={(el) => {
              tabRefs.current[index] = el;
            }}
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-selected={item.id === resolvedActive}
            aria-controls={`panel-${item.id}`}
            tabIndex={item.id === resolvedActive ? 0 : -1}
            disabled={item.disabled}
            className={[styles.tab, shared.focusVisible].join(' ')}
            onClick={() => onChange?.(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {activePanel ? (
        <div
          role="tabpanel"
          id={`panel-${activePanel.id}`}
          aria-labelledby={`tab-${activePanel.id}`}
          className={styles.panel}
        >
          {activePanel.panel}
        </div>
      ) : (
        <div className={shared.errorState} role="alert">
          {ERROR_COPY.missingRequiredProp('active panel')}
        </div>
      )}
    </div>
  );
}
