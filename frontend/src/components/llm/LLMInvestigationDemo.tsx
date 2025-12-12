/**
 * LLM Investigation Demo Component
 * Demonstrates the LLM investigation flow with async job polling
 * B0.2: Test component for verifying LLM service integration
 */

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { AlertCircle, CheckCircle, Clock, Loader2, RefreshCw } from 'lucide-react';
import { LLMInvestigationsService, type InvestigationRequest, type InvestigationStatusResponse } from '@/api/services/llm-investigations';
import { useAsyncJobPoller } from '@/hooks/use-async-job-poller';

type InvestigationStatus = InvestigationStatusResponse['status'];

const STATUS_CONFIG: Record<InvestigationStatus, { icon: typeof Clock; color: string; label: string }> = {
  queued: { icon: Clock, color: 'bg-yellow-500', label: 'Queued' },
  in_progress: { icon: Loader2, color: 'bg-blue-500', label: 'In Progress' },
  completed: { icon: CheckCircle, color: 'bg-green-500', label: 'Completed' },
  failed: { icon: AlertCircle, color: 'bg-red-500', label: 'Failed' },
  cancelled: { icon: AlertCircle, color: 'bg-gray-500', label: 'Cancelled' },
};

export function LLMInvestigationDemo() {
  const [investigationId, setInvestigationId] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [startError, setStartError] = useState<Error | null>(null);

  const { status, error: pollError, isPolling, refresh } = useAsyncJobPoller<InvestigationStatusResponse>(
    investigationId,
    LLMInvestigationsService.getInvestigationStatus
  );

  const handleStartInvestigation = async () => {
    setIsStarting(true);
    setStartError(null);
    setInvestigationId(null);

    const request: InvestigationRequest = {
      entity_type: 'transaction',
      entity_id: `txn-${Date.now()}`,
      investigation_type: 'discrepancy',
      context: {
        platform: 'shopify',
        amount: 150.00,
        demo: true,
      },
    };

    try {
      const response = await LLMInvestigationsService.startInvestigation(request);
      setInvestigationId(response.investigation_id);
    } catch (err) {
      setStartError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsStarting(false);
    }
  };

  const handleReset = () => {
    setInvestigationId(null);
    setStartError(null);
  };

  const statusConfig = status ? STATUS_CONFIG[status.status] : null;
  const Icon = statusConfig?.icon || Clock;
  const error = startError || pollError;

  return (
    <Card className="w-full max-w-lg" data-testid="card-llm-investigation-demo">
      <CardHeader>
        <CardTitle data-testid="text-demo-title">LLM Investigation Demo</CardTitle>
        <CardDescription data-testid="text-demo-description">
          Demonstrates async job polling with exponential backoff
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {!investigationId && !status && (
          <p className="text-sm text-muted-foreground" data-testid="text-instructions">
            Click the button below to start a demo investigation. The system will poll
            for status updates using exponential backoff.
          </p>
        )}

        {status && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Badge 
                variant="secondary"
                className={statusConfig?.color}
                data-testid="badge-investigation-status"
              >
                <Icon className={`w-3 h-3 mr-1 ${status.status === 'in_progress' ? 'animate-spin' : ''}`} />
                {statusConfig?.label}
              </Badge>
              {isPolling && (
                <span className="text-xs text-muted-foreground" data-testid="text-polling-indicator">
                  Polling...
                </span>
              )}
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Progress</span>
                <span data-testid="text-progress-value">{status.progress}%</span>
              </div>
              <Progress value={status.progress} data-testid="progress-investigation" />
            </div>

            <div className="text-xs text-muted-foreground space-y-1">
              <p data-testid="text-investigation-id">
                <strong>ID:</strong> {status.investigation_id}
              </p>
              <p data-testid="text-investigation-created">
                <strong>Created:</strong> {status.created_at}
              </p>
              <p data-testid="text-investigation-updated">
                <strong>Updated:</strong> {status.updated_at}
              </p>
            </div>

            {status.result && (
              <div className="mt-4 p-3 bg-muted rounded-md" data-testid="div-investigation-result">
                <h4 className="font-semibold text-sm mb-2">Results</h4>
                {status.result.findings && status.result.findings.length > 0 && (
                  <div className="space-y-1">
                    {status.result.findings.map((finding, idx) => (
                      <div key={idx} className="text-xs" data-testid={`text-finding-${idx}`}>
                        <Badge variant="outline" className="mr-1">{finding.severity}</Badge>
                        {finding.description}
                      </div>
                    ))}
                  </div>
                )}
                {status.result.recommendations && status.result.recommendations.length > 0 && (
                  <div className="mt-2">
                    <p className="font-medium text-xs mb-1">Recommendations:</p>
                    <ul className="list-disc list-inside text-xs space-y-1">
                      {status.result.recommendations.map((rec, idx) => (
                        <li key={idx} data-testid={`text-recommendation-${idx}`}>{rec}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {status.error && (
              <div className="mt-4 p-3 bg-destructive/10 rounded-md" data-testid="div-investigation-error">
                <h4 className="font-semibold text-sm text-destructive mb-1">Error</h4>
                <p className="text-xs">{status.error.message}</p>
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="p-3 bg-destructive/10 rounded-md" data-testid="div-api-error">
            <p className="text-sm text-destructive">{error.message}</p>
          </div>
        )}
      </CardContent>

      <CardFooter className="flex gap-2">
        {!investigationId ? (
          <Button
            onClick={handleStartInvestigation}
            disabled={isStarting}
            data-testid="button-start-investigation"
          >
            {isStarting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            Start Investigation
          </Button>
        ) : (
          <>
            <Button
              variant="outline"
              onClick={refresh}
              disabled={isPolling}
              data-testid="button-refresh-status"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${isPolling ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button
              variant="secondary"
              onClick={handleReset}
              data-testid="button-reset"
            >
              Reset
            </Button>
          </>
        )}
      </CardFooter>
    </Card>
  );
}

export default LLMInvestigationDemo;
