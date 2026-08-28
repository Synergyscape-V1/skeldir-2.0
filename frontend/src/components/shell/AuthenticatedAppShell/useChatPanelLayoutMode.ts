import { useEffect, useState } from 'react';
import {
  CHAT_PANEL_DEFAULT_WIDTH_PX,
  readChatPanelDefaultWidth,
  resolveChatPanelLayoutMode,
  type ChatPanelLayoutMode,
} from '../../../shell/chatPanelLayout';

export function useChatPanelLayoutMode(
  chatOpen: boolean,
  sidebarCollapsed: boolean,
  chatPanelWidth: number | null,
  shellElement: HTMLElement | null,
): ChatPanelLayoutMode {
  const [layoutMode, setLayoutMode] = useState<ChatPanelLayoutMode>(() =>
    resolveChatPanelLayoutMode(chatOpen, typeof window !== 'undefined' ? window.innerWidth : 1280, {
      sidebarCollapsed,
      chatPanelWidthPx:
        chatPanelWidth ?? readChatPanelDefaultWidth(shellElement) ?? CHAT_PANEL_DEFAULT_WIDTH_PX,
    }),
  );

  useEffect(() => {
    const update = () => {
      setLayoutMode(
        resolveChatPanelLayoutMode(chatOpen, window.innerWidth, {
          sidebarCollapsed,
          chatPanelWidthPx:
            chatPanelWidth ?? readChatPanelDefaultWidth(shellElement) ?? CHAT_PANEL_DEFAULT_WIDTH_PX,
        }),
      );
    };

    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, [chatOpen, sidebarCollapsed, chatPanelWidth, shellElement]);

  return layoutMode;
}
