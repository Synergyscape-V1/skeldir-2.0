import { SHELL_COPY } from '../../../shell/copy';
import { getChatSessionTabPreview, type ChatSession } from '../../../shell/chatUi';
import { ChatToggle } from '../ChatToggle/ChatToggle';
import historyIcon from '../../../assets/icons/nav/history.svg';
import shared from '../../../styles/shared.module.css';
import { useChatTablistScroll } from './useChatTablistScroll';
import styles from './ChatSessionTabs.module.css';

export interface ChatSessionTabsProps {
  sessions: ChatSession[];
  activeSessionId: string;
  chatOpen: boolean;
  onSelect: (sessionId: string) => void;
  onClose: (sessionId: string) => void;
  onAdd: () => void;
  onChatToggle: () => void;
  onShowHistory?: () => void;
}

export function ChatSessionTabs({
  sessions,
  activeSessionId,
  chatOpen,
  onSelect,
  onClose,
  onAdd,
  onChatToggle,
  onShowHistory,
}: ChatSessionTabsProps) {
  const canClose = sessions.length > 1;
  const {
    tablistRef,
    scrollThumb,
    syncScrollThumb,
    handleThumbPointerDown,
    handleThumbPointerMove,
    handleThumbPointerUp,
    handleTrackPointerDown,
  } = useChatTablistScroll(sessions);

  return (
    <div className={styles.bar} data-chat-session-tabs>
      <div
        className={styles.tablistViewport}
        data-scrollable={scrollThumb.visible ? 'true' : undefined}
      >
        <div
          ref={tablistRef}
          role="tablist"
          aria-label={SHELL_COPY.chatTabsLabel}
          className={styles.tablist}
          onScroll={syncScrollThumb}
        >
          {sessions.map((session, index) => {
            const selected = session.id === activeSessionId;
            const tabLabel = getChatSessionTabPreview(session);
            return (
              <div
                key={session.id}
                className={[styles.tabWrap, selected ? styles.tabWrapActive : ''].filter(Boolean).join(' ')}
              >
                <button
                  type="button"
                  role="tab"
                  id={`chat-tab-${session.id}`}
                  aria-selected={selected}
                  aria-controls={`chat-panel-${session.id}`}
                  aria-label={
                    sessions.length > 1 ? `${tabLabel}, conversation ${index + 1}` : tabLabel
                  }
                  tabIndex={selected ? 0 : -1}
                  className={styles.tab}
                  onClick={() => onSelect(session.id)}
                >
                  <span className={styles.tabLabel}>{tabLabel}</span>
                </button>
                {canClose ? (
                  <button
                    type="button"
                    className={styles.tabClose}
                    aria-label={SHELL_COPY.chatCloseSession(tabLabel)}
                    onClick={(event) => {
                      event.stopPropagation();
                      onClose(session.id);
                    }}
                  >
                    ×
                  </button>
                ) : null}
              </div>
            );
          })}
        </div>
        {scrollThumb.visible ? (
          <div
            className={styles.scrollbarTrack}
            aria-hidden
            data-chat-tablist-scrollbar
            onPointerDown={handleTrackPointerDown}
          >
            <div
              className={styles.scrollbarThumb}
              style={{
                width: `${scrollThumb.width}px`,
                transform: `translateX(${scrollThumb.left}px)`,
              }}
              onPointerDown={handleThumbPointerDown}
              onPointerMove={handleThumbPointerMove}
              onPointerUp={handleThumbPointerUp}
              onPointerCancel={handleThumbPointerUp}
            />
          </div>
        ) : null}
      </div>
      <div className={styles.barActions}>
        <button
          type="button"
          className={[styles.barAction, shared.focusVisible].join(' ')}
          aria-label={SHELL_COPY.chatNewSession}
          onClick={onAdd}
        >
          +
        </button>
        <button
          type="button"
          className={[styles.barAction, shared.focusVisible].join(' ')}
          aria-label={SHELL_COPY.chatHistoryLabel}
          data-chat-history-toggle
          onClick={() => onShowHistory?.()}
        >
          <img
            src={historyIcon}
            alt=""
            className={styles.barActionIcon}
            width={16}
            height={16}
            draggable={false}
          />
        </button>
        <ChatToggle open={chatOpen} onToggle={onChatToggle} />
      </div>
    </div>
  );
}
