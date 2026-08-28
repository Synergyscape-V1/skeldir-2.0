import { useCallback, useEffect, useRef, type PointerEvent as ReactPointerEvent } from 'react';
import { CHAT_PANEL_RESIZE_CURSOR, widthFromResizePointer } from '../../../shell/chatPanelLayout';

export interface UseChatPanelResizeOptions {
  enabled: boolean;
  onWidthChange: (width: number) => void;
}

function applyResizeCursor(active: boolean) {
  document.body.style.cursor = active ? CHAT_PANEL_RESIZE_CURSOR : '';
  document.body.style.userSelect = active ? 'none' : '';
}

export function useChatPanelResize({ enabled, onWidthChange }: UseChatPanelResizeOptions) {
  const draggingRef = useRef(false);
  const pointerIdRef = useRef<number | null>(null);
  const handleRef = useRef<HTMLButtonElement | null>(null);

  const endResize = useCallback((pointerId: number | null = pointerIdRef.current) => {
    if (!draggingRef.current) return;

    const handle = handleRef.current;
    draggingRef.current = false;
    pointerIdRef.current = null;
    handleRef.current = null;
    applyResizeCursor(false);

    if (handle && pointerId !== null && handle.hasPointerCapture(pointerId)) {
      handle.releasePointerCapture(pointerId);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;

    const handlePointerMove = (event: PointerEvent) => {
      if (!draggingRef.current || pointerIdRef.current !== event.pointerId) return;
      onWidthChange(widthFromResizePointer(event.clientX));
    };

    const handlePointerEnd = (event: PointerEvent) => {
      if (!draggingRef.current || pointerIdRef.current !== event.pointerId) return;
      endResize(event.pointerId);
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerEnd);
    window.addEventListener('pointercancel', handlePointerEnd);

    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerEnd);
      window.removeEventListener('pointercancel', handlePointerEnd);
      endResize();
    };
  }, [enabled, endResize, onWidthChange]);

  const startResize = useCallback(
    (event: ReactPointerEvent<HTMLButtonElement>) => {
      if (!enabled || event.button !== 0) return;

      event.preventDefault();
      draggingRef.current = true;
      pointerIdRef.current = event.pointerId;
      handleRef.current = event.currentTarget;
      event.currentTarget.setPointerCapture(event.pointerId);
      applyResizeCursor(true);
      onWidthChange(widthFromResizePointer(event.clientX));
    },
    [enabled, onWidthChange],
  );

  return { startResize };
}
