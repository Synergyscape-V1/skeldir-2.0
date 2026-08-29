import { SHELL_COPY } from '../../../shell/copy';
import type { ChatMessage } from '../../../shell/chatUi';
import styles from './ChatMessageList.module.css';

export interface ChatMessageListProps {
  messages: ChatMessage[];
  isTyping: boolean;
  onSuggestionSelect: (prompt: string) => void;
}

export function ChatMessageList({ messages, isTyping, onSuggestionSelect }: ChatMessageListProps) {
  if (messages.length === 0 && !isTyping) {
    return (
      <div className={styles.emptyState} data-chat-empty-state>
        <p className={styles.emptyTitle}>{SHELL_COPY.chatEmptyTitle}</p>
        <p className={styles.emptyDescription}>{SHELL_COPY.chatEmptyDescription}</p>
        <ul className={styles.suggestions} aria-label="Suggested prompts">
          {SHELL_COPY.chatSuggestions.map((prompt) => (
            <li key={prompt}>
              <button
                type="button"
                className={styles.suggestion}
                onClick={() => onSuggestionSelect(prompt)}
              >
                {prompt}
              </button>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <ol className={styles.list} aria-live="polite" data-chat-message-list>
      {messages.map((message) => (
        <li
          key={message.id}
          className={[styles.messageItem, styles[message.role]].join(' ')}
          data-chat-message-role={message.role}
        >
          <div
            className={styles.bubble}
            aria-label={message.role === 'user' ? 'Your message' : 'Assistant message'}
          >
            <p className={styles.content}>{message.content}</p>
          </div>
        </li>
      ))}
      {isTyping ? (
        <li className={[styles.messageItem, styles.assistant, styles.typingItem].join(' ')}>
          <div
            className={[styles.bubble, styles.typingBubble].join(' ')}
            aria-live="polite"
            aria-label={SHELL_COPY.chatTyping}
          >
            <span className={styles.typingLabel}>{SHELL_COPY.chatTyping}</span>
            <span className={styles.typingDots} aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
          </div>
        </li>
      ) : null}
    </ol>
  );
}
