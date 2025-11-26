import { useState, useCallback, useRef, useEffect } from 'react';
import { useErrorBanner } from '@/hooks/use-error-banner';
import { ErrorBannerMapper } from '@/lib/error-banner-mapper';

const MIME_TYPES: Record<string, string> = { 'csv': 'text/csv', 'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'pdf': 'application/pdf' };
export type DownloadError = { code: 'NETWORK_ERROR' | 'CORS_ERROR' | 'HTTP_ERROR' | 'ABORT_ERROR'; message: string; httpStatus?: number };

export function useFileDownloader() {
  const { showBanner } = useErrorBanner();
  const [isDownloading, setIsDownloading] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [downloadedBytes, setDownloadedBytes] = useState(0);
  const [totalBytes, setTotalBytes] = useState(0);
  const [error, setError] = useState<DownloadError | null>(null);
  const [showFallbackModal, setShowFallbackModal] = useState(false);
  const [fallbackUrl, setFallbackUrl] = useState<string | null>(null);
  const [fallbackFilename, setFallbackFilename] = useState<string | null>(null);
  const lastProgressUpdateRef = useRef<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const blobUrlsRef = useRef<string[]>([]);
  const revokeTimersRef = useRef<NodeJS.Timeout[]>([]);
  const currentDownloadTokenRef = useRef<number>(0);
  const fallbackTimersRef = useRef<Map<number, NodeJS.Timeout>>(new Map());

  const download = useCallback(async (url: string, filename: string): Promise<void> => {
    abortControllerRef.current?.abort();
    blobUrlsRef.current.forEach(u => URL.revokeObjectURL(u));
    blobUrlsRef.current = []; revokeTimersRef.current.forEach(t => clearTimeout(t)); revokeTimersRef.current = [];
    setIsDownloading(true); setProgress(null); setDownloadedBytes(0); setTotalBytes(0); setError(null); setShowFallbackModal(false); lastProgressUpdateRef.current = 0;
    abortControllerRef.current = new AbortController();
    const downloadToken = ++currentDownloadTokenRef.current;
    const fallbackTimer = setTimeout(() => { if (currentDownloadTokenRef.current === downloadToken) { setShowFallbackModal(true); setFallbackUrl(url); setFallbackFilename(filename); } }, 10000);
    fallbackTimersRef.current.set(downloadToken, fallbackTimer);
    try {
      const response = await fetch(url, { signal: abortControllerRef.current.signal });
      if (!response.ok) throw { code: 'HTTP_ERROR', httpStatus: response.status, message: `Download failed: HTTP ${response.status}` };
      const contentLength = parseInt(response.headers.get('Content-Length') || '0'); setTotalBytes(contentLength);
      const extension = filename.split('.').pop()?.toLowerCase() || '';
      const detectedMime = response.headers.get('Content-Type') || MIME_TYPES[extension] || 'application/octet-stream';
      const expectedMime = MIME_TYPES[extension];
      if (expectedMime && detectedMime !== expectedMime) console.warn(`[FileDownloader] MIME mismatch: expected ${expectedMime}, got ${detectedMime} for ${filename}`);
      let blob: Blob;
      if (contentLength > 1_000_000 && response.body) {
        setProgress(0); const reader = response.body.getReader(); const chunks: Uint8Array[] = []; let downloaded = 0;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          chunks.push(value); downloaded += value.length; const now = Date.now();
          if (downloaded === value.length || downloaded >= contentLength || now - lastProgressUpdateRef.current >= 100) {
            setDownloadedBytes(downloaded); setProgress(contentLength > 0 ? downloaded / contentLength : 0); lastProgressUpdateRef.current = now;
          }
        }
        blob = new Blob(chunks); setProgress(1);
      } else blob = await response.blob();
      if (blob.size === 0) throw new Error('Received empty or corrupt file.');
      const blobUrl = URL.createObjectURL(blob); blobUrlsRef.current.push(blobUrl);
      const link = document.createElement('a');
      link.href = blobUrl; link.download = filename;
      document.body.appendChild(link); link.click(); document.body.removeChild(link);
      revokeTimersRef.current.push(setTimeout(() => URL.revokeObjectURL(blobUrl), 5000));
      if (currentDownloadTokenRef.current === downloadToken) { const timer = fallbackTimersRef.current.get(downloadToken); if (timer) { clearTimeout(timer); fallbackTimersRef.current.delete(downloadToken); } setIsDownloading(false); }
    } catch (err: any) {
      if (currentDownloadTokenRef.current === downloadToken) { const timer = fallbackTimersRef.current.get(downloadToken); if (timer) { clearTimeout(timer); fallbackTimersRef.current.delete(downloadToken); } }
      if (err.name === 'AbortError') { 
        setError({ code: 'ABORT_ERROR', message: 'Download aborted by user' }); 
        const bannerConfig = ErrorBannerMapper.mapDownloadError('ABORT_ERROR');
        showBanner(bannerConfig);
        setIsDownloading(false); 
        return; 
      }
      if (err.code === 'HTTP_ERROR') {
        setError({ code: 'HTTP_ERROR', message: err.message, httpStatus: err.httpStatus });
        const bannerConfig = ErrorBannerMapper.mapDownloadError('HTTP_ERROR');
        showBanner(bannerConfig);
      } else if (err instanceof TypeError && err.message === 'Failed to fetch') {
        setError({ code: 'CORS_ERROR', message: 'Download blocked by CORS policy' });
        const bannerConfig = ErrorBannerMapper.mapDownloadError('CORS_ERROR');
        showBanner(bannerConfig);
      } else {
        setError({ code: 'NETWORK_ERROR', message: 'Network error during download' });
        const bannerConfig = ErrorBannerMapper.mapDownloadError('NETWORK_ERROR');
        showBanner(bannerConfig);
      }
      if (currentDownloadTokenRef.current === downloadToken) setIsDownloading(false);
    }
  }, [showBanner]);
  const abort = useCallback(() => { abortControllerRef.current?.abort(); setIsDownloading(false); }, []);
  useEffect(() => () => { abortControllerRef.current?.abort(); blobUrlsRef.current.forEach(url => URL.revokeObjectURL(url)); revokeTimersRef.current.forEach(timer => clearTimeout(timer)); fallbackTimersRef.current.forEach(timer => clearTimeout(timer)); }, []);
  return { download, abort, isDownloading, progress, downloadedBytes, totalBytes, error, showFallbackModal, fallbackUrl, fallbackFilename };
}
