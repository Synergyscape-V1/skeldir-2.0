import { describe, expect, it } from 'vitest';
import {
  CHAT_PANEL_DEFAULT_WIDTH_PX,
  MAIN_COLUMN_DOCK_MIN_WIDTH_PX,
  SHELL_SIDEBAR_WIDTH_PX,
  resolveChatPanelLayoutMode,
} from '../shell/chatPanelLayout';

describe('resolveChatPanelLayoutMode', () => {
  it('positive: laptop viewports overlay when main column would be too narrow', () => {
    expect(resolveChatPanelLayoutMode(true, 1024)).toBe('overlay');
    expect(resolveChatPanelLayoutMode(true, 1280)).toBe('overlay');
    expect(resolveChatPanelLayoutMode(true, 1440)).toBe('overlay');
    expect(resolveChatPanelLayoutMode(true, 1600)).toBe('overlay');
  });

  it('positive: wide viewports dock when main column retains supervisory width', () => {
    const dockViewport =
      MAIN_COLUMN_DOCK_MIN_WIDTH_PX + SHELL_SIDEBAR_WIDTH_PX + CHAT_PANEL_DEFAULT_WIDTH_PX;
    expect(resolveChatPanelLayoutMode(true, dockViewport)).toBe('docked');
    expect(resolveChatPanelLayoutMode(true, dockViewport + 200)).toBe('docked');
  });

  it('positive: collapsed sidebar still overlays when remaining width is insufficient', () => {
    expect(
      resolveChatPanelLayoutMode(true, 1440, {
        sidebarCollapsed: true,
        chatPanelWidthPx: CHAT_PANEL_DEFAULT_WIDTH_PX,
      }),
    ).toBe('overlay');
  });

  it('positive: widening chat panel can force overlay on marginal viewports', () => {
    const viewport = MAIN_COLUMN_DOCK_MIN_WIDTH_PX + SHELL_SIDEBAR_WIDTH_PX + 400;
    expect(
      resolveChatPanelLayoutMode(true, viewport, {
        chatPanelWidthPx: 400,
      }),
    ).toBe('docked');
    expect(
      resolveChatPanelLayoutMode(true, viewport, {
        chatPanelWidthPx: 560,
      }),
    ).toBe('overlay');
  });

  it('positive: mobile viewports use full-screen mobile layout', () => {
    expect(resolveChatPanelLayoutMode(true, 390)).toBe('mobile');
  });

  it('negative: closed chat always reports closed layout', () => {
    expect(resolveChatPanelLayoutMode(false, 1280)).toBe('closed');
    expect(resolveChatPanelLayoutMode(false, 1920)).toBe('closed');
  });
});
