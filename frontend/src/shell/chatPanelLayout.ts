export const CHAT_PANEL_MIN_WIDTH_PX = 320;
export const CHAT_PANEL_MAX_WIDTH_PX = 560;
export const CHAT_PANEL_DEFAULT_WIDTH_PX = 400;

/** Matches `--sk-dimension-sidebar-width` — conservative for dock eligibility. */
export const SHELL_SIDEBAR_WIDTH_PX = 264;

/**
 * Minimum unobstructed main-column width required before the chat panel may dock
 * beside content. Below this, chat overlays so supervisory grids/tables keep width.
 */
export const MAIN_COLUMN_DOCK_MIN_WIDTH_PX = 1200;

/** Horizontal resize cursor for the trailing chat panel's inner (west) edge. */
export const CHAT_PANEL_RESIZE_CURSOR = 'ew-resize';

export type ChatPanelLayoutMode = 'closed' | 'mobile' | 'overlay' | 'docked';

export interface ChatPanelLayoutContext {
  sidebarCollapsed?: boolean;
  chatPanelWidthPx?: number;
}

export function resolveChatPanelLayoutMode(
  chatOpen: boolean,
  viewportWidth: number,
  context: ChatPanelLayoutContext = {},
): ChatPanelLayoutMode {
  if (!chatOpen) return 'closed';
  if (viewportWidth <= 767) return 'mobile';

  const sidebarWidth = context.sidebarCollapsed ? 0 : SHELL_SIDEBAR_WIDTH_PX;
  const chatWidth = context.chatPanelWidthPx ?? CHAT_PANEL_DEFAULT_WIDTH_PX;
  const mainColumnWidth = viewportWidth - sidebarWidth - chatWidth;

  if (mainColumnWidth >= MAIN_COLUMN_DOCK_MIN_WIDTH_PX) return 'docked';
  return 'overlay';
}

export function clampChatPanelWidth(width: number, maxWidth = CHAT_PANEL_MAX_WIDTH_PX): number {
  return Math.min(maxWidth, Math.max(CHAT_PANEL_MIN_WIDTH_PX, Math.round(width)));
}

export function readChatPanelDefaultWidth(element: HTMLElement | null): number {
  if (!element || typeof window === 'undefined') {
    return CHAT_PANEL_DEFAULT_WIDTH_PX;
  }

  const tokenValue = getComputedStyle(element)
    .getPropertyValue('--sk-dimension-chat-panel-width')
    .trim();

  const parsed = Number.parseFloat(tokenValue);
  return Number.isNaN(parsed) ? CHAT_PANEL_DEFAULT_WIDTH_PX : parsed;
}

export function widthFromResizePointer(
  clientX: number,
  viewportWidth = typeof window !== 'undefined' ? window.innerWidth : 1280,
): number {
  const maxWidth = Math.min(CHAT_PANEL_MAX_WIDTH_PX, Math.floor(viewportWidth * 0.5));
  return clampChatPanelWidth(viewportWidth - clientX, maxWidth);
}
