/** Maximum bytes for inline export preview panels */
export const MAX_EXPORT_PREVIEW_BYTES = 32_768;

/** Maximum DOM nodes mounted in export preview */
export const MAX_EXPORT_PREVIEW_DOM_NODES = 120;

/** Maximum bytes copied to clipboard synchronously */
export const MAX_COPY_JSON_BYTES = 65_536;

/** Maximum artifact bytes for inline download handoff */
export const MAX_DOWNLOAD_ARTIFACT_BYTES = 1_048_576;

const CLIPBOARD_STAGE_KEY = 'skeldir_l9_clipboard_stage_v1';

interface StagedClipboardPayload {
  fingerprint: string;
  text: string;
}

export function isOversizePayload(byteLength: number, limit = MAX_EXPORT_PREVIEW_BYTES): boolean {
  return byteLength > limit;
}

function readClipboardStage(): StagedClipboardPayload | null {
  if (typeof sessionStorage === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(CLIPBOARD_STAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StagedClipboardPayload;
  } catch {
    return null;
  }
}

function writeClipboardStage(payload: StagedClipboardPayload): void {
  if (typeof sessionStorage === 'undefined') return;
  sessionStorage.setItem(CLIPBOARD_STAGE_KEY, JSON.stringify(payload));
}

export function stageClipboardPayload(fingerprint: string, text: string): void {
  writeClipboardStage({ fingerprint, text });
}

export function getStagedClipboardPayload(fingerprint: string): string | null {
  const staged = readClipboardStage();
  return staged?.fingerprint === fingerprint ? staged.text : null;
}

export function clearStagedClipboard(fingerprint?: string): void {
  if (typeof sessionStorage === 'undefined') return;
  if (!fingerprint) {
    sessionStorage.removeItem(CLIPBOARD_STAGE_KEY);
    return;
  }
  const staged = readClipboardStage();
  if (staged?.fingerprint === fingerprint) {
    sessionStorage.removeItem(CLIPBOARD_STAGE_KEY);
  }
}

export function clearClipboardStageForTests(): void {
  clearStagedClipboard();
}

export async function copyTextBounded(
  text: string,
  maxBytes = MAX_COPY_JSON_BYTES,
  fingerprint?: string,
): Promise<'ok' | 'oversize' | 'denied'> {
  const bytes = new TextEncoder().encode(text).length;
  if (bytes > maxBytes) return 'oversize';
  try {
    await navigator.clipboard.writeText(text);
    if (fingerprint) clearStagedClipboard(fingerprint);
    return 'ok';
  } catch (err) {
    if (err instanceof DOMException && err.name === 'NotAllowedError') {
      return 'denied';
    }
    if (err instanceof Error && err.name === 'NotAllowedError') {
      return 'denied';
    }
    throw err;
  }
}
