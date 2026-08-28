import { useCallback, useEffect, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';

export type ScrollThumb = {
  visible: boolean;
  width: number;
  left: number;
};

const HIDDEN_SCROLL_THUMB: ScrollThumb = { visible: false, width: 0, left: 0 };

function measureScrollThumb(element: HTMLElement): ScrollThumb {
  const { scrollWidth, clientWidth, scrollLeft } = element;
  if (scrollWidth <= clientWidth + 1) {
    return HIDDEN_SCROLL_THUMB;
  }

  const thumbWidth = Math.max((clientWidth / scrollWidth) * clientWidth, 24);
  const maxThumbLeft = clientWidth - thumbWidth;
  const scrollRatio = scrollLeft / (scrollWidth - clientWidth);

  return {
    visible: true,
    width: thumbWidth,
    left: scrollRatio * maxThumbLeft,
  };
}

function scrollMetrics(element: HTMLElement) {
  const { scrollWidth, clientWidth, scrollLeft } = element;
  const thumbWidth = Math.max((clientWidth / scrollWidth) * clientWidth, 24);
  const maxThumbLeft = clientWidth - thumbWidth;
  const maxScrollLeft = scrollWidth - clientWidth;

  return { thumbWidth, maxThumbLeft, maxScrollLeft, scrollLeft };
}

export function useChatTablistScroll(resyncKey: unknown) {
  const tablistRef = useRef<HTMLDivElement>(null);
  const dragStateRef = useRef<{
    pointerId: number;
    startX: number;
    startScrollLeft: number;
  } | null>(null);
  const [scrollThumb, setScrollThumb] = useState<ScrollThumb>(HIDDEN_SCROLL_THUMB);

  const syncScrollThumb = useCallback(() => {
    const element = tablistRef.current;
    if (!element) return;
    setScrollThumb(measureScrollThumb(element));
  }, []);

  useLayoutEffect(() => {
    syncScrollThumb();

    const element = tablistRef.current;
    if (!element) return;

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', syncScrollThumb);
      return () => window.removeEventListener('resize', syncScrollThumb);
    }

    const resizeObserver = new ResizeObserver(syncScrollThumb);
    resizeObserver.observe(element);
    return () => resizeObserver.disconnect();
  }, [resyncKey, syncScrollThumb]);

  useEffect(() => {
    const element = tablistRef.current;
    if (!element) return;

    const handleWheel = (event: WheelEvent) => {
      if (element.scrollWidth <= element.clientWidth) return;

      const horizontalIntent = Math.abs(event.deltaX) > Math.abs(event.deltaY);
      if (horizontalIntent) {
        return;
      }

      event.preventDefault();
      element.scrollLeft += event.deltaY;
    };

    element.addEventListener('wheel', handleWheel, { passive: false });
    return () => element.removeEventListener('wheel', handleWheel);
  }, [resyncKey]);

  const handleThumbPointerDown = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    const element = tablistRef.current;
    if (!element) return;

    event.preventDefault();
    dragStateRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startScrollLeft: element.scrollLeft,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }, []);

  const handleThumbPointerMove = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragStateRef.current;
    const element = tablistRef.current;
    if (!drag || !element || drag.pointerId !== event.pointerId) return;

    const { maxThumbLeft, maxScrollLeft } = scrollMetrics(element);
    if (maxThumbLeft <= 0 || maxScrollLeft <= 0) return;

    const deltaX = event.clientX - drag.startX;
    const scrollDelta = (deltaX / maxThumbLeft) * maxScrollLeft;
    element.scrollLeft = drag.startScrollLeft + scrollDelta;
  }, []);

  const handleThumbPointerUp = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (dragStateRef.current?.pointerId !== event.pointerId) return;

    dragStateRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }, []);

  const handleTrackPointerDown = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    const element = tablistRef.current;
    if (!element || event.target !== event.currentTarget) return;

    const rect = event.currentTarget.getBoundingClientRect();
    const clickX = event.clientX - rect.left;
    const { thumbWidth, maxThumbLeft, maxScrollLeft } = scrollMetrics(element);
    if (maxThumbLeft <= 0 || maxScrollLeft <= 0) return;

    const targetThumbLeft = Math.min(Math.max(clickX - thumbWidth / 2, 0), maxThumbLeft);
    element.scrollLeft = (targetThumbLeft / maxThumbLeft) * maxScrollLeft;
  }, []);

  return {
    tablistRef,
    scrollThumb,
    syncScrollThumb,
    handleThumbPointerDown,
    handleThumbPointerMove,
    handleThumbPointerUp,
    handleTrackPointerDown,
  };
}
