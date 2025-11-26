import { useState } from 'react';
import { usePollingManager } from '@/hooks/use-polling-manager';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Play, Pause, ToggleLeft } from 'lucide-react';

export default function PollingDemo() {
  const [logs, setLogs] = useState<string[]>([]);
  
  const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [`[${timestamp}] ${message}`, ...prev].slice(0, 20));
  };

  const { 
    pause, 
    resume, 
    toggle, 
    isPaused, 
    isPausedByVisibility, 
    isActive, 
    timeUntilNext, 
    lastPollTime, 
    pollCount 
  } = usePollingManager({
    intervalMs: 30000,
    onPoll: async () => {
      addLog(`Poll executed (count: ${pollCount + 1})`);
      await new Promise(resolve => setTimeout(resolve, 100));
    },
    onStateChange: (state) => {
      if (state.isPausedByVisibility) {
        addLog('⚠️ Paused by visibility change');
      }
    }
  });

  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <h1 className="text-3xl font-bold mb-6" data-testid="text-title">Polling Manager Demo</h1>
      
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Controls</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Button 
                onClick={pause} 
                disabled={isPaused}
                data-testid="button-pause"
              >
                <Pause className="w-4 h-4 mr-2" />
                Pause
              </Button>
              <Button 
                onClick={resume} 
                disabled={!isPaused}
                data-testid="button-resume"
              >
                <Play className="w-4 h-4 mr-2" />
                Resume
              </Button>
              <Button 
                onClick={toggle}
                variant="outline"
                data-testid="button-toggle"
              >
                <ToggleLeft className="w-4 h-4 mr-2" />
                Toggle
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Is Active:</span>
              <Badge 
                variant={isActive ? "default" : "secondary"}
                data-testid="badge-is-active"
              >
                {isActive ? 'Yes' : 'No'}
              </Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Manual Pause:</span>
              <Badge 
                variant={isPaused ? "destructive" : "outline"}
                data-testid="badge-is-paused"
              >
                {isPaused ? 'Paused' : 'Running'}
              </Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Visibility Pause:</span>
              <Badge 
                variant={isPausedByVisibility ? "destructive" : "outline"}
                data-testid="badge-visibility-pause"
              >
                {isPausedByVisibility ? 'Hidden' : 'Visible'}
              </Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Time Until Next:</span>
              <Badge variant="secondary" data-testid="badge-time-until-next">
                {Math.ceil(timeUntilNext / 1000)}s
              </Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Poll Count:</span>
              <Badge variant="secondary" data-testid="badge-poll-count">
                {pollCount}
              </Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Last Poll:</span>
              <span className="text-sm font-mono" data-testid="text-last-poll">
                {lastPollTime ? lastPollTime.toLocaleTimeString() : 'Never'}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Activity Log</CardTitle>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => setLogs([])}
            data-testid="button-clear-log"
          >
            Clear
          </Button>
        </CardHeader>
        <CardContent>
          <div className="bg-muted rounded-md p-4 h-64 overflow-y-auto font-mono text-sm">
            {logs.length === 0 ? (
              <p className="text-muted-foreground" data-testid="text-empty-log">No activity yet</p>
            ) : (
              logs.map((log, i) => (
                <div key={i} className="mb-1" data-testid={`log-entry-${i}`}>
                  {log}
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Binary Validation Checklist</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm">
            <li className="flex items-start gap-2">
              <span className="text-green-500">✓</span>
              <span><strong>30-second intervals:</strong> Check poll count increases every 30s</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500">✓</span>
              <span><strong>Tab pause:</strong> Switch to another tab, "Visibility Pause" badge should turn red</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500">✓</span>
              <span><strong>Manual controls:</strong> Use Pause/Resume/Toggle buttons - status updates immediately</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500">✓</span>
              <span><strong>Cleanup on unmount:</strong> Navigate away, intervals cleared automatically</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500">✓</span>
              <span><strong>No overlaps:</strong> Check logs - no concurrent polls during async operations</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500">✓</span>
              <span><strong>Drift correction:</strong> Monitor "Time Until Next" - stays accurate over multiple cycles</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-500">✓</span>
              <span><strong>Immediate poll on resume:</strong> Click Resume - log shows immediate poll execution</span>
            </li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
