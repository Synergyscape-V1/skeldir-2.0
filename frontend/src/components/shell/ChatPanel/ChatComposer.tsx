import { type KeyboardEvent } from 'react';
import { IconArrowUp } from '../../icons/StatusIcons';
import { SHELL_COPY } from '../../../shell/copy';
import type { ChatSpecificModelId } from '../../../shell/chatUi';
import { ChatModelPicker } from './ChatModelPicker';
import styles from './ChatComposer.module.css';

export interface ChatComposerProps {
  draft: string;
  modelId: ChatSpecificModelId;
  recommendedEnabled: boolean;
  disabled?: boolean;
  onDraftChange: (value: string) => void;
  onRecommendedChange: (enabled: boolean) => void;
  onModelChange: (modelId: ChatSpecificModelId) => void;
  onSend: () => void;
}

export function ChatComposer({
  draft,
  modelId,
  recommendedEnabled,
  disabled = false,
  onDraftChange,
  onRecommendedChange,
  onModelChange,
  onSend,
}: ChatComposerProps) {
  const canSend = draft.trim().length > 0 && !disabled;

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      if (canSend) onSend();
    }
  };

  return (
    <footer className={styles.footer} data-chat-composer>
      <div className={styles.composer}>
        <div className={styles.composerBody}>
          <div className={styles.inputRow}>
            <label className={styles.inputField}>
              <span className={styles.visuallyHidden}>{SHELL_COPY.chatComposerLabel}</span>
              <input
                type="text"
                className={styles.input}
                value={draft}
                placeholder={SHELL_COPY.chatComposerPlaceholder}
                aria-label={SHELL_COPY.chatComposerLabel}
                disabled={disabled}
                onChange={(event) => onDraftChange(event.target.value)}
                onKeyDown={handleKeyDown}
              />
            </label>
          </div>
          <div className={styles.modelPickerRow}>
            <ChatModelPicker
              modelId={modelId}
              recommendedEnabled={recommendedEnabled}
              disabled={disabled}
              onRecommendedChange={onRecommendedChange}
              onModelChange={onModelChange}
            />
          </div>
        </div>
        <button
          type="button"
          className={[
            styles.sendButton,
            canSend ? styles.sendButtonActive : styles.sendButtonIdle,
          ].join(' ')}
          disabled={!canSend}
          aria-label={SHELL_COPY.chatSend}
          onClick={onSend}
        >
          <IconArrowUp title="" />
        </button>
      </div>
    </footer>
  );
}
