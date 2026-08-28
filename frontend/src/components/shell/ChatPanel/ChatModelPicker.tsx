import { useEffect, useId, useRef, useState } from 'react';
import { IconChevronDown } from '../../icons/StatusIcons';
import { SHELL_COPY } from '../../../shell/copy';
import {
  CHAT_SPECIFIC_MODEL_OPTIONS,
  type ChatSpecificModelId,
} from '../../../shell/chatUi';
import styles from './ChatModelPicker.module.css';

export interface ChatModelPickerProps {
  modelId: ChatSpecificModelId;
  recommendedEnabled: boolean;
  disabled?: boolean;
  onRecommendedChange: (enabled: boolean) => void;
  onModelChange: (modelId: ChatSpecificModelId) => void;
}

export function ChatModelPicker({
  modelId,
  recommendedEnabled,
  disabled = false,
  onRecommendedChange,
  onModelChange,
}: ChatModelPickerProps) {
  const listboxId = useId();
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  const selectedOption =
    CHAT_SPECIFIC_MODEL_OPTIONS.find((option) => option.id === modelId) ??
    CHAT_SPECIFIC_MODEL_OPTIONS[0];
  const triggerLabel = recommendedEnabled ? SHELL_COPY.chatRecommendedLabel : selectedOption.label;

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  const handleSelect = (nextModelId: ChatSpecificModelId) => {
    onModelChange(nextModelId);
    setOpen(false);
  };

  const handleRecommendedToggle = () => {
    onRecommendedChange(!recommendedEnabled);
  };

  return (
    <div className={styles.root} ref={rootRef} data-chat-model-picker>
      <button
        type="button"
        className={styles.trigger}
        disabled={disabled}
        aria-label={SHELL_COPY.chatModelLabel}
        aria-haspopup={recommendedEnabled ? 'dialog' : 'listbox'}
        aria-expanded={open}
        aria-controls={open ? (recommendedEnabled ? menuId : listboxId) : undefined}
        onClick={() => setOpen((value) => !value)}
      >
        <span className={styles.triggerLabel}>{triggerLabel}</span>
        <IconChevronDown className={styles.triggerIcon} title="" />
      </button>

      {open ? (
        <div
          id={menuId}
          className={[
            styles.menu,
            recommendedEnabled ? styles.menuRecommendedOnly : '',
          ].filter(Boolean).join(' ')}
          data-chat-model-menu
        >
          <div className={styles.recommendedRow}>
            <span className={styles.recommendedLabel}>{SHELL_COPY.chatRecommendedLabel}</span>
            <button
              type="button"
              role="switch"
              className={[styles.switch, recommendedEnabled ? styles.switchOn : ''].join(' ')}
              aria-label={SHELL_COPY.chatRecommendedToggle}
              aria-checked={recommendedEnabled}
              disabled={disabled}
              onClick={handleRecommendedToggle}
            >
              <span className={styles.switchThumb} aria-hidden="true" />
            </button>
          </div>

          {recommendedEnabled ? (
            <p className={styles.recommendedNote}>{SHELL_COPY.chatRecommendedDescription}</p>
          ) : (
            <ul
              id={listboxId}
              role="listbox"
              className={styles.optionList}
              aria-label={SHELL_COPY.chatModelLabel}
            >
              {CHAT_SPECIFIC_MODEL_OPTIONS.map((option) => {
                const selected = option.id === modelId;
                return (
                  <li key={option.id} role="presentation">
                    <button
                      type="button"
                      role="option"
                      aria-selected={selected}
                      disabled={disabled}
                      className={[styles.option, selected ? styles.optionSelected : ''].filter(Boolean).join(' ')}
                      onClick={() => handleSelect(option.id)}
                    >
                      {option.label}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
