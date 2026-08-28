import { useCallback, useEffect, useRef, useState } from 'react';
import {
  buildStubAssistantReply,
  createChatMessage,
  createChatSession,
  type ChatSession,
  type ChatSpecificModelId,
} from '../../../shell/chatUi';

export function useChatSessions() {
  const [sessions, setSessions] = useState<ChatSession[]>(() => [createChatSession()]);
  const [activeSessionId, setActiveSessionId] = useState(() => sessions[0]?.id ?? '');
  const typingTimeoutsRef = useRef<Map<string, number>>(new Map());

  const activeSession =
    sessions.find((session) => session.id === activeSessionId) ?? sessions[0] ?? null;

  useEffect(
    () => () => {
      typingTimeoutsRef.current.forEach((timeoutId) => window.clearTimeout(timeoutId));
      typingTimeoutsRef.current.clear();
    },
    [],
  );

  const updateSession = useCallback((sessionId: string, patch: Partial<ChatSession>) => {
    setSessions((current) =>
      current.map((session) => (session.id === sessionId ? { ...session, ...patch } : session)),
    );
  }, []);

  const addSession = useCallback(() => {
    setSessions((current) => {
      const nextSession = createChatSession();
      setActiveSessionId(nextSession.id);
      return [...current, nextSession];
    });
  }, []);

  const closeSession = useCallback(
    (sessionId: string) => {
      setSessions((current) => {
        if (current.length <= 1) return current;

        const timeoutId = typingTimeoutsRef.current.get(sessionId);
        if (timeoutId !== undefined) {
          window.clearTimeout(timeoutId);
          typingTimeoutsRef.current.delete(sessionId);
        }

        const closingIndex = current.findIndex((session) => session.id === sessionId);
        const nextSessions = current.filter((session) => session.id !== sessionId);

        if (activeSessionId === sessionId) {
          const nextIndex = Math.max(0, closingIndex - 1);
          setActiveSessionId(nextSessions[nextIndex]?.id ?? nextSessions[0].id);
        }

        return nextSessions;
      });
    },
    [activeSessionId],
  );

  const sendMessage = useCallback(
    (rawContent: string) => {
      if (!activeSession || activeSession.isTyping) return;

      const content = rawContent.trim();
      if (!content) return;

      const sessionId = activeSession.id;
      updateSession(sessionId, {
        messages: [...activeSession.messages, createChatMessage('user', content)],
        draft: '',
        isTyping: true,
      });

      const timeoutId = window.setTimeout(() => {
        setSessions((current) =>
          current.map((session) => {
            if (session.id !== sessionId) return session;
            return {
              ...session,
              messages: [
                ...session.messages,
                createChatMessage('assistant', buildStubAssistantReply(content)),
              ],
              isTyping: false,
            };
          }),
        );
        typingTimeoutsRef.current.delete(sessionId);
      }, 700);

      typingTimeoutsRef.current.set(sessionId, timeoutId);
    },
    [activeSession, updateSession],
  );

  const setDraft = useCallback(
    (draft: string) => {
      if (!activeSession) return;
      updateSession(activeSession.id, { draft });
    },
    [activeSession, updateSession],
  );

  const setRecommendedEnabled = useCallback(
    (recommendedEnabled: boolean) => {
      if (!activeSession) return;
      updateSession(activeSession.id, { recommendedEnabled });
    },
    [activeSession, updateSession],
  );

  const setModelId = useCallback(
    (modelId: ChatSpecificModelId) => {
      if (!activeSession) return;
      updateSession(activeSession.id, { modelId, recommendedEnabled: false });
    },
    [activeSession, updateSession],
  );

  return {
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
  };
}
