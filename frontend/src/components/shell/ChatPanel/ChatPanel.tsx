import { useCallback, useEffect, useRef } from 'react';
import shared from '../../../styles/shared.module.css';
import { SHELL_COPY } from '../../../shell/copy';
import { ChatComposer } from './ChatComposer';
import { ChatMessageList } from './ChatMessageList';
import { ChatSessionTabs } from './ChatSessionTabs';
import { useChatSessions } from './useChatSessions';
import styles from './ChatPanel.module.css';

export interface ChatPanelProps {
  open: boolean;
  onChatToggle: () => void;
}

export function ChatPanel({ open, onChatToggle }: ChatPanelProps) {
  const {
    sessions,
    activeSession,
    activeSessionId,
    setActiveSessionId,
    addSession,
    closeSession,
    sendMessage,
    setDraft,
    setRecommendedEnabled,
    setModelId,
  } = useChatSessions();
  const messageAreaRef = useRef<HTMLDivElement>(null);

  const scrollToLatest = useCallback(() => {
    const area = messageAreaRef.current;
    if (!area) return;
    area.scrollTop = area.scrollHeight;
  }, []);

  useEffect(() => {
    if (open && activeSession) {
      scrollToLatest();
    }
  }, [open, activeSession, activeSession?.messages, activeSession?.isTyping, scrollToLatest]);

  const handleSuggestion = (prompt: string) => {
    setDraft(prompt);
  };

  if (!activeSession) {
    return null;
  }

  return (
    <section
      id="shell-chat-panel"
      className={styles.panel}
      data-shell-chat-panel
      data-chat-recommended-enabled={activeSession.recommendedEnabled ? 'true' : 'false'}
      aria-label={SHELL_COPY.chatPanelTitle}
      aria-hidden={open ? undefined : true}
    >
      <h2 className={shared.srOnly}>{SHELL_COPY.chatPanelTitle}</h2>

      <ChatSessionTabs
        sessions={sessions}
        activeSessionId={activeSessionId}
        chatOpen={open}
        onSelect={setActiveSessionId}
        onClose={closeSession}
        onAdd={addSession}
        onChatToggle={onChatToggle}
      />

      <div
        ref={messageAreaRef}
        id={`chat-panel-${activeSession.id}`}
        role="tabpanel"
        aria-labelledby={`chat-tab-${activeSession.id}`}
        className={styles.messageArea}
        data-chat-message-area
        data-chat-active-session={activeSession.id}
      >
        <ChatMessageList
          messages={activeSession.messages}
          isTyping={activeSession.isTyping}
          onSuggestionSelect={handleSuggestion}
        />
      </div>

      <ChatComposer
        draft={activeSession.draft}
        modelId={activeSession.modelId}
        recommendedEnabled={activeSession.recommendedEnabled}
        disabled={activeSession.isTyping}
        onDraftChange={setDraft}
        onRecommendedChange={setRecommendedEnabled}
        onModelChange={setModelId}
        onSend={() => sendMessage(activeSession.draft)}
      />
    </section>
  );
}
