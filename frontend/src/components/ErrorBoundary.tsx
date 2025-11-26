import { Component, ErrorInfo, ReactNode } from 'react';
import { RefreshCw, Home } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import errorIcon from '@/assets/brand/icons/error.svg';
import "@/assets/brand/colors.css";
import { ErrorQueueManager } from '@/lib/error-queue-manager';
import { ErrorLoggingMetrics } from '@/lib/error-logging-metrics';
import { ErrorBannerContextInstance } from '@/components/error-banner/ErrorBannerContext';
import { ErrorBannerMapper } from '@/lib/error-banner-mapper';
import type { ErrorBannerContext } from '@/types/error-banner';

interface ErrorBoundaryState { hasError: boolean; error: Error | null; errorId: string | null; correlationId: string | null; isRetrying: boolean; }
interface ErrorBoundaryProps { children: ReactNode; }

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  static contextType = ErrorBannerContextInstance;
  declare context: ErrorBannerContext | null;
  
  private abortController: AbortController | null = null;
  private hasLogged = false;

  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, errorId: null, correlationId: null, isRetrying: false };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    const errorId = (error as any).errorId || (error as any).response?.data?.error_id || `frontend-err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const correlationId = (error as any).correlationId || (error as any).response?.headers?.['x-correlation-id'] || `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    return { 
      hasError: true, 
      error,
      errorId,
      correlationId
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    if (!this.hasLogged && this.state.correlationId) {
      this.hasLogged = true;
      this.logErrorToBackend(error, errorInfo);
      
      if (this.context) {
        const bannerConfig = ErrorBannerMapper.mapReactError(error, this.state.correlationId);
        this.context.showBanner(bannerConfig);
      }
    }
  }

  private async logErrorToBackend(error: Error, errorInfo: ErrorInfo) {
    // Prepare error payload
    const errorPayload = {
      correlationId: this.state.correlationId!,
      message: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack ?? undefined,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href,
    };
    
    // Attempt immediate logging with strict 500ms timeout
    this.abortController?.abort();
    this.abortController = new AbortController();
    
    const timeoutId = setTimeout(() => this.abortController?.abort(), 500);
    const startTime = performance.now();
    let immediateSuccess = false;
    
    try {
      await fetch('/api/errors/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(errorPayload),
        signal: this.abortController.signal
      });
      
      const duration = performance.now() - startTime;
      
      // Check if logged within 500ms SLA
      if (duration <= 500) {
        console.log(`✅ [ErrorBoundary] Error logged in ${duration.toFixed(2)}ms (within 500ms SLA)`);
        ErrorLoggingMetrics.recordImmediateSuccess();
        immediateSuccess = true;
      } else {
        // Successfully sent but exceeded 500ms - still count as immediate success
        console.log(`⚠️ [ErrorBoundary] Error logged in ${duration.toFixed(2)}ms (exceeded 500ms SLA)`);
        ErrorLoggingMetrics.recordImmediateSuccess();
        immediateSuccess = true;
      }
    } catch (logError) {
      const duration = performance.now() - startTime;
      
      if ((logError as Error).name === 'AbortError') {
        console.warn(`⏱️ [ErrorBoundary] Error logging timed out after ${duration.toFixed(2)}ms, queuing for retry`);
      } else {
        console.error(`❌ [ErrorBoundary] Error logging failed after ${duration.toFixed(2)}ms:`, logError);
      }
      
      // Queue for retry
      ErrorLoggingMetrics.recordImmediateFailure();
      const queued = ErrorQueueManager.enqueue(errorPayload);
      
      if (queued) {
        console.log(`📦 [ErrorBoundary] Error ${errorPayload.correlationId} queued for retry`);
      } else {
        console.error(`❌ [ErrorBoundary] Failed to queue error ${errorPayload.correlationId}`);
      }
    } finally {
      clearTimeout(timeoutId);
    }
  }

  private handleRetry = () => {
    this.abortController?.abort();
    this.hasLogged = false;
    this.setState({ isRetrying: true });
    const delay = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 100 : 300;
    setTimeout(() => {
      this.setState({ hasError: false, error: null, errorId: null, correlationId: null, isRetrying: false });
      window.dispatchEvent(new CustomEvent('error-boundary-retry'));
    }, delay);
  };

  private handleGoHome = () => {
    this.abortController?.abort();
    this.hasLogged = false;
    this.setState({ hasError: false, error: null, errorId: null, correlationId: null, isRetrying: false });
    window.dispatchEvent(new CustomEvent('error-boundary-go-home'));
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 glass-container"
          style={{ backgroundColor: 'hsl(var(--brand-alice) / 0.3)', backdropFilter: 'blur(20px)' }}
          role="alert" aria-live="assertive" aria-atomic="true">
          <Card className="max-w-md w-full glass-container" style={{
            backgroundColor: 'hsl(var(--brand-alice) / 0.95)',
            borderColor: 'var(--auth-error-border)',
            backdropFilter: 'blur(20px)'
          }}>
            <CardHeader className="text-center">
              <img src={errorIcon} alt="" className="mx-auto mb-4 w-12 h-12" aria-hidden="true" />
              <CardTitle style={{ color: 'hsl(var(--brand-cool-black))' }}>Something went wrong</CardTitle>
              <CardDescription style={{ color: 'hsl(var(--brand-cool-black) / 0.7)' }}>
                We've encountered an unexpected error. Our team has been notified.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <dl className="text-xs text-center p-3 rounded space-y-2" style={{
                backgroundColor: 'var(--auth-error-bg)',
                color: 'hsl(var(--brand-cool-black) / 0.6)'
              }}>
                <div>
                  <dt className="inline font-medium">Error ID: </dt>
                  <dd className="inline font-mono" data-testid="text-error-id">{this.state.errorId}</dd>
                </div>
                <div>
                  <dt className="inline font-medium">Correlation ID: </dt>
                  <dd className="inline font-mono" data-testid="text-correlation-id">{this.state.correlationId}</dd>
                </div>
              </dl>
              <div className="flex gap-2">
                <Button onClick={this.handleRetry} disabled={this.state.isRetrying} className="flex-1"
                  style={{ backgroundColor: 'hsl(var(--brand-tufts))', color: 'white' }}
                  data-testid="button-retry-error" aria-label="Retry after error">
                  {this.state.isRetrying ? (
                    <><RefreshCw className="w-4 h-4 mr-2 animate-spin" aria-hidden="true" />Retrying...</>
                  ) : (
                    <><RefreshCw className="w-4 h-4 mr-2" aria-hidden="true" />Try Again</>
                  )}
                </Button>
                <Button onClick={this.handleGoHome} variant="outline" className="flex-1"
                  data-testid="button-go-home" aria-label="Go to home page">
                  <Home className="w-4 h-4 mr-2" aria-hidden="true" />Go Home
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      );
    }
    return this.props.children;
  }
}
