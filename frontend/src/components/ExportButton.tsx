import { useReducer, useCallback, useRef, useEffect } from 'react';
import { useApiClient } from '@/hooks/use-api-client';
import { useFileDownloader } from '@/hooks/use-file-downloader';
import { useErrorBanner } from '@/hooks/use-error-banner';
import { ErrorBannerMapper } from '@/lib/error-banner-mapper';
import { Check } from 'lucide-react';
import { ExportIcon as ExportIconCustom } from '@/components/icons';
import styles from './ExportButton.module.css';
import csvIcon from '@/assets/brand/icons/csv.svg';
import excelIcon from '@/assets/brand/icons/excel.svg';
import pdfIcon from '@/assets/brand/icons/pdf.svg';
import chevronIcon from '@/assets/brand/icons/chevron-down.svg';

type ExportFormat = 'csv' | 'excel' | 'pdf';

type ErrorState = {
  type: 'NetworkTimeout' | 'Unauthorized' | 'InvalidFormat' | 'ServerError' | 'DownloadFailed' | 'CorruptFile' | 'ProgressTimeout';
  message: string;
  retryable: boolean;
  correlationId?: string;
};

type State = {
  isOpen: boolean;
  selectedFormat: ExportFormat;
  isExporting: boolean;
  progress: number | null;
  error: ErrorState | null;
  showToast: boolean;
  downloadUrl: string | null;
  retryCount: number;
};

type Action =
  | { type: 'TOGGLE_DROPDOWN' }
  | { type: 'CLOSE_DROPDOWN' }
  | { type: 'SELECT_FORMAT'; format: ExportFormat }
  | { type: 'START_EXPORT' }
  | { type: 'UPDATE_PROGRESS'; progress: number }
  | { type: 'SET_ERROR'; error: ErrorState }
  | { type: 'COMPLETE_EXPORT'; url: string }
  | { type: 'CLOSE_TOAST' }
  | { type: 'RESET' }
  | { type: 'INCREMENT_RETRY' };

const initialState: State = {
  isOpen: false,
  selectedFormat: 'csv',
  isExporting: false,
  progress: null,
  error: null,
  showToast: false,
  downloadUrl: null,
  retryCount: 0,
};

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'TOGGLE_DROPDOWN':
      return { ...state, isOpen: !state.isOpen };
    case 'CLOSE_DROPDOWN':
      return { ...state, isOpen: false };
    case 'SELECT_FORMAT':
      return { ...state, selectedFormat: action.format, isOpen: false };
    case 'START_EXPORT':
      return { ...state, isExporting: true, error: null, progress: 0, showToast: false, isOpen: false };
    case 'UPDATE_PROGRESS':
      return { ...state, progress: action.progress };
    case 'SET_ERROR':
      return { ...state, error: action.error, isExporting: false, progress: null };
    case 'COMPLETE_EXPORT':
      return { ...state, isExporting: false, progress: 100, showToast: true, downloadUrl: action.url, retryCount: 0 };
    case 'CLOSE_TOAST':
      return { ...state, showToast: false, error: null };
    case 'INCREMENT_RETRY':
      return { ...state, retryCount: state.retryCount + 1 };
    case 'RESET':
      return initialState;
    default:
      return state;
  }
}

const formatOptions = [
  { value: 'csv' as const, label: 'CSV', icon: csvIcon },
  { value: 'excel' as const, label: 'Excel (.xlsx)', icon: excelIcon },
  { value: 'pdf' as const, label: 'PDF', icon: pdfIcon },
];

interface ExportButtonProps {
  data?: any;
}

