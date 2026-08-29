import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach, vi } from 'vitest';
import '../tokens/tokens.css';
import '../tokens/density.css';

export const clipboardWriteTextMock = vi.fn().mockResolvedValue(undefined);

beforeEach(() => {
  if (!('clipboard' in navigator) || !navigator.clipboard) {
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: clipboardWriteTextMock },
      configurable: true,
    });
  } else {
    vi.spyOn(navigator.clipboard, 'writeText').mockImplementation(clipboardWriteTextMock);
  }
});

afterEach(() => {
  cleanup();
  clipboardWriteTextMock.mockClear();
  vi.restoreAllMocks();
});