export function ExportButton({ data }: ExportButtonProps = {}) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const { request } = useApiClient();
  const { download } = useFileDownloader();
  const { showBanner } = useErrorBanner();
  const dropdownRef = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<NodeJS.Timeout>();
  const progressIntervalRef = useRef<NodeJS.Timeout>();
  const selectedFormatRef = useRef<ExportFormat>(state.selectedFormat);

  useEffect(() => {
    selectedFormatRef.current = state.selectedFormat;
  }, [state.selectedFormat]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        dispatch({ type: 'CLOSE_DROPDOWN' });
      }
    }
    if (state.isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [state.isOpen]);

  useEffect(() => {
    if (state.showToast || state.error) {
      timeoutRef.current = setTimeout(() => dispatch({ type: 'CLOSE_TOAST' }), 5000);
      return () => clearTimeout(timeoutRef.current);
    }
  }, [state.showToast, state.error]);

  const handleExport = useCallback(async (formatOverride?: ExportFormat) => {
    const format = formatOverride || selectedFormatRef.current;
    dispatch({ type: 'START_EXPORT' });
    
    const abortController = new AbortController();
    let exportTimeoutId: NodeJS.Timeout | undefined;
    let progressIntervalId: NodeJS.Timeout | undefined;
    let progressTimeoutId: NodeJS.Timeout | undefined;
    let isAborted = false;
    
    exportTimeoutId = setTimeout(() => {
      isAborted = true;
      abortController.abort();
      if (progressIntervalId) clearInterval(progressIntervalId);
      if (progressTimeoutId) clearTimeout(progressTimeoutId);
      const error = { type: 'NetworkTimeout' as const, message: 'Export timed out. Please try again.', retryable: true };
      dispatch({ type: 'SET_ERROR', error });
      const bannerConfig = ErrorBannerMapper.mapExportError(error.type);
      showBanner(bannerConfig);
    }, 30000);

    const startTime = Date.now();
    progressTimeoutId = setTimeout(() => {
      isAborted = true;
      abortController.abort();
      if (exportTimeoutId) clearTimeout(exportTimeoutId);
      if (progressIntervalId) clearInterval(progressIntervalId);
      const error = { type: 'ProgressTimeout' as const, message: 'Export is taking longer than expected.', retryable: true, correlationId: `timeout-${startTime}` };
      dispatch({ type: 'SET_ERROR', error });
      const bannerConfig = ErrorBannerMapper.mapExportError(error.type, error.correlationId);
      showBanner(bannerConfig);
    }, 300000);

    let currentProgress = 0;
    progressIntervalId = setInterval(() => {
      currentProgress = Math.min(95, currentProgress + 5);
      dispatch({ type: 'UPDATE_PROGRESS', progress: currentProgress });
    }, 500);

    try {
      const response = await request<{ data?: any }, { url: string }>('POST', `/api/export/${format}`, { 
        body: data ? { data } : undefined,
        signal: abortController.signal 
      });
      
      if (isAborted) return;
      
      if (exportTimeoutId) clearTimeout(exportTimeoutId);
      if (progressIntervalId) clearInterval(progressIntervalId);
      if (progressTimeoutId) clearTimeout(progressTimeoutId);
      
      if (response.data) {
        dispatch({ type: 'UPDATE_PROGRESS', progress: 100 });
        
        try {
          await download(response.data.url, `export.${format === 'excel' ? 'xlsx' : format}`);
          dispatch({ type: 'COMPLETE_EXPORT', url: response.data.url });
        } catch (downloadErr: any) {
          dispatch({ type: 'CLOSE_TOAST' });
          let error;
          if (downloadErr.message?.includes('empty') || downloadErr.message?.includes('corrupt')) {
            error = { type: 'CorruptFile' as const, message: 'Received empty or corrupt file.', retryable: true };
          } else {
            error = { type: 'DownloadFailed' as const, message: 'File download failed. Check browser permissions.', retryable: true };
          }
          dispatch({ type: 'SET_ERROR', error });
          const bannerConfig = ErrorBannerMapper.mapExportError(error.type);
          showBanner(bannerConfig);
        }
      } else if (response.error) {
        throw response.error;
      }
    } catch (err: any) {
      if (isAborted) return;
      
      if (exportTimeoutId) clearTimeout(exportTimeoutId);
      if (progressIntervalId) clearInterval(progressIntervalId);
      if (progressTimeoutId) clearTimeout(progressTimeoutId);
      
      if (err.name === 'AbortError') {
        return;
      }
      
      const status = err.status || err.response?.status;
      const correlationId = err.correlationId || err.response?.headers?.['x-correlation-id'];
      
      let error;
      if (status === 401) {
        error = { type: 'Unauthorized' as const, message: 'You do not have permission to export data.', retryable: false, correlationId };
      } else if (status === 400) {
        error = { type: 'InvalidFormat' as const, message: 'Selected format is not supported.', retryable: false, correlationId };
      } else if (status === 500 || status === 503) {
        error = {
          type: 'ServerError' as const,
          message: `Server error occurred.${correlationId ? ` Reference: ${correlationId}` : ''}`,
          retryable: true,
          correlationId
        };
      } else {
        error = { type: 'DownloadFailed' as const, message: 'File download failed. Check browser permissions.', retryable: true, correlationId };
      }
      dispatch({ type: 'SET_ERROR', error });
      const bannerConfig = ErrorBannerMapper.mapExportError(error.type, error.correlationId);
      showBanner(bannerConfig);
    }
  }, [request, download, showBanner]);

  const handleRetry = useCallback(async () => {
    if (state.retryCount >= 3) {
      const error = { type: 'NetworkTimeout' as const, message: 'Maximum retries exceeded.', retryable: false };
      dispatch({ type: 'SET_ERROR', error });
      const bannerConfig = ErrorBannerMapper.mapExportError(error.type);
      showBanner(bannerConfig);
      return;
    }
    dispatch({ type: 'INCREMENT_RETRY' });
    const delay = Math.pow(2, state.retryCount) * 1000;
    setTimeout(handleExport, delay);
  }, [state.retryCount, handleExport, showBanner]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape' && state.isOpen) {
      dispatch({ type: 'CLOSE_DROPDOWN' });
      e.preventDefault();
    } else if (e.key === 'ArrowDown' && !state.isOpen && !state.isExporting) {
      dispatch({ type: 'TOGGLE_DROPDOWN' });
      e.preventDefault();
    } else if (e.key === 'Enter' && !state.isOpen && !state.isExporting) {
      handleExport();
      e.preventDefault();
    }
  }, [state.isOpen, state.isExporting, handleExport]);

  return (
    <div style={{ position: 'relative' }} ref={dropdownRef}>
      <div className={styles.buttonContainer}>
        <button
          className={styles.exportButton}
          onClick={() => state.isExporting ? null : handleExport()}
          onKeyDown={handleKeyDown}
          disabled={state.isExporting}
          data-testid="button-export"
        >
          {state.isExporting ? (
            <svg className={styles.spinner} viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="10" r="8" stroke="#93BFEF" strokeWidth="3" strokeLinecap="round" strokeDasharray="40 10" />
            </svg>
          ) : (
            <div className={styles.icon}>
              <ExportIconCustom size={20} aria-label="Export" />
            </div>
          )}
          <span>{state.isExporting ? (state.progress !== null ? `${state.progress}%` : 'Exporting...') : 'Export'}</span>
        </button>
        {!state.isExporting && (
          <button
            className={styles.chevronButton}
            onClick={() => dispatch({ type: 'TOGGLE_DROPDOWN' })}
            aria-expanded={state.isOpen}
            aria-controls="export-dropdown"
            aria-label="Select export format"
            data-testid="button-format-selector"
          >
            <img
              src={chevronIcon}
              alt=""
              className={`${styles.chevron} ${state.isOpen ? styles.chevronOpen : ''}`}
            />
          </button>
        )}
      </div>
      
      {state.isExporting && state.progress !== null && (
        <div 
          className={styles.progressContainer} 
          role="progressbar" 
          aria-valuenow={state.progress} 
          aria-valuemin={0} 
          aria-valuemax={100}
          aria-valuetext={`${state.progress}% complete`}
        >
          <div className={styles.progressFill} style={{ width: `${state.progress}%` }} />
        </div>
      )}

      {state.isOpen && !state.isExporting && (
        <div 
          id="export-dropdown"
          className={styles.dropdownContainer} 
          role="menu"
          aria-label="Export format options"
          data-testid="dropdown-formats"
        >
          {formatOptions.map(({ value, label, icon }) => (
            <button
              key={value}
              className={styles.formatOption}
              role="menuitem"
              onClick={() => {
                dispatch({ type: 'SELECT_FORMAT', format: value });
                handleExport(value);
              }}
              data-testid={`option-format-${value}`}
            >
              <img src={icon} alt="" className={styles.formatIcon} />
              <span>{label}</span>
              {state.selectedFormat === value && <Check className={styles.checkmark} aria-label="Selected" />}
            </button>
          ))}
        </div>
      )}

      {state.showToast && state.downloadUrl && (
        <div className={styles.toast} data-testid="toast-success">
          <div className={styles.toastContent}>
            <Check className={styles.toastIcon} />
            <div>
              <div className={styles.toastMessage}>Export complete</div>
              <button
                className={styles.toastLink}
                onClick={() => state.downloadUrl && download(state.downloadUrl, `export.${selectedFormatRef.current === 'excel' ? 'xlsx' : selectedFormatRef.current}`)}
                data-testid="link-download"
              >
                Download file
              </button>
            </div>
          </div>
          <div className={styles.toastCountdown} />
        </div>
      )}
    </div>
  );
}
